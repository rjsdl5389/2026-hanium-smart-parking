#include "wifi_manager.h"

#include <stdio.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"

#include "app_config.h"

#define WIFI_CONNECTED_BIT BIT0

static const char *TAG = "WIFI";
static EventGroupHandle_t s_wifi_event_group;

static void wifi_event_handler(void *arg, esp_event_base_t base,
                               int32_t event_id, void *event_data)
{
    (void)arg;
    if (base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        ESP_LOGI(TAG, "Wi-Fi station started");
        ESP_ERROR_CHECK(esp_wifi_connect());
        return;
    }

    if (base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        const wifi_event_sta_disconnected_t *disconnected =
            (const wifi_event_sta_disconnected_t *)event_data;
        xEventGroupClearBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
        ESP_LOGW(TAG, "Wi-Fi disconnected reason=%u rssi=%d; reconnecting",
                 disconnected ? (unsigned)disconnected->reason : 0U,
                 disconnected ? (int)disconnected->rssi : 0);
        (void)esp_wifi_connect();
        return;
    }

    if (base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        const ip_event_got_ip_t *got_ip = (const ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "IPv4 acquired: " IPSTR, IP2STR(&got_ip->ip_info.ip));
        wifi_ap_record_t ap = {0};
        wifi_bandwidth_t bandwidth = WIFI_BW20;
        if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
            (void)esp_wifi_get_bandwidth(WIFI_IF_STA, &bandwidth);
            ESP_LOGI(TAG, "AP channel=%u bandwidth=%s rssi=%d auth=%d",
                     (unsigned)ap.primary,
                     bandwidth == WIFI_BW20 ? "HT20" : "HT40",
                     (int)ap.rssi, (int)ap.authmode);
        }
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

void wifi_manager_init(void)
{
    s_wifi_event_group = xEventGroupCreate();
    configASSERT(s_wifi_event_group != NULL);

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_t *netif = esp_netif_create_default_wifi_sta();
    configASSERT(netif != NULL);

    const wifi_init_config_t init_config = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init_config));
    ESP_ERROR_CHECK(esp_event_handler_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event_handler, NULL));

    wifi_config_t config = {0};
    (void)snprintf((char *)config.sta.ssid, sizeof(config.sta.ssid), "%s", WIFI_SSID);
    (void)snprintf((char *)config.sta.password, sizeof(config.sta.password), "%s", WIFI_PASSWORD);
    config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &config));
    ESP_ERROR_CHECK(esp_wifi_start());
    /* The Windows mobile hotspot shares one physical radio with the laptop's
     * infrastructure uplink.  Keep the safety-control STA on 20 MHz so a
     * strong-RSSI link does not also occupy a 40 MHz-wide, interference-prone
     * 2.4 GHz channel.  This changes only RF bandwidth, not timeout policy. */
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_STA, WIFI_BW20));
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));

    ESP_LOGI(TAG, "Connecting to SSID: %s", WIFI_SSID);
}

EventBits_t wifi_manager_wait_connected(TickType_t timeout_ticks)
{
    return xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECTED_BIT,
                               pdFALSE, pdTRUE, timeout_ticks);
}

bool wifi_manager_is_connected(void)
{
    return (xEventGroupGetBits(s_wifi_event_group) & WIFI_CONNECTED_BIT) != 0;
}
