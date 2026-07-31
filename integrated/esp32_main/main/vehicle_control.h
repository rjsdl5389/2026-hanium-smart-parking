#pragma once

#include <stdbool.h>
#include <stddef.h>

#include "app_types.h"

void vehicle_control_init(void);
void vehicle_control_notify_tcp_connected(void);
void vehicle_control_notify_tcp_disconnected(void);
void vehicle_control_notify_comm_timeout(void);
void vehicle_control_submit_message(const protocol_message_t *message);
void vehicle_control_get_snapshot(vehicle_snapshot_t *snapshot);
bool vehicle_control_session_matches(const char *session_id);
bool vehicle_control_is_session_active(void);
void vehicle_control_build_hello(char *buffer, size_t buffer_size);
