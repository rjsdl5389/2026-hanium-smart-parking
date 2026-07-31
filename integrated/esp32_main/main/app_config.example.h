#pragma once

#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define SERVER_IPV4 "192.168.0.10"
#define SERVER_PORT 5000

#define CAR_ID "CAR_01"
#define FIRMWARE_VERSION "0.5.3-logic-hardening"
#define PROTOCOL_VERSION 1

/* Inbound command lines from the notebook stay <= 512 bytes (protocol cap). */
#define MAX_NDJSON_LINE_LENGTH 512
#define TCP_STREAM_BUFFER_LENGTH 1024

/* Keep both inbound and outbound NDJSON messages inside the architecture's
 * current 512-byte cap. REMOTE_DIRECT STATUS is serialized compactly. */
#define MAX_TX_LINE_LENGTH 512

#define HELLO_RETRY_MS 500
#define TCP_RECONNECT_DELAY_MS 1000
#define HEARTBEAT_TIMEOUT_MS 1000
#define STATUS_PERIOD_MS 200

/* REMOTE_DIRECT streaming safety: stop if no fresh DIRECT_CONTROL for this long. */
#define DIRECT_CONTROL_TIMEOUT_MS 500

#define TX_HIGH_QUEUE_LENGTH 12
#define COMMAND_QUEUE_LENGTH 12

/*
 * 0 = mock actuator (no GPIO output; computed PWM/dir/servo are logged only).
 * 1 = real motor + servo output. Bench-test with wheels off the ground first,
 *     forward and reverse with wheels off the ground before floor testing.
 */
#define ENABLE_ACTUATOR_OUTPUT 0
#define DAY3_ALLOW_GO_WITHOUT_POSE 1

#define MAX_ROUTE_ID 1000000
#define MAX_WAYPOINT_ID 1000000
#define MAX_COORDINATE_CM 500.0
#define MAX_SPEED_CM_S 100.0
#define MAX_POSITION_TOLERANCE_CM 100.0
#define MAX_HEADING_TOLERANCE_DEG 180.0

/* -------------------------------------------------------------------------
 * Actuator hardware pins (DO NOT change; strapping pins must not be reused).
 * ------------------------------------------------------------------------- */
#define MOTOR_PWM_GPIO 25
#define MOTOR_DIR_GPIO 26
#define SERVO_PWM_GPIO 27
#define ENCODER_A_GPIO 34
#define ENCODER_B_GPIO 35

/* Change to -1 after the first real forward-drive test if the raw count sign is opposite. */
#define ENCODER_DIRECTION_SIGN -1

/* -------------------------------------------------------------------------
 * Motor mapping calibrated on 2026-07-29 (20 kHz, 8-bit PWM, duty 0..255).
 * A normalized throttle magnitude of 1.0 means the current integration-test
 * profile's DEFAULT duty, not unrestricted full hardware output.
 * ------------------------------------------------------------------------- */
#define MOTOR_PWM_FREQ_HZ 20000
#define MOTOR_PWM_RES_BITS 8           /* LEDC_TIMER_8_BIT -> duty 0..255 */
#define MOTOR_PWM_MAX_DUTY 255
#define MOTOR_DEADBAND_THROTTLE 0.02
#define MOTOR_ALLOW_REVERSE 1          /* v5: S-hold reverse enabled; bench-test first */
#define MOTOR_FORWARD_DIR_LEVEL 1      /* verified: GPIO26 HIGH = forward */
#define MOTOR_REVERSE_DIR_LEVEL 0

#define PWM_FORWARD_MIN 15
#define PWM_FORWARD_DEFAULT 27
#define PWM_TURN_MIN 35
#define PWM_TURN_DEFAULT 45
#define PWM_STRONG_TURN_DEFAULT 55

/* Steering changes previously disturbed motor PWM when servo/motor PWM setup
 * overlapped. Keep independent LEDC timers, initialize servo first, and stop
 * the motor for one 50 Hz servo period when the target angle changes. */
#define STOP_MOTOR_DURING_STEER_UPDATE 0
#define STEER_UPDATE_SETTLE_MS 20
#define SERVO_BOOT_CENTER_DELAY_MS 500

/* -------------------------------------------------------------------------
 * Servo mapping calibrated on 2026-07-29.
 * Piecewise points: -1.0=50°, -0.5=68°, 0=86°, +0.5=104°, +1.0=122°.
 * 22° / 130° are mechanical-limit checks only and are not used in operation.
 * ------------------------------------------------------------------------- */
#define SERVO_PWM_FREQ_HZ 50
#define SERVO_PWM_RES_BITS 14          /* LEDC_TIMER_14_BIT -> 16384 counts/20ms */
#define SERVO_LEFT_STRONG_DEG 50.0
#define SERVO_LEFT_WEAK_DEG 68.0
#define SERVO_CENTER_DEG 86.0
#define SERVO_RIGHT_WEAK_DEG 104.0
#define SERVO_RIGHT_STRONG_DEG 122.0
#define SERVO_MIN_PULSE_US 500.0
#define SERVO_MAX_PULSE_US 2400.0
#define SERVO_FULL_SWEEP_DEG 180.0
