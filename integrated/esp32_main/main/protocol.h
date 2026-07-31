#pragma once

#include <stdbool.h>
#include <stddef.h>
#include "app_types.h"

int protocol_parse_line(const char *line, protocol_message_t *out, char *error, size_t error_size);
bool protocol_is_reliable_command(protocol_message_type_t type);
