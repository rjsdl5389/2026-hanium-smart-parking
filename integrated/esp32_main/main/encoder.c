#include "encoder.h"

#include <stdbool.h>
#include <stdint.h>

#include "app_config.h"
#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/portmacro.h"

static const char *TAG = "ENCODER";
static portMUX_TYPE s_encoder_lock = portMUX_INITIALIZER_UNLOCKED;
static volatile int64_t s_encoder_count = 0;
static volatile uint8_t s_previous_ab = 0;

/* Previous AB in the high two bits, current AB in the low two bits. */
static const int8_t QUADRATURE_TRANSITION[16] = {
     0, -1, +1,  0,
    +1,  0,  0, -1,
    -1,  0,  0, +1,
     0, +1, -1,  0,
};

static uint8_t read_ab(void)
{
    const uint8_t a = (uint8_t)(gpio_get_level(ENCODER_A_GPIO) & 0x1);
    const uint8_t b = (uint8_t)(gpio_get_level(ENCODER_B_GPIO) & 0x1);
    return (uint8_t)((a << 1) | b);
}

static void encoder_edge_isr(void *argument)
{
    (void)argument;
    const uint8_t current_ab = read_ab();

    portENTER_CRITICAL_ISR(&s_encoder_lock);
    const uint8_t transition = (uint8_t)((s_previous_ab << 2) | current_ab);
    const int8_t raw_delta = QUADRATURE_TRANSITION[transition & 0x0F];
    s_encoder_count += (int64_t)(raw_delta * ENCODER_DIRECTION_SIGN);
    s_previous_ab = current_ab;
    portEXIT_CRITICAL_ISR(&s_encoder_lock);
}

void encoder_init(void)
{
    gpio_config_t config = {
        .pin_bit_mask = (1ULL << ENCODER_A_GPIO) | (1ULL << ENCODER_B_GPIO),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_ANYEDGE,
    };
    ESP_ERROR_CHECK(gpio_config(&config));

    portENTER_CRITICAL(&s_encoder_lock);
    s_encoder_count = 0;
    s_previous_ab = read_ab();
    portEXIT_CRITICAL(&s_encoder_lock);

    esp_err_t result = gpio_install_isr_service(0);
    if (result != ESP_OK && result != ESP_ERR_INVALID_STATE) {
        ESP_ERROR_CHECK(result);
    }
    ESP_ERROR_CHECK(gpio_isr_handler_add(ENCODER_A_GPIO, encoder_edge_isr, NULL));
    ESP_ERROR_CHECK(gpio_isr_handler_add(ENCODER_B_GPIO, encoder_edge_isr, NULL));

    ESP_LOGI(TAG,
             "Quadrature encoder initialized: A=GPIO%d B=GPIO%d sign=%d, no internal pulls",
             ENCODER_A_GPIO, ENCODER_B_GPIO, ENCODER_DIRECTION_SIGN);
}

int64_t encoder_get_count(void)
{
    int64_t value;
    portENTER_CRITICAL(&s_encoder_lock);
    value = s_encoder_count;
    portEXIT_CRITICAL(&s_encoder_lock);
    return value;
}

void encoder_reset_count(void)
{
    portENTER_CRITICAL(&s_encoder_lock);
    s_encoder_count = 0;
    s_previous_ab = read_ab();
    portEXIT_CRITICAL(&s_encoder_lock);
    ESP_LOGI(TAG, "Encoder count reset to zero");
}
