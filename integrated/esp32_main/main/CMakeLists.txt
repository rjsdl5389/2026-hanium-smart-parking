idf_component_register(
    SRCS
        "app_main.c"
        "app_types.c"
        "actuator.c"
        "encoder.c"
        "network_client.c"
        "protocol.c"
        "socket_transport.c"
        "tx_manager.c"
        "vehicle_control.c"
        "wifi_manager.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES esp_event esp_netif esp_wifi esp_hw_support lwip nvs_flash
                  esp_driver_ledc esp_driver_gpio
)
