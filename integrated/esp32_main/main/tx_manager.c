#include "tx_manager.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "app_config.h"
#include "socket_transport.h"

typedef struct {
    char line[MAX_TX_LINE_LENGTH + 1];
    uint32_t socket_generation;
} tx_message_t;

static const char *TAG = "TX";
static QueueHandle_t s_high_queue;
static QueueHandle_t s_latest_status_queue;
static portMUX_TYPE s_stats_lock = portMUX_INITIALIZER_UNLOCKED;
static uint32_t s_high_enqueued;
static uint32_t s_high_dropped;
static uint32_t s_status_published;

static bool make_message(const char *line, tx_message_t *message)
{
    if (!line || !message) return false;

    const size_t length = strlen(line);
    if (length == 0 || length > MAX_TX_LINE_LENGTH) {
        ESP_LOGE(TAG, "Invalid TX length: %u", (unsigned)length);
        return false;
    }

    (void)snprintf(message->line, sizeof(message->line), "%s", line);
    message->socket_generation = socket_transport_get_generation();
    return true;
}

bool tx_manager_enqueue_high(const char *line)
{
    tx_message_t message;
    if (!make_message(line, &message)) return false;

    if (xQueueSend(s_high_queue, &message, 0) != pdTRUE) {
        taskENTER_CRITICAL(&s_stats_lock);
        s_high_dropped++;
        taskEXIT_CRITICAL(&s_stats_lock);
        ESP_LOGE(TAG, "High-priority TX queue full");
        return false;
    }

    taskENTER_CRITICAL(&s_stats_lock);
    s_high_enqueued++;
    taskEXIT_CRITICAL(&s_stats_lock);

    return true;
}

bool tx_manager_overwrite_latest_status(const char *line)
{
    tx_message_t message;
    if (!make_message(line, &message)) return false;

    const bool queued = xQueueOverwrite(s_latest_status_queue, &message) == pdTRUE;
    if (queued) {
        taskENTER_CRITICAL(&s_stats_lock);
        s_status_published++;
        taskEXIT_CRITICAL(&s_stats_lock);
    }
    return queued;
}

void tx_manager_clear(void)
{
    if (s_high_queue) (void)xQueueReset(s_high_queue);
    if (s_latest_status_queue) (void)xQueueReset(s_latest_status_queue);
}

static bool transmit_one(const tx_message_t *message)
{
    const int send_result = socket_transport_send_line_if_current(
        message->line,
        message->socket_generation
    );

    if (send_result != 0 &&
        message->socket_generation == socket_transport_get_generation()) {
        ESP_LOGW(TAG, "Socket send failed; closing active socket");
        socket_transport_force_close();
    }
    return send_result == 0;
}

static void transmit_task(void *argument)
{
    (void)argument;
    tx_message_t message;
    TickType_t last_summary = xTaskGetTickCount();
    uint32_t sent_ok = 0;
    uint32_t sent_failed = 0;

    while (true) {
        /*
         * Wait on the high-priority queue first.
         *
         * This fixes both issues seen in v5.3:
         *  1) command-result STATUS must be preferred over periodic STATUS;
         *  2) the task must block/yield so IDLE0 can run and feed the watchdog.
         *
         * If no high-priority message arrives within 10 ms, send the latest
         * periodic STATUS if one is pending. A 1-tick delay after every send
         * prevents a continuously non-empty queue from starving CPU0's idle
         * task.
         */
        if (xQueueReceive(
                s_high_queue,
                &message,
                pdMS_TO_TICKS(10)
            ) == pdTRUE) {
            if (transmit_one(&message)) sent_ok++;
            else sent_failed++;
            vTaskDelay(pdMS_TO_TICKS(1));
        } else if (xQueueReceive(
                s_latest_status_queue,
                &message,
                0
            ) == pdTRUE) {
            if (transmit_one(&message)) sent_ok++;
            else sent_failed++;
            vTaskDelay(pdMS_TO_TICKS(1));
        }

        const TickType_t now = xTaskGetTickCount();
        if (now - last_summary >= pdMS_TO_TICKS(10000)) {
            uint32_t high_enqueued;
            uint32_t high_dropped;
            uint32_t status_published;
            taskENTER_CRITICAL(&s_stats_lock);
            high_enqueued = s_high_enqueued;
            high_dropped = s_high_dropped;
            status_published = s_status_published;
            taskEXIT_CRITICAL(&s_stats_lock);
            ESP_LOGI(TAG,
                     "summary sent_ok=%" PRIu32 " sent_failed=%" PRIu32
                     " high_enqueued=%" PRIu32 " high_dropped=%" PRIu32
                     " status_published=%" PRIu32 " high_depth=%u status_pending=%u",
                     sent_ok, sent_failed, high_enqueued, high_dropped,
                     status_published,
                     (unsigned)uxQueueMessagesWaiting(s_high_queue),
                     (unsigned)uxQueueMessagesWaiting(s_latest_status_queue));
            last_summary = now;
        }
    }
}

void tx_manager_init(void)
{
    s_high_queue = xQueueCreate(TX_HIGH_QUEUE_LENGTH, sizeof(tx_message_t));
    s_latest_status_queue = xQueueCreate(1, sizeof(tx_message_t));

    configASSERT(s_high_queue != NULL);
    configASSERT(s_latest_status_queue != NULL);
}

void tx_manager_start(void)
{
    const BaseType_t created = xTaskCreate(
        transmit_task,
        "TransmitTask",
        4096,
        NULL,
        8,
        NULL
    );

    configASSERT(created == pdPASS);
}
