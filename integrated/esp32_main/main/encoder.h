#pragma once

#include <stdint.h>

/*
 * Quadrature encoder on GPIO34/GPIO35.
 * GPIO34/35 are input-only and have no internal pull-ups; the current hardware
 * was verified without level shifting. Add external pull-ups only if motor-noise
 * testing shows unstable edges.
 */

void encoder_init(void);
int64_t encoder_get_count(void);
void encoder_reset_count(void);
