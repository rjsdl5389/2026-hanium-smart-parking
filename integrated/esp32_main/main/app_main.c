#include "esp_err.h"
#include "esp_log.h"
#include "nvs_flash.h"

#include "actuator.h"
#include "app_config.h"
#include "encoder.h"
#include "network_client.h"
#include "socket_transport.h"
#include "tx_manager.h"
#include "vehicle_control.h"
#include "wifi_manager.h"

static const char *TAG = "APP";

static void initialize_nvs(void)
{
    esp_err_t result = nvs_flash_init();
    if (result == ESP_ERR_NVS_NO_FREE_PAGES ||
        result == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        result = nvs_flash_init();
    }
    ESP_ERROR_CHECK(result);
}

void app_main(void)
{
    ESP_LOGI(TAG, "Hanium REMOTE_DIRECT encoder v3 firmware starting");
    ESP_LOGI(TAG, "Firmware version: %s", FIRMWARE_VERSION);
    ESP_LOGW(TAG, "ENABLE_ACTUATOR_OUTPUT=%d", ENABLE_ACTUATOR_OUTPUT);
    ESP_LOGW(TAG, "DAY3_ALLOW_GO_WITHOUT_POSE=%d", DAY3_ALLOW_GO_WITHOUT_POSE);

    initialize_nvs();
    actuator_init();
    encoder_init();
    socket_transport_init();
    tx_manager_init();
    tx_manager_start();
    vehicle_control_init();
    wifi_manager_init();
    network_client_start();
}
