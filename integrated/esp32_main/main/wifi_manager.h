#pragma once

#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

void wifi_manager_init(void);
EventBits_t wifi_manager_wait_connected(TickType_t timeout_ticks);
bool wifi_manager_is_connected(void);
