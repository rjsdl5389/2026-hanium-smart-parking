#include "socket_transport.h"

#include <errno.h>
#include <inttypes.h>
#include <stddef.h>
#include <string.h>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "lwip/sockets.h"

static SemaphoreHandle_t s_socket_mutex;
static int s_socket_fd = -1;
static uint32_t s_generation;
static portMUX_TYPE s_generation_lock = portMUX_INITIALIZER_UNLOCKED;
static const char *TAG = "SOCKET_TX";

static void bump_generation(void)
{
    taskENTER_CRITICAL(&s_generation_lock);
    s_generation++;
    taskEXIT_CRITICAL(&s_generation_lock);
}

static int send_all(int fd, const char *data, size_t length)
{
    size_t sent_total = 0;
    while (sent_total < length) {
        const int sent = send(fd, data + sent_total, length - sent_total, 0);
        if (sent < 0 && errno == EINTR) continue;
        if (sent <= 0) return -1;
        sent_total += (size_t)sent;
    }
    return 0;
}

void socket_transport_init(void)
{
    s_socket_mutex = xSemaphoreCreateMutex();
    configASSERT(s_socket_mutex != NULL);
    taskENTER_CRITICAL(&s_generation_lock);
    s_generation = 1;
    taskEXIT_CRITICAL(&s_generation_lock);
}

void socket_transport_install(int socket_fd)
{
    xSemaphoreTake(s_socket_mutex, portMAX_DELAY);
    if (s_socket_fd >= 0 && s_socket_fd != socket_fd) {
        (void)shutdown(s_socket_fd, SHUT_RDWR);
        (void)close(s_socket_fd);
    }
    bump_generation();
    s_socket_fd = socket_fd;
    xSemaphoreGive(s_socket_mutex);
}

void socket_transport_clear_if_matches(int socket_fd)
{
    xSemaphoreTake(s_socket_mutex, portMAX_DELAY);
    if (s_socket_fd == socket_fd) {
        (void)shutdown(s_socket_fd, SHUT_RDWR);
        (void)close(s_socket_fd);
        s_socket_fd = -1;
        bump_generation();
    }
    xSemaphoreGive(s_socket_mutex);
}

void socket_transport_force_close(void)
{
    xSemaphoreTake(s_socket_mutex, portMAX_DELAY);
    if (s_socket_fd >= 0) {
        (void)shutdown(s_socket_fd, SHUT_RDWR);
        (void)close(s_socket_fd);
        s_socket_fd = -1;
        bump_generation();
    }
    xSemaphoreGive(s_socket_mutex);
}

bool socket_transport_is_connected(void)
{
    bool connected;
    xSemaphoreTake(s_socket_mutex, portMAX_DELAY);
    connected = s_socket_fd >= 0;
    xSemaphoreGive(s_socket_mutex);
    return connected;
}

uint32_t socket_transport_get_generation(void)
{
    uint32_t generation;
    taskENTER_CRITICAL(&s_generation_lock);
    generation = s_generation;
    taskEXIT_CRITICAL(&s_generation_lock);
    return generation;
}

int socket_transport_send_line_if_current(const char *line, uint32_t generation)
{
    if (!line) return -1;
    int result = -1;

    xSemaphoreTake(s_socket_mutex, portMAX_DELAY);
    const uint32_t current_generation = socket_transport_get_generation();
    if (s_socket_fd >= 0 && generation == current_generation) {
        const TickType_t started = xTaskGetTickCount();
        const size_t length = strlen(line);
        if (send_all(s_socket_fd, line, length) == 0 &&
            send_all(s_socket_fd, "\n", 1) == 0) {
            result = 0;
        } else {
            ESP_LOGW(TAG, "send failed generation=%" PRIu32 " errno=%d",
                     generation, errno);
        }
        const uint32_t elapsed_ms = (uint32_t)(
            (xTaskGetTickCount() - started) * portTICK_PERIOD_MS);
        if (elapsed_ms >= 100) {
            ESP_LOGW(TAG, "slow send generation=%" PRIu32
                     " bytes=%u elapsed_ms=%" PRIu32 " result=%d",
                     generation, (unsigned)(length + 1), elapsed_ms, result);
        }
    }
    xSemaphoreGive(s_socket_mutex);
    return result;
}
