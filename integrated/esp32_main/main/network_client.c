#include "network_client.h"

#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"

#include "app_config.h"
#include "protocol.h"
#include "socket_transport.h"
#include "tx_manager.h"
#include "vehicle_control.h"
#include "wifi_manager.h"

static const char *TAG = "TCP";
static portMUX_TYPE s_heartbeat_lock = portMUX_INITIALIZER_UNLOCKED;
static TickType_t s_last_heartbeat_tick;
static bool s_watch_started;
static bool s_timeout_fired;

static void reset_heartbeat_watchdog(void)
{
    taskENTER_CRITICAL(&s_heartbeat_lock);
    s_last_heartbeat_tick = xTaskGetTickCount();
    s_watch_started = true;
    s_timeout_fired = false;
    taskEXIT_CRITICAL(&s_heartbeat_lock);
}

static void record_heartbeat(uint32_t seq)
{
    reset_heartbeat_watchdog();
    ESP_LOGD(TAG, "HEARTBEAT seq=%" PRIu32, seq);
}

static int connect_to_server(void)
{
    const int fd = socket(AF_INET, SOCK_STREAM, IPPROTO_IP);
    if (fd < 0) {
        ESP_LOGE(TAG, "socket() failed: errno=%d", errno);
        return -1;
    }

    const struct timeval receive_timeout = {.tv_sec = 0, .tv_usec = 100000};
    const struct timeval send_timeout = {.tv_sec = 0, .tv_usec = 200000};
    (void)setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO,
                     &receive_timeout, sizeof(receive_timeout));
    (void)setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO,
                     &send_timeout, sizeof(send_timeout));

    struct sockaddr_in address = {
        .sin_family = AF_INET,
        .sin_port = htons(SERVER_PORT),
    };

    if (inet_pton(AF_INET, SERVER_IPV4, &address.sin_addr) != 1) {
        ESP_LOGE(TAG, "Invalid SERVER_IPV4: %s", SERVER_IPV4);
        (void)close(fd);
        return -1;
    }

    ESP_LOGI(TAG, "Connecting to %s:%d", SERVER_IPV4, SERVER_PORT);
    if (connect(fd, (struct sockaddr *)&address, sizeof(address)) != 0) {
        ESP_LOGW(TAG, "connect() failed: errno=%d", errno);
        (void)close(fd);
        return -1;
    }
    return fd;
}

static void process_line(const char *line)
{
    protocol_message_t message;
    char error[128] = {0};
    if (protocol_parse_line(line, &message, error, sizeof(error)) != 0) {
        ESP_LOGW(TAG, "Protocol reject: %s | %s", error, line);
        return;
    }

    ESP_LOGI(TAG, "RX type=%s", protocol_message_type_to_string(message.type));

    if (message.type == PROTOCOL_MSG_HEARTBEAT) {
        if (vehicle_control_session_matches(message.session_id)) {
            record_heartbeat(message.heartbeat_seq);
        } else {
            ESP_LOGW(TAG, "Heartbeat session mismatch");
        }
        return;
    }

    if (message.type == PROTOCOL_MSG_HELLO_ACK &&
        message.hello_result != HELLO_RESULT_REJECTED) {
        reset_heartbeat_watchdog();
    }

    vehicle_control_submit_message(&message);

    if (message.type == PROTOCOL_MSG_HELLO_ACK &&
        message.hello_result == HELLO_RESULT_REJECTED) {
        socket_transport_force_close();
    }
}

static int append_stream(char *buffer, size_t *length,
                         const char *bytes, size_t byte_count)
{
    if (*length + byte_count > TCP_STREAM_BUFFER_LENGTH) {
        ESP_LOGE(TAG, "TCP stream buffer overflow; resetting");
        *length = 0;
        return -1;
    }

    memcpy(buffer + *length, bytes, byte_count);
    *length += byte_count;

    while (true) {
        char *newline = memchr(buffer, '\n', *length);
        if (!newline) {
            if (*length > MAX_NDJSON_LINE_LENGTH) {
                ESP_LOGE(TAG, "NDJSON line exceeds maximum length");
                *length = 0;
                return -1;
            }
            break;
        }

        const size_t line_length = (size_t)(newline - buffer);
        if (line_length > 0 && line_length <= MAX_NDJSON_LINE_LENGTH) {
            char line[MAX_NDJSON_LINE_LENGTH + 1];
            memcpy(line, buffer, line_length);
            line[line_length] = '\0';
            if (line_length > 0 && line[line_length - 1] == '\r') {
                line[line_length - 1] = '\0';
            }
            process_line(line);
        } else if (line_length > MAX_NDJSON_LINE_LENGTH) {
            ESP_LOGE(TAG, "Oversized NDJSON line discarded");
        }

        const size_t consumed = line_length + 1;
        const size_t remaining = *length - consumed;
        memmove(buffer, buffer + consumed, remaining);
        *length = remaining;
    }
    return 0;
}

static void enqueue_hello(void)
{
    char hello[MAX_NDJSON_LINE_LENGTH + 1];
    vehicle_control_build_hello(hello, sizeof(hello));
    if (!tx_manager_enqueue_high(hello)) {
        ESP_LOGW(TAG, "Failed to enqueue HELLO");
    }
}

static void communication_task(void *argument)
{
    (void)argument;
    char stream_buffer[TCP_STREAM_BUFFER_LENGTH];
    char temporary[256];

    while (true) {
        (void)wifi_manager_wait_connected(portMAX_DELAY);
        const int fd = connect_to_server();
        if (fd < 0) {
            vTaskDelay(pdMS_TO_TICKS(TCP_RECONNECT_DELAY_MS));
            continue;
        }

        tx_manager_clear();
        socket_transport_install(fd);
        vehicle_control_notify_tcp_connected();

        size_t stream_length = 0;
        TickType_t last_hello = 0;
        ESP_LOGI(TAG, "TCP connected");

        while (wifi_manager_is_connected() && socket_transport_is_connected()) {
            const TickType_t now = xTaskGetTickCount();
            if (!vehicle_control_is_session_active() &&
                now - last_hello >= pdMS_TO_TICKS(HELLO_RETRY_MS)) {
                last_hello = now;
                enqueue_hello();
            }

            const int received = recv(fd, temporary, sizeof(temporary), 0);
            if (received > 0) {
                (void)append_stream(stream_buffer, &stream_length,
                                    temporary, (size_t)received);
                continue;
            }
            if (received == 0) {
                ESP_LOGW(TAG, "TCP peer closed connection");
                break;
            }
            if (errno == EAGAIN || errno == EWOULDBLOCK) continue;
            ESP_LOGW(TAG, "recv() failed: errno=%d", errno);
            break;
        }

        socket_transport_clear_if_matches(fd);
        tx_manager_clear();
        vehicle_control_notify_tcp_disconnected();
        ESP_LOGW(TAG, "TCP disconnected; retrying");
        vTaskDelay(pdMS_TO_TICKS(TCP_RECONNECT_DELAY_MS));
    }
}

static void heartbeat_watchdog_task(void *argument)
{
    (void)argument;
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(50));
        if (!vehicle_control_is_session_active()) continue;

        bool fire = false;
        TickType_t elapsed = 0;
        taskENTER_CRITICAL(&s_heartbeat_lock);
        if (s_watch_started && !s_timeout_fired) {
            const TickType_t now = xTaskGetTickCount();
            elapsed = now - s_last_heartbeat_tick;
            if (elapsed >= pdMS_TO_TICKS(HEARTBEAT_TIMEOUT_MS)) {
                s_timeout_fired = true;
                fire = true;
            }
        }
        taskEXIT_CRITICAL(&s_heartbeat_lock);

        if (fire) {
            ESP_LOGE(TAG, "HEARTBEAT timeout after %" PRIu32 " ms",
                     (uint32_t)(elapsed * portTICK_PERIOD_MS));
            vehicle_control_notify_comm_timeout();
            socket_transport_force_close();
        }
    }
}

void network_client_start(void)
{
    taskENTER_CRITICAL(&s_heartbeat_lock);
    s_last_heartbeat_tick = 0;
    s_watch_started = false;
    s_timeout_fired = false;
    taskEXIT_CRITICAL(&s_heartbeat_lock);

    BaseType_t created = xTaskCreate(communication_task, "CommunicationTask",
                                     8192, NULL, 8, NULL);
    configASSERT(created == pdPASS);
    created = xTaskCreate(heartbeat_watchdog_task, "HeartbeatWatchdog",
                          3072, NULL, 9, NULL);
    configASSERT(created == pdPASS);
}
