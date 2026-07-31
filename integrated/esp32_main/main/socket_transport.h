#pragma once

#include <stdbool.h>
#include <stdint.h>

void socket_transport_init(void);
void socket_transport_install(int socket_fd);
void socket_transport_clear_if_matches(int socket_fd);
void socket_transport_force_close(void);
bool socket_transport_is_connected(void);
uint32_t socket_transport_get_generation(void);
int socket_transport_send_line_if_current(const char *line, uint32_t generation);
