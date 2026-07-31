#pragma once

#include <stdbool.h>

void tx_manager_init(void);
void tx_manager_start(void);
void tx_manager_clear(void);
bool tx_manager_enqueue_high(const char *line);
bool tx_manager_overwrite_latest_status(const char *line);
