#pragma once

#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define SERVER_IPV4 "192.168.0.10"
#define SERVER_PORT 5000

#define CAR_ID "CAR_01"
#define FIRMWARE_VERSION "0.5.3-logic-hardening"
#define PROTOCOL_VERSION 1

#define MAX_NDJSON_LINE_LENGTH 512
#define TCP_STREAM_BUFFER_LENGTH 1024
#define MAX_TX_LINE_LENGTH 512

#define HELLO_RETRY_MS 500
#define TCP_RECONNECT_DELAY_MS 1000
#define HEARTBEAT_TIMEOUT_MS 1000
#define STATUS_PERIOD_MS 200
#define DIRECT_CONTROL_TIMEOUT_MS 500

#define TX_HIGH_QUEUE_LENGTH 12
#define COMMAND_QUEUE_LENGTH 12

/*
 * Safe public defaults.
 * 0 = no real motor/servo GPIO output.
 * Create local app_config.h and set to 1 only after wheels-off-ground checks.
 */
#define ENABLE_ACTUATOR_OUTPUT 0

/*
 * WAYPOINT parsing and target storage exist, but the actual Pose-based
 * waypoint control loop is not implemented yet. Keep this disabled.
 */
#define ENABLE_WAYPOINT_AUTO_CONTROL 0
#define DAY3_ALLOW_GO_WITHOUT_POSE 0

#define MAX_ROUTE_ID 1000000
#define MAX_WAYPOINT_ID 1000000
#define MAX_COORDINATE_CM 500.0
#define MAX_SPEED_CM_S 100.0
#define MAX_POSITION_TOLERANCE_CM 100.0
#define MAX_HEADING_TOLERANCE_DEG 180.0

#define MOTOR_PWM_GPIO 25
#define MOTOR_DIR_GPIO 26
#define SERVO_PWM_GPIO 27
#define ENCODER_A_GPIO 34
#define ENCODER_B_GPIO 35

#define ENCODER_DIRECTION_SIGN -1

#define MOTOR_PWM_FREQ_HZ 20000
#define MOTOR_PWM_RES_BITS 8
#define MOTOR_PWM_MAX_DUTY 255
#define MOTOR_DEADBAND_THROTTLE 0.02
#define MOTOR_ALLOW_REVERSE 1
#define MOTOR_FORWARD_DIR_LEVEL 1
#define MOTOR_REVERSE_DIR_LEVEL 0

#define PWM_FORWARD_MIN 12
#define PWM_FORWARD_DEFAULT 22
#define PWM_TURN_MIN 32
#define PWM_TURN_DEFAULT 40
/* Strong-turn?먯꽌??host throttle???댁븘 ?덈룄濡?理쒖냼/湲곕낯 PWM??遺꾨━. */
#define PWM_STRONG_TURN_MIN 38
#define PWM_STRONG_TURN_DEFAULT 50

/*
 * Servo and motor use independent LEDC timers.
 * The former 20 ms motor stop on every steering update is disabled because
 * it caused repeated ground-driving slowdown during ramped steering.
 */
#define STOP_MOTOR_DURING_STEER_UPDATE 0
#define STEER_UPDATE_SETTLE_MS 20
#define SERVO_BOOT_CENTER_DELAY_MS 500

#define SERVO_PWM_FREQ_HZ 50
#define SERVO_PWM_RES_BITS 14
#define SERVO_LEFT_STRONG_DEG 46.0
#define SERVO_LEFT_WEAK_DEG 66.0
#define SERVO_CENTER_DEG 86.0
#define SERVO_RIGHT_WEAK_DEG 106.0
#define SERVO_RIGHT_STRONG_DEG 126.0
#define SERVO_MIN_PULSE_US 500.0
#define SERVO_MAX_PULSE_US 2400.0
#define SERVO_FULL_SWEEP_DEG 180.0
