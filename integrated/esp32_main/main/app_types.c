#include "app_types.h"

const char *vehicle_state_to_string(vehicle_state_t value)
{
    switch (value) {
        case VEHICLE_STATE_BOOT: return "BOOT";
        case VEHICLE_STATE_WIFI_CONNECTING: return "WIFI_CONNECTING";
        case VEHICLE_STATE_SYNCING: return "SYNCING";
        case VEHICLE_STATE_READY: return "READY";
        case VEHICLE_STATE_MOVING: return "MOVING";
        case VEHICLE_STATE_WAITING: return "WAITING";
        case VEHICLE_STATE_EMERGENCY_STOP: return "EMERGENCY_STOP";
        case VEHICLE_STATE_COMM_TIMEOUT: return "COMM_TIMEOUT";
        case VEHICLE_STATE_ERROR: return "ERROR";
        default: return "UNKNOWN";
    }
}

const char *control_mode_to_string(control_mode_t value)
{
    switch (value) {
        case CONTROL_MODE_MANUAL_SERIAL: return "MANUAL_SERIAL";
        case CONTROL_MODE_REMOTE_DIRECT: return "REMOTE_DIRECT";
        case CONTROL_MODE_WAYPOINT_AUTO: return "WAYPOINT_AUTO";
        default: return "UNKNOWN";
    }
}

const char *drive_phase_to_string(drive_phase_t value)
{
    switch (value) {
        case DRIVE_PHASE_NONE: return "NONE";
        case DRIVE_PHASE_CRUISE: return "CRUISE";
        case DRIVE_PHASE_APPROACH: return "APPROACH";
        case DRIVE_PHASE_ALIGN: return "ALIGN";
        case DRIVE_PHASE_ENTRY: return "ENTRY";
        case DRIVE_PHASE_FINAL: return "FINAL";
        default: return "UNKNOWN";
    }
}

const char *wait_reason_to_string(wait_reason_t value)
{
    switch (value) {
        case WAIT_REASON_NONE: return "NONE";
        case WAIT_REASON_AWAITING_START: return "AWAITING_START";
        case WAIT_REASON_REMOTE_WAIT: return "REMOTE_WAIT";
        case WAIT_REASON_COLLISION_RISK: return "COLLISION_RISK";
        case WAIT_REASON_OBSTACLE: return "OBSTACLE";
        case WAIT_REASON_REROUTING: return "REROUTING";
        case WAIT_REASON_WAYPOINT_REACHED: return "WAYPOINT_REACHED";
        case WAIT_REASON_FINAL_WAYPOINT_REACHED: return "FINAL_WAYPOINT_REACHED";
        case WAIT_REASON_OPERATOR_REQUEST: return "OPERATOR_REQUEST";
        case WAIT_REASON_POSE_TIMEOUT: return "POSE_TIMEOUT";
        case WAIT_REASON_DIRECT_CONTROL_TIMEOUT: return "DIRECT_CONTROL_TIMEOUT";
        default: return "UNKNOWN";
    }
}

const char *motion_direction_to_string(motion_direction_t value)
{
    return value == MOTION_DIRECTION_REVERSE ? "REVERSE" : "FORWARD";
}

const char *arrival_mode_to_string(arrival_mode_t value)
{
    return value == ARRIVAL_MODE_PASS ? "PASS" : "STOP";
}

const char *protocol_message_type_to_string(protocol_message_type_t value)
{
    switch (value) {
        case PROTOCOL_MSG_HELLO_ACK: return "HELLO_ACK";
        case PROTOCOL_MSG_HEARTBEAT: return "HEARTBEAT";
        case PROTOCOL_MSG_WAYPOINT: return "WAYPOINT";
        case PROTOCOL_MSG_WAIT: return "WAIT";
        case PROTOCOL_MSG_GO: return "GO";
        case PROTOCOL_MSG_STOP: return "STOP";
        case PROTOCOL_MSG_RESET: return "RESET";
        case PROTOCOL_MSG_SET_MODE: return "SET_MODE";
        case PROTOCOL_MSG_DIRECT_CONTROL: return "DIRECT_CONTROL";
        default: return "INVALID";
    }
}

const char *command_result_to_string(command_result_t value)
{
    switch (value) {
        case COMMAND_RESULT_NONE: return "NONE";
        case COMMAND_RESULT_ACCEPTED: return "ACCEPTED";
        case COMMAND_RESULT_ALREADY_STOPPED: return "ALREADY_STOPPED";
        case COMMAND_RESULT_INVALID_STATE: return "INVALID_STATE";
        case COMMAND_RESULT_SESSION_MISMATCH: return "SESSION_MISMATCH";
        case COMMAND_RESULT_SEQ_CONFLICT: return "SEQ_CONFLICT";
        case COMMAND_RESULT_STALE_SEQ: return "STALE_SEQ";
        case COMMAND_RESULT_TARGET_MISMATCH: return "TARGET_MISMATCH";
        case COMMAND_RESULT_TARGET_NOT_LOADED: return "TARGET_NOT_LOADED";
        case COMMAND_RESULT_NEW_ROUTE_REQUIRED: return "NEW_ROUTE_REQUIRED";
        case COMMAND_RESULT_STALE_ROUTE: return "STALE_ROUTE";
        case COMMAND_RESULT_POSE_REQUIRED: return "POSE_REQUIRED";
        case COMMAND_RESULT_LOCKED_STATE: return "LOCKED_STATE";
        case COMMAND_RESULT_PROTOCOL_ERROR: return "PROTOCOL_ERROR";
        case COMMAND_RESULT_HOLD: return "HOLD";
        case COMMAND_RESULT_REJECTED: return "REJECTED";
        default: return "UNKNOWN";
    }
}
