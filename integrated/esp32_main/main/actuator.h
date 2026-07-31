#pragma once

#include <stdbool.h>

#include "app_types.h"

/*
 * Actuator module: the ONLY owner of motor + servo output.
 * Only VehicleControlTask may call these functions.
 *
 * Two compile-time modes (app_config.h ENABLE_ACTUATOR_OUTPUT):
 *   0 = mock: computes PWM/direction/servo angle and logs them, no GPIO output.
 *   1 = real: drives MOTOR_PWM_GPIO / MOTOR_DIR_GPIO / SERVO_PWM_GPIO via LEDC.
 *
 * In both modes actuator_apply_direct() returns the computed values so STATUS
 * can report exactly what would be / is being driven.
 */

typedef struct {
    int motor_pwm;                    /* duty 0..MOTOR_PWM_MAX_DUTY */
    motion_direction_t motor_direction;
    double servo_angle_deg;
    double applied_throttle;          /* post-clamp/deadband throttle actually used */
    double applied_steering;          /* post-clamp steering actually used */
} actuator_output_t;

void actuator_init(void);

/* Motor to 0 and servo to safe center. Single stop path for all safeStop reasons. */
void actuator_safe_stop(const char *reason);

/* Legacy WAYPOINT_AUTO hook: marks the start of autonomous motion. */
void actuator_start_motion(void);

/* REMOTE_DIRECT: map normalized throttle/steering to motor + servo output. */
void actuator_apply_direct(double throttle, double steering, actuator_output_t *out);

/* true if real GPIO output is compiled in (ENABLE_ACTUATOR_OUTPUT=1). */
bool actuator_output_enabled(void);
