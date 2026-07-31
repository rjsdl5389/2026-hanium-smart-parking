#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Wire IDs are intentionally short in this project (B/S + 8 hex chars).
 * Keeping explicit storage caps here guarantees the compact REMOTE_DIRECT
 * STATUS remains below the architecture's 512-byte NDJSON ceiling even at
 * maximum numeric values and error text length. */
#define CAR_ID_BUFFER_SIZE 16
#define BOOT_ID_BUFFER_SIZE 12
#define SESSION_ID_BUFFER_SIZE 12
#define ERROR_CODE_BUFFER_SIZE 16

typedef enum {
    VEHICLE_STATE_BOOT = 0,
    VEHICLE_STATE_WIFI_CONNECTING,
    VEHICLE_STATE_SYNCING,
    VEHICLE_STATE_READY,
    VEHICLE_STATE_MOVING,
    VEHICLE_STATE_WAITING,
    VEHICLE_STATE_EMERGENCY_STOP,
    VEHICLE_STATE_COMM_TIMEOUT,
    VEHICLE_STATE_ERROR,
} vehicle_state_t;

typedef enum {
    CONTROL_MODE_MANUAL_SERIAL = 0,
    CONTROL_MODE_REMOTE_DIRECT,
    CONTROL_MODE_WAYPOINT_AUTO,
} control_mode_t;

typedef enum {
    DRIVE_PHASE_NONE = 0,
    DRIVE_PHASE_CRUISE,
    DRIVE_PHASE_APPROACH,
    DRIVE_PHASE_ALIGN,
    DRIVE_PHASE_ENTRY,
    DRIVE_PHASE_FINAL,
} drive_phase_t;

typedef enum {
    WAIT_REASON_NONE = 0,
    WAIT_REASON_AWAITING_START,
    WAIT_REASON_REMOTE_WAIT,
    WAIT_REASON_COLLISION_RISK,
    WAIT_REASON_OBSTACLE,
    WAIT_REASON_REROUTING,
    WAIT_REASON_WAYPOINT_REACHED,
    WAIT_REASON_FINAL_WAYPOINT_REACHED,
    WAIT_REASON_OPERATOR_REQUEST,
    WAIT_REASON_POSE_TIMEOUT,
    WAIT_REASON_DIRECT_CONTROL_TIMEOUT,
} wait_reason_t;

typedef enum {
    MOTION_DIRECTION_FORWARD = 0,
    MOTION_DIRECTION_REVERSE,
} motion_direction_t;

typedef enum {
    ARRIVAL_MODE_STOP = 0,
    ARRIVAL_MODE_PASS,
} arrival_mode_t;

typedef enum {
    PROTOCOL_MSG_INVALID = 0,
    PROTOCOL_MSG_HELLO_ACK,
    PROTOCOL_MSG_HEARTBEAT,
    PROTOCOL_MSG_WAYPOINT,
    PROTOCOL_MSG_WAIT,
    PROTOCOL_MSG_GO,
    PROTOCOL_MSG_STOP,
    PROTOCOL_MSG_RESET,
    PROTOCOL_MSG_SET_MODE,        /* REMOTE_DIRECT: reliable mode change */
    PROTOCOL_MSG_DIRECT_CONTROL,  /* REMOTE_DIRECT: streaming throttle/steering */
} protocol_message_type_t;

typedef enum {
    HELLO_RESULT_INVALID = 0,
    HELLO_RESULT_READY_ALLOWED,
    HELLO_RESULT_HOLD,
    HELLO_RESULT_REJECTED,
} hello_result_t;

typedef enum {
    COMMAND_RESULT_NONE = 0,
    COMMAND_RESULT_ACCEPTED,
    COMMAND_RESULT_ALREADY_STOPPED,
    COMMAND_RESULT_INVALID_STATE,
    COMMAND_RESULT_SESSION_MISMATCH,
    COMMAND_RESULT_SEQ_CONFLICT,
    COMMAND_RESULT_STALE_SEQ,
    COMMAND_RESULT_TARGET_MISMATCH,
    COMMAND_RESULT_TARGET_NOT_LOADED,
    COMMAND_RESULT_NEW_ROUTE_REQUIRED,
    COMMAND_RESULT_STALE_ROUTE,
    COMMAND_RESULT_POSE_REQUIRED,
    COMMAND_RESULT_LOCKED_STATE,
    COMMAND_RESULT_PROTOCOL_ERROR,
    COMMAND_RESULT_HOLD,
    COMMAND_RESULT_REJECTED,
} command_result_t;

typedef struct {
    int route_id;
    int waypoint_id;
    drive_phase_t phase;
    double x_cm;
    double y_cm;
    double target_heading_deg;
    motion_direction_t motion_direction;
    arrival_mode_t arrival_mode;
    double speed_cm_s;
    double position_tolerance_cm;
    double heading_tolerance_deg;
    bool heading_required;
    bool is_final;
} waypoint_target_t;

typedef struct {
    protocol_message_type_t type;
    uint32_t seq;
    uint64_t logical_fingerprint;
    uint32_t heartbeat_seq;
    uint32_t command_seq_start;
    hello_result_t hello_result;
    wait_reason_t wait_reason;
    int route_id;
    int waypoint_id;
    waypoint_target_t target;
    control_mode_t mode;      /* SET_MODE */
    uint32_t control_seq;     /* DIRECT_CONTROL streaming sequence */
    double throttle;          /* DIRECT_CONTROL, -1.0..1.0 */
    double steering;          /* DIRECT_CONTROL, -1.0..1.0 */
    char car_id[CAR_ID_BUFFER_SIZE];
    char boot_id[BOOT_ID_BUFFER_SIZE];
    char session_id[SESSION_ID_BUFFER_SIZE];
    char reason[48];
    char hold_reason[48];
    char reject_reason[48];
} protocol_message_t;

typedef struct {
    vehicle_state_t state;
    vehicle_state_t previous_state;
    control_mode_t mode;
    bool session_active;
    bool sync_hold;
    bool comm_timeout_active;
    bool target_loaded;
    bool resume_allowed;
    bool pose_valid;
    uint32_t status_seq;
    uint32_t last_processed_cmd_seq;
    wait_reason_t wait_reason;
    waypoint_target_t target;
    /* REMOTE_DIRECT applied-control reporting (streaming, not reliable seq). */
    uint32_t latest_control_seq;
    double applied_throttle;
    double applied_steering;
    int motor_pwm;
    motion_direction_t motor_direction;
    double servo_angle_deg;
    int64_t encoder_count;
    char boot_id[BOOT_ID_BUFFER_SIZE];
    char session_id[SESSION_ID_BUFFER_SIZE];
    char previous_session_id[SESSION_ID_BUFFER_SIZE];
    char error_code[ERROR_CODE_BUFFER_SIZE];
} vehicle_snapshot_t;

const char *vehicle_state_to_string(vehicle_state_t value);
const char *control_mode_to_string(control_mode_t value);
const char *drive_phase_to_string(drive_phase_t value);
const char *wait_reason_to_string(wait_reason_t value);
const char *motion_direction_to_string(motion_direction_t value);
const char *arrival_mode_to_string(arrival_mode_t value);
const char *protocol_message_type_to_string(protocol_message_type_t value);
const char *command_result_to_string(command_result_t value);
