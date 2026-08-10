#include "vehicle_control.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "esp_log.h"
#include "esp_random.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#include "actuator.h"
#include "encoder.h"
#include "app_config.h"
#include "tx_manager.h"

#define NOTIFY_STOP          BIT0
#define NOTIFY_WAIT          BIT1
#define NOTIFY_COMM_TIMEOUT  BIT2
#define NOTIFY_TCP_CONNECTED BIT3
#define NOTIFY_TCP_DOWN      BIT4
#define NOTIFY_DIRECT        BIT5

static const char *TAG = "VEHICLE";

static TaskHandle_t s_vehicle_task;
static QueueHandle_t s_command_queue;
static SemaphoreHandle_t s_context_mutex;

static portMUX_TYPE s_safety_slot_lock = portMUX_INITIALIZER_UNLOCKED;
static protocol_message_t s_stop_slot;
static protocol_message_t s_wait_slot;
static bool s_stop_slot_valid;
static bool s_wait_slot_valid;

/* Latest-value DIRECT_CONTROL slot (never queued; newest wins). */
static portMUX_TYPE s_direct_slot_lock = portMUX_INITIALIZER_UNLOCKED;
typedef struct {
    uint32_t control_seq;
    double throttle;
    double steering;
    char session_id[48];
    bool valid;
} direct_control_slot_t;
static direct_control_slot_t s_direct_slot;

typedef struct {
    vehicle_snapshot_t snapshot;
    vehicle_state_t pre_sync_state;
    bool last_command_valid;
    uint64_t last_command_fingerprint;
    command_result_t last_command_result;
    /* REMOTE_DIRECT streaming state. */
    uint32_t applied_control_seq;
    TickType_t last_direct_apply_tick;
    bool direct_active;
} vehicle_context_t;

static vehicle_context_t s_context;

static void copy_text(char *dst, size_t size, const char *src)
{
    if (dst && size) (void)snprintf(dst, size, "%s", src ? src : "");
}

static void clear_target_locked(void)
{
    memset(&s_context.snapshot.target, 0, sizeof(s_context.snapshot.target));
    s_context.snapshot.target.route_id = -1;
    s_context.snapshot.target.waypoint_id = -1;
    s_context.snapshot.target.phase = DRIVE_PHASE_NONE;
    s_context.snapshot.target_loaded = false;
    s_context.snapshot.resume_allowed = false;
    s_context.snapshot.wait_reason = WAIT_REASON_NONE;
}

static void clear_direct_slot(void)
{
    taskENTER_CRITICAL(&s_direct_slot_lock);
    s_direct_slot.valid = false;
    taskEXIT_CRITICAL(&s_direct_slot_lock);
}

/* Drop any pending/held DIRECT_CONTROL and zero the reported outputs. Keeps
 * applied_control_seq so a stale replay cannot restart motion; only a strictly
 * larger control_seq (new operator input) may drive again. */
static void invalidate_direct_locked(void)
{
    clear_direct_slot();
    s_context.direct_active = false;
    s_context.last_direct_apply_tick = 0;
    s_context.snapshot.applied_throttle = 0.0;
    s_context.snapshot.applied_steering = 0.0;
    s_context.snapshot.motor_pwm = 0;
    s_context.snapshot.motor_direction = MOTION_DIRECTION_FORWARD;
    s_context.snapshot.servo_angle_deg = SERVO_CENTER_DEG;
}

static void set_state_locked(vehicle_state_t next_state)
{
    if (s_context.snapshot.state == next_state) return;
    ESP_LOGI(TAG, "State: %s -> %s",
             vehicle_state_to_string(s_context.snapshot.state),
             vehicle_state_to_string(next_state));
    s_context.snapshot.previous_state = s_context.snapshot.state;
    s_context.snapshot.state = next_state;
}

static bool session_matches_locked(const char *session_id)
{
    return s_context.snapshot.session_active && session_id &&
           strcmp(s_context.snapshot.session_id, session_id) == 0;
}

static void queue_status_locked(command_result_t result, uint32_t rejected_seq,
                                bool duplicate, bool high_priority)
{
    (void)duplicate; /* duplicate execution is already prevented; no wire field needed */
    char line[MAX_TX_LINE_LENGTH + 1];
    s_context.snapshot.status_seq++;
    s_context.snapshot.encoder_count = encoder_get_count();

    int written;
    if (s_context.snapshot.mode == CONTROL_MODE_REMOTE_DIRECT) {
        /* Keep the REMOTE_DIRECT STATUS within the architecture's 512-byte
         * message cap. Hardware-mapping details (PWM/servo angle) remain in the
         * ESP32 serial log; the wire STATUS carries the normalized applied input. */
        written = snprintf(
            line, sizeof(line),
            "{"
            "\"version\":%d,"
            "\"type\":\"STATUS\","
            "\"car_id\":\"%s\","
            "\"boot_id\":\"%s\","
            "\"session_id\":\"%s\","
            "\"status_seq\":%" PRIu32 ","
            "\"last_processed_cmd_seq\":%" PRIu32 ","
            "\"rejected_seq\":%" PRIu32 ","
            "\"command_result\":\"%s\","
            "\"state\":\"%s\","
            "\"mode\":\"%s\","
            "\"target_loaded\":%s,"
            "\"resume_allowed\":%s,"
            "\"wait_reason\":\"%s\","
            "\"error_code\":\"%s\","
            "\"latest_control_seq\":%" PRIu32 ","
            "\"applied_throttle\":%.3f,"
            "\"applied_steering\":%.3f,"
            "\"encoder_count\":%" PRId64
            "}",
            PROTOCOL_VERSION,
            CAR_ID,
            s_context.snapshot.boot_id,
            s_context.snapshot.session_id,
            s_context.snapshot.status_seq,
            s_context.snapshot.last_processed_cmd_seq,
            rejected_seq,
            command_result_to_string(result),
            vehicle_state_to_string(s_context.snapshot.state),
            control_mode_to_string(s_context.snapshot.mode),
            s_context.snapshot.target_loaded ? "true" : "false",
            s_context.snapshot.resume_allowed ? "true" : "false",
            wait_reason_to_string(s_context.snapshot.wait_reason),
            s_context.snapshot.error_code,
            s_context.snapshot.latest_control_seq,
            s_context.snapshot.applied_throttle,
            s_context.snapshot.applied_steering,
            s_context.snapshot.encoder_count);
    } else {
        written = snprintf(
            line, sizeof(line),
            "{"
            "\"version\":%d,"
            "\"type\":\"STATUS\","
            "\"car_id\":\"%s\","
            "\"boot_id\":\"%s\","
            "\"session_id\":\"%s\","
            "\"status_seq\":%" PRIu32 ","
            "\"last_processed_cmd_seq\":%" PRIu32 ","
            "\"rejected_seq\":%" PRIu32 ","
            "\"command_result\":\"%s\","
            "\"state\":\"%s\","
            "\"mode\":\"%s\","
            "\"route_id\":%d,"
            "\"waypoint_id\":%d,"
            "\"phase\":\"%s\","
            "\"target_loaded\":%s,"
            "\"resume_allowed\":%s,"
            "\"wait_reason\":\"%s\","
            "\"error_code\":\"%s\""
            "}",
            PROTOCOL_VERSION,
            CAR_ID,
            s_context.snapshot.boot_id,
            s_context.snapshot.session_id,
            s_context.snapshot.status_seq,
            s_context.snapshot.last_processed_cmd_seq,
            rejected_seq,
            command_result_to_string(result),
            vehicle_state_to_string(s_context.snapshot.state),
            control_mode_to_string(s_context.snapshot.mode),
            s_context.snapshot.target_loaded ? s_context.snapshot.target.route_id : -1,
            s_context.snapshot.target_loaded ? s_context.snapshot.target.waypoint_id : -1,
            drive_phase_to_string(s_context.snapshot.target.phase),
            s_context.snapshot.target_loaded ? "true" : "false",
            s_context.snapshot.resume_allowed ? "true" : "false",
            wait_reason_to_string(s_context.snapshot.wait_reason),
            s_context.snapshot.error_code);
    }

    if (written < 0 || (size_t)written >= sizeof(line)) {
        ESP_LOGE(TAG, "STATUS serialization exceeded %u-byte protocol cap",
                 (unsigned)MAX_TX_LINE_LENGTH);
        return;
    }

    if (high_priority) (void)tx_manager_enqueue_high(line);
    else (void)tx_manager_overwrite_latest_status(line);
}

static bool begin_reliable_locked(const protocol_message_t *message)
{
    if (!session_matches_locked(message->session_id)) {
        queue_status_locked(COMMAND_RESULT_SESSION_MISMATCH,
                            message->seq, false, true);
        return false;
    }

    if (message->seq == s_context.snapshot.last_processed_cmd_seq) {
        if (s_context.last_command_valid &&
            message->logical_fingerprint == s_context.last_command_fingerprint) {
            ESP_LOGW(TAG, "Duplicate command %s seq=%" PRIu32,
                     protocol_message_type_to_string(message->type), message->seq);
            queue_status_locked(s_context.last_command_result, 0, true, true);
        } else {
            ESP_LOGE(TAG, "SEQ_CONFLICT seq=%" PRIu32, message->seq);
            queue_status_locked(COMMAND_RESULT_SEQ_CONFLICT,
                                message->seq, false, true);
        }
        return false;
    }

    if (message->seq < s_context.snapshot.last_processed_cmd_seq) {
        queue_status_locked(COMMAND_RESULT_STALE_SEQ,
                            message->seq, false, true);
        return false;
    }

    return true;
}

static void finish_reliable_locked(const protocol_message_t *message,
                                   command_result_t result)
{
    s_context.snapshot.last_processed_cmd_seq = message->seq;
    s_context.last_command_valid = true;
    s_context.last_command_fingerprint = message->logical_fingerprint;
    s_context.last_command_result = result;
    queue_status_locked(result, 0, false, true);
}

static void handle_tcp_connected_locked(void)
{
    actuator_safe_stop("TCP_CONNECTED_SYNCING");
    copy_text(s_context.snapshot.previous_session_id,
              sizeof(s_context.snapshot.previous_session_id),
              s_context.snapshot.session_id);
    s_context.pre_sync_state = s_context.snapshot.state;
    s_context.snapshot.session_active = false;
    s_context.snapshot.sync_hold = false;
    s_context.snapshot.session_id[0] = '\0';
    /* A new TCP session never inherits a drive mode. Require an explicit
     * SET_MODE again before REMOTE_DIRECT can move. */
    s_context.snapshot.mode = CONTROL_MODE_WAYPOINT_AUTO;
    clear_target_locked();
    invalidate_direct_locked();
    s_context.applied_control_seq = 0;
    s_context.snapshot.latest_control_seq = 0;
    set_state_locked(VEHICLE_STATE_SYNCING);
}

static void handle_comm_timeout_locked(void)
{
    actuator_safe_stop("COMM_TIMEOUT");
    s_context.snapshot.comm_timeout_active = true;
    s_context.snapshot.session_active = false;
    clear_target_locked();
    invalidate_direct_locked();

    if (s_context.snapshot.state == VEHICLE_STATE_ERROR ||
        s_context.snapshot.state == VEHICLE_STATE_EMERGENCY_STOP) {
        /* Preserve the stronger locked state. */
    } else if (
        s_context.snapshot.state == VEHICLE_STATE_SYNCING &&
        (s_context.pre_sync_state == VEHICLE_STATE_ERROR ||
         s_context.pre_sync_state == VEHICLE_STATE_EMERGENCY_STOP)
    ) {
        set_state_locked(s_context.pre_sync_state);
    } else {
        set_state_locked(VEHICLE_STATE_COMM_TIMEOUT);
    }

    queue_status_locked(COMMAND_RESULT_NONE, 0, false, true);
}

static void handle_hello_ack_locked(const protocol_message_t *message)
{
    if (strcmp(message->boot_id, s_context.snapshot.boot_id) != 0) {
        copy_text(s_context.snapshot.error_code,
                  sizeof(s_context.snapshot.error_code),
                  "BOOT_ID_MISMATCH");
        set_state_locked(VEHICLE_STATE_ERROR);
        queue_status_locked(COMMAND_RESULT_PROTOCOL_ERROR, 0, false, true);
        return;
    }

    if (s_context.snapshot.state != VEHICLE_STATE_SYNCING) {
        queue_status_locked(COMMAND_RESULT_INVALID_STATE, 0, false, true);
        return;
    }

    if (message->hello_result == HELLO_RESULT_READY_ALLOWED) {
        if (s_context.pre_sync_state == VEHICLE_STATE_ERROR ||
            s_context.pre_sync_state == VEHICLE_STATE_EMERGENCY_STOP) {
            queue_status_locked(COMMAND_RESULT_LOCKED_STATE, 0, false, true);
            return;
        }

        copy_text(s_context.snapshot.session_id,
                  sizeof(s_context.snapshot.session_id),
                  message->session_id);
        s_context.snapshot.session_active = true;
        s_context.snapshot.sync_hold = false;
        s_context.snapshot.comm_timeout_active = false;
        s_context.snapshot.last_processed_cmd_seq =
            message->command_seq_start > 0 ? message->command_seq_start - 1 : 0;
        s_context.last_command_valid = false;
        s_context.last_command_fingerprint = 0;
        s_context.last_command_result = COMMAND_RESULT_NONE;
        s_context.snapshot.mode = CONTROL_MODE_WAYPOINT_AUTO;
        clear_target_locked();
        invalidate_direct_locked();
        s_context.applied_control_seq = 0;
        s_context.snapshot.latest_control_seq = 0;
        s_context.snapshot.error_code[0] = '\0';
        set_state_locked(VEHICLE_STATE_READY);
        queue_status_locked(COMMAND_RESULT_ACCEPTED, 0, false, true);
        return;
    }

    if (message->hello_result == HELLO_RESULT_HOLD) {
        copy_text(s_context.snapshot.session_id,
                  sizeof(s_context.snapshot.session_id),
                  message->session_id);
        s_context.snapshot.session_active = true;
        s_context.snapshot.sync_hold = true;
        s_context.snapshot.last_processed_cmd_seq =
            message->command_seq_start > 0 ? message->command_seq_start - 1 : 0;
        queue_status_locked(COMMAND_RESULT_HOLD, 0, false, true);
        return;
    }

    copy_text(s_context.snapshot.error_code,
              sizeof(s_context.snapshot.error_code),
              message->reject_reason[0] ? message->reject_reason : "HELLO_REJECTED");
    s_context.snapshot.session_active = false;
    set_state_locked(VEHICLE_STATE_ERROR);
    queue_status_locked(COMMAND_RESULT_REJECTED, 0, false, true);
}

static bool route_acceptable_locked(const waypoint_target_t *target,
                                    command_result_t *failure)
{
    if (!s_context.snapshot.target_loaded) return true;

    const waypoint_target_t *current = &s_context.snapshot.target;
    if (target->route_id < current->route_id) {
        *failure = COMMAND_RESULT_STALE_ROUTE;
        return false;
    }

    if ((s_context.snapshot.wait_reason == WAIT_REASON_REROUTING ||
         s_context.snapshot.wait_reason == WAIT_REASON_FINAL_WAYPOINT_REACHED) &&
        target->route_id == current->route_id) {
        *failure = COMMAND_RESULT_NEW_ROUTE_REQUIRED;
        return false;
    }

    if (s_context.snapshot.wait_reason == WAIT_REASON_WAYPOINT_REACHED &&
        (target->route_id != current->route_id ||
         target->waypoint_id <= current->waypoint_id)) {
        *failure = COMMAND_RESULT_TARGET_MISMATCH;
        return false;
    }

    return true;
}

static void handle_waypoint_locked(const protocol_message_t *message)
{
    if (!begin_reliable_locked(message)) return;

    if (s_context.snapshot.mode != CONTROL_MODE_WAYPOINT_AUTO ||
        (s_context.snapshot.state != VEHICLE_STATE_READY &&
         s_context.snapshot.state != VEHICLE_STATE_WAITING)) {
        finish_reliable_locked(message, COMMAND_RESULT_INVALID_STATE);
        return;
    }

    command_result_t failure = COMMAND_RESULT_NONE;
    if (!route_acceptable_locked(&message->target, &failure)) {
        finish_reliable_locked(message, failure);
        return;
    }

    s_context.snapshot.target = message->target;
    s_context.snapshot.target_loaded = true;
    s_context.snapshot.resume_allowed = true;
    s_context.snapshot.wait_reason = WAIT_REASON_AWAITING_START;
    actuator_safe_stop("AWAITING_START");
    set_state_locked(VEHICLE_STATE_WAITING);
    finish_reliable_locked(message, COMMAND_RESULT_ACCEPTED);
}

static bool go_pose_gate_passes_locked(void)
{
#if DAY3_ALLOW_GO_WITHOUT_POSE
    ESP_LOGW(TAG, "DAY3 only: GO Pose gate bypassed");
    return true;
#else
    return s_context.snapshot.pose_valid;
#endif
}

static void handle_go_locked(const protocol_message_t *message)
{
    if (!begin_reliable_locked(message)) return;

    if (s_context.snapshot.state != VEHICLE_STATE_WAITING) {
        finish_reliable_locked(message, COMMAND_RESULT_INVALID_STATE);
        return;
    }
    if (!s_context.snapshot.target_loaded) {
        finish_reliable_locked(message, COMMAND_RESULT_TARGET_NOT_LOADED);
        return;
    }
    if (!s_context.snapshot.resume_allowed) {
        finish_reliable_locked(message, COMMAND_RESULT_INVALID_STATE);
        return;
    }
    if (message->route_id != s_context.snapshot.target.route_id ||
        message->waypoint_id != s_context.snapshot.target.waypoint_id) {
        finish_reliable_locked(message, COMMAND_RESULT_TARGET_MISMATCH);
        return;
    }
    if (!go_pose_gate_passes_locked()) {
        finish_reliable_locked(message, COMMAND_RESULT_POSE_REQUIRED);
        return;
    }

    s_context.snapshot.wait_reason = WAIT_REASON_NONE;
    set_state_locked(VEHICLE_STATE_MOVING);
    actuator_start_motion();
    finish_reliable_locked(message, COMMAND_RESULT_ACCEPTED);
}

static bool wait_requires_new_waypoint(wait_reason_t reason)
{
    return reason == WAIT_REASON_REROUTING ||
           reason == WAIT_REASON_WAYPOINT_REACHED ||
           reason == WAIT_REASON_FINAL_WAYPOINT_REACHED;
}

static void handle_wait_locked(const protocol_message_t *message)
{
    if (!begin_reliable_locked(message)) return;

    actuator_safe_stop(wait_reason_to_string(message->wait_reason));
    invalidate_direct_locked();

    if (s_context.snapshot.state == VEHICLE_STATE_MOVING ||
        s_context.snapshot.state == VEHICLE_STATE_WAITING) {
        if (
            wait_requires_new_waypoint(message->wait_reason) &&
            s_context.snapshot.target_loaded &&
            (message->route_id != s_context.snapshot.target.route_id ||
             message->waypoint_id != s_context.snapshot.target.waypoint_id)
        ) {
            /* Stop first, but do not apply stale route-completion semantics. */
            s_context.snapshot.wait_reason = WAIT_REASON_REMOTE_WAIT;
            s_context.snapshot.resume_allowed = false;
            set_state_locked(VEHICLE_STATE_WAITING);
            finish_reliable_locked(message, COMMAND_RESULT_TARGET_MISMATCH);
            return;
        }

        s_context.snapshot.wait_reason = message->wait_reason;
        if (wait_requires_new_waypoint(message->wait_reason)) {
            s_context.snapshot.resume_allowed = false;
        }
        set_state_locked(VEHICLE_STATE_WAITING);
        finish_reliable_locked(message, COMMAND_RESULT_ACCEPTED);
        return;
    }

    if (s_context.snapshot.state == VEHICLE_STATE_READY) {
        finish_reliable_locked(message, COMMAND_RESULT_ALREADY_STOPPED);
        return;
    }

    finish_reliable_locked(message, COMMAND_RESULT_INVALID_STATE);
}

static void handle_stop_locked(const protocol_message_t *message)
{
    actuator_safe_stop(message->reason[0] ? message->reason : "EMERGENCY");
    clear_target_locked();
    invalidate_direct_locked();
    set_state_locked(VEHICLE_STATE_EMERGENCY_STOP);

    if (!session_matches_locked(message->session_id)) {
        queue_status_locked(COMMAND_RESULT_SESSION_MISMATCH,
                            message->seq, false, true);
        return;
    }
    if (!begin_reliable_locked(message)) return;
    finish_reliable_locked(message, COMMAND_RESULT_ACCEPTED);
}

static void handle_reset_locked(const protocol_message_t *message)
{
    if (!begin_reliable_locked(message)) return;

    const bool hold_reset =
        s_context.snapshot.state == VEHICLE_STATE_SYNCING &&
        s_context.snapshot.sync_hold &&
        (s_context.pre_sync_state == VEHICLE_STATE_EMERGENCY_STOP ||
         s_context.pre_sync_state == VEHICLE_STATE_ERROR);

    if (!hold_reset &&
        s_context.snapshot.state != VEHICLE_STATE_EMERGENCY_STOP &&
        s_context.snapshot.state != VEHICLE_STATE_ERROR) {
        finish_reliable_locked(message, COMMAND_RESULT_INVALID_STATE);
        return;
    }

    actuator_safe_stop("RESET");
    s_context.snapshot.mode = CONTROL_MODE_WAYPOINT_AUTO;
    clear_target_locked();
    invalidate_direct_locked();
    s_context.applied_control_seq = 0;
    s_context.snapshot.latest_control_seq = 0;
    s_context.snapshot.comm_timeout_active = false;
    s_context.snapshot.error_code[0] = '\0';

    if (hold_reset) {
        /*
         * HOLD recovery requires a fresh HELLO/HELLO_ACK decision.
         * Do not jump directly to READY.
         */
        finish_reliable_locked(message, COMMAND_RESULT_ACCEPTED);
        copy_text(s_context.snapshot.previous_session_id,
                  sizeof(s_context.snapshot.previous_session_id),
                  s_context.snapshot.session_id);
        s_context.snapshot.session_id[0] = '\0';
        s_context.snapshot.session_active = false;
        s_context.snapshot.sync_hold = false;
        s_context.pre_sync_state = VEHICLE_STATE_READY;
        s_context.snapshot.previous_state = VEHICLE_STATE_READY;
        return;
    }

    set_state_locked(VEHICLE_STATE_READY);
    finish_reliable_locked(message, COMMAND_RESULT_ACCEPTED);
}

static void handle_set_mode_locked(const protocol_message_t *message)
{
    if (!begin_reliable_locked(message)) return;

    /* Mode change only when READY and stopped. MOVING and locked states
     * (EMERGENCY_STOP/ERROR/COMM_TIMEOUT/WAITING) reject; SET_MODE alone must
     * never recover or start motion. */
    if (s_context.snapshot.state != VEHICLE_STATE_READY) {
        finish_reliable_locked(message, COMMAND_RESULT_INVALID_STATE);
        return;
    }

    s_context.snapshot.mode = message->mode;
    invalidate_direct_locked();
    if (message->mode == CONTROL_MODE_REMOTE_DIRECT) {
        /* Fresh control_seq baseline for the new REMOTE_DIRECT drive. */
        s_context.applied_control_seq = 0;
        s_context.snapshot.latest_control_seq = 0;
    }
    ESP_LOGI(TAG, "SET_MODE -> %s", control_mode_to_string(message->mode));
    finish_reliable_locked(message, COMMAND_RESULT_ACCEPTED);
}

/* Apply the latest DIRECT_CONTROL value (streaming, lowest priority). */
static void apply_direct_control_locked(const direct_control_slot_t *slot)
{
    if (!session_matches_locked(slot->session_id)) return;
    if (s_context.snapshot.mode != CONTROL_MODE_REMOTE_DIRECT) return;

    const vehicle_state_t st = s_context.snapshot.state;
    if (st == VEHICLE_STATE_ERROR || st == VEHICLE_STATE_EMERGENCY_STOP ||
        st == VEHICLE_STATE_COMM_TIMEOUT || st == VEHICLE_STATE_SYNCING ||
        st == VEHICLE_STATE_BOOT || st == VEHICLE_STATE_WIFI_CONNECTING) {
        return;  /* not synced / locked -> ignore direct control */
    }
    if (slot->control_seq <= s_context.applied_control_seq) {
        return;  /* stale or duplicate control_seq -> drop, no output change */
    }

    s_context.applied_control_seq = slot->control_seq;
    s_context.snapshot.latest_control_seq = slot->control_seq;

    actuator_output_t out;
    actuator_apply_direct(slot->throttle, slot->steering, &out);
    s_context.snapshot.applied_throttle = out.applied_throttle;
    s_context.snapshot.applied_steering = out.applied_steering;
    s_context.snapshot.motor_pwm = out.motor_pwm;
    s_context.snapshot.motor_direction = out.motor_direction;
    s_context.snapshot.servo_angle_deg = out.servo_angle_deg;
    s_context.last_direct_apply_tick = xTaskGetTickCount();
    s_context.direct_active = true;

    const vehicle_state_t prev = s_context.snapshot.state;
    s_context.snapshot.wait_reason = WAIT_REASON_NONE;
    if (out.motor_pwm > 0) {
        set_state_locked(VEHICLE_STATE_MOVING);           /* throttle != 0 -> drive */
    } else if (s_context.snapshot.state == VEHICLE_STATE_MOVING) {
        set_state_locked(VEHICLE_STATE_READY);            /* throttle 0 -> stop, steer only */
    }
    if (s_context.snapshot.state != prev) {
        queue_status_locked(COMMAND_RESULT_NONE, 0, false, true);
    }
}

/* safeStop if no fresh DIRECT_CONTROL within DIRECT_CONTROL_TIMEOUT_MS. */
static void check_direct_timeout_locked(void)
{
    if (s_context.snapshot.mode != CONTROL_MODE_REMOTE_DIRECT) return;
    if (s_context.snapshot.state != VEHICLE_STATE_MOVING) return;
    if (!s_context.direct_active || s_context.last_direct_apply_tick == 0) return;

    const TickType_t now = xTaskGetTickCount();
    if ((now - s_context.last_direct_apply_tick) <
        pdMS_TO_TICKS(DIRECT_CONTROL_TIMEOUT_MS)) {
        return;
    }

    ESP_LOGW(TAG, "DIRECT_CONTROL timeout -> safeStop WAITING");
    actuator_safe_stop("DIRECT_CONTROL_TIMEOUT");
    invalidate_direct_locked();
    s_context.snapshot.wait_reason = WAIT_REASON_DIRECT_CONTROL_TIMEOUT;
    s_context.snapshot.resume_allowed = false;
    set_state_locked(VEHICLE_STATE_WAITING);
    queue_status_locked(COMMAND_RESULT_NONE, 0, false, true);
}

static void process_general_locked(const protocol_message_t *message)
{
    switch (message->type) {
        case PROTOCOL_MSG_HELLO_ACK: handle_hello_ack_locked(message); break;
        case PROTOCOL_MSG_WAYPOINT: handle_waypoint_locked(message); break;
        case PROTOCOL_MSG_GO: handle_go_locked(message); break;
        case PROTOCOL_MSG_RESET: handle_reset_locked(message); break;
        case PROTOCOL_MSG_SET_MODE: handle_set_mode_locked(message); break;
        default:
            ESP_LOGW(TAG, "Unsupported general message: %s",
                     protocol_message_type_to_string(message->type));
            break;
    }
}

static void vehicle_control_task(void *argument)
{
    (void)argument;
    TickType_t last_periodic_status = xTaskGetTickCount();

    xSemaphoreTake(s_context_mutex, portMAX_DELAY);
    actuator_safe_stop("BOOT");
    set_state_locked(VEHICLE_STATE_WIFI_CONNECTING);
    xSemaphoreGive(s_context_mutex);

    while (true) {
        uint32_t bits = 0;
        (void)xTaskNotifyWait(0, UINT32_MAX, &bits, pdMS_TO_TICKS(50));

        if (bits & NOTIFY_STOP) {
            protocol_message_t message;
            bool valid;
            taskENTER_CRITICAL(&s_safety_slot_lock);
            valid = s_stop_slot_valid;
            message = s_stop_slot;
            s_stop_slot_valid = false;
            taskEXIT_CRITICAL(&s_safety_slot_lock);
            if (valid) {
                xSemaphoreTake(s_context_mutex, portMAX_DELAY);
                handle_stop_locked(&message);
                xSemaphoreGive(s_context_mutex);
            }
        }

        if (bits & NOTIFY_COMM_TIMEOUT) {
            xSemaphoreTake(s_context_mutex, portMAX_DELAY);
            handle_comm_timeout_locked();
            xSemaphoreGive(s_context_mutex);
        }

        if (bits & NOTIFY_TCP_DOWN) {
            xSemaphoreTake(s_context_mutex, portMAX_DELAY);
            handle_comm_timeout_locked();
            xSemaphoreGive(s_context_mutex);
        }

        if (bits & NOTIFY_TCP_CONNECTED) {
            xSemaphoreTake(s_context_mutex, portMAX_DELAY);
            handle_tcp_connected_locked();
            xSemaphoreGive(s_context_mutex);
        }

        if ((bits & NOTIFY_WAIT) && !(bits & NOTIFY_STOP)) {
            protocol_message_t message;
            bool valid;
            taskENTER_CRITICAL(&s_safety_slot_lock);
            valid = s_wait_slot_valid;
            message = s_wait_slot;
            s_wait_slot_valid = false;
            taskEXIT_CRITICAL(&s_safety_slot_lock);
            if (valid) {
                xSemaphoreTake(s_context_mutex, portMAX_DELAY);
                handle_wait_locked(&message);
                xSemaphoreGive(s_context_mutex);
            }
        }

        for (int i = 0; i < 4; ++i) {
            protocol_message_t message;
            if (xQueueReceive(s_command_queue, &message, 0) != pdTRUE) break;
            xSemaphoreTake(s_context_mutex, portMAX_DELAY);
            process_general_locked(&message);
            xSemaphoreGive(s_context_mutex);
        }

        /*
         * DIRECT_CONTROL is the lowest priority: applied only after STOP, WAIT,
         * comm events and general reliable commands have been handled above.
         */
        {
            direct_control_slot_t slot;
            bool have;
            taskENTER_CRITICAL(&s_direct_slot_lock);
            have = s_direct_slot.valid;
            slot = s_direct_slot;
            s_direct_slot.valid = false;
            taskEXIT_CRITICAL(&s_direct_slot_lock);
            if (have) {
                xSemaphoreTake(s_context_mutex, portMAX_DELAY);
                apply_direct_control_locked(&slot);
                xSemaphoreGive(s_context_mutex);
            }
        }

        xSemaphoreTake(s_context_mutex, portMAX_DELAY);
        check_direct_timeout_locked();
        xSemaphoreGive(s_context_mutex);

        const TickType_t now = xTaskGetTickCount();
        if (now - last_periodic_status >= pdMS_TO_TICKS(STATUS_PERIOD_MS)) {
            last_periodic_status = now;
            xSemaphoreTake(s_context_mutex, portMAX_DELAY);
            if (s_context.snapshot.session_active) {
                queue_status_locked(COMMAND_RESULT_NONE, 0, false, false);
            }
            xSemaphoreGive(s_context_mutex);
        }
    }
}

void vehicle_control_init(void)
{
    memset(&s_context, 0, sizeof(s_context));
    s_context.snapshot.state = VEHICLE_STATE_BOOT;
    s_context.snapshot.previous_state = VEHICLE_STATE_BOOT;
    s_context.snapshot.mode = CONTROL_MODE_WAYPOINT_AUTO;
    s_context.snapshot.target.route_id = -1;
    s_context.snapshot.target.waypoint_id = -1;
    s_context.snapshot.target.phase = DRIVE_PHASE_NONE;
    s_context.snapshot.motor_direction = MOTION_DIRECTION_FORWARD;
    s_context.snapshot.servo_angle_deg = SERVO_CENTER_DEG;
    s_context.snapshot.encoder_count = 0;

    (void)snprintf(s_context.snapshot.boot_id,
                   sizeof(s_context.snapshot.boot_id),
                   "B%08" PRIX32, esp_random());

    s_context_mutex = xSemaphoreCreateMutex();
    s_command_queue = xQueueCreate(COMMAND_QUEUE_LENGTH,
                                   sizeof(protocol_message_t));
    configASSERT(s_context_mutex != NULL);
    configASSERT(s_command_queue != NULL);

    const BaseType_t created = xTaskCreate(
        vehicle_control_task, "VehicleControlTask", 8192,
        NULL, 10, &s_vehicle_task);
    configASSERT(created == pdPASS);
    ESP_LOGI(TAG, "boot_id=%s", s_context.snapshot.boot_id);
}

void vehicle_control_notify_tcp_connected(void)
{
    if (s_vehicle_task) (void)xTaskNotify(s_vehicle_task,
                                         NOTIFY_TCP_CONNECTED, eSetBits);
}

void vehicle_control_notify_tcp_disconnected(void)
{
    if (s_vehicle_task) (void)xTaskNotify(s_vehicle_task,
                                         NOTIFY_TCP_DOWN, eSetBits);
}

void vehicle_control_notify_comm_timeout(void)
{
    if (s_vehicle_task) (void)xTaskNotify(s_vehicle_task,
                                         NOTIFY_COMM_TIMEOUT, eSetBits);
}

void vehicle_control_submit_message(const protocol_message_t *message)
{
    if (!message || !s_vehicle_task) return;

    if (message->type == PROTOCOL_MSG_STOP) {
        taskENTER_CRITICAL(&s_safety_slot_lock);
        s_stop_slot = *message;
        s_stop_slot_valid = true;
        taskEXIT_CRITICAL(&s_safety_slot_lock);
        (void)xTaskNotify(s_vehicle_task, NOTIFY_STOP, eSetBits);
        return;
    }

    if (message->type == PROTOCOL_MSG_WAIT) {
        taskENTER_CRITICAL(&s_safety_slot_lock);
        s_wait_slot = *message;
        s_wait_slot_valid = true;
        taskEXIT_CRITICAL(&s_safety_slot_lock);
        (void)xTaskNotify(s_vehicle_task, NOTIFY_WAIT, eSetBits);
        return;
    }

    if (message->type == PROTOCOL_MSG_DIRECT_CONTROL) {
        /* Streaming: keep only the newest value; never accumulate a queue. */
        direct_control_slot_t slot;
        slot.control_seq = message->control_seq;
        slot.throttle = message->throttle;
        slot.steering = message->steering;
        (void)snprintf(slot.session_id, sizeof(slot.session_id), "%s",
                       message->session_id);
        slot.valid = true;
        taskENTER_CRITICAL(&s_direct_slot_lock);
        s_direct_slot = slot;
        taskEXIT_CRITICAL(&s_direct_slot_lock);
        (void)xTaskNotify(s_vehicle_task, NOTIFY_DIRECT, eSetBits);
        return;
    }

    if (xQueueSend(s_command_queue, message, 0) != pdTRUE) {
        ESP_LOGE(TAG, "General command queue full: %s",
                 protocol_message_type_to_string(message->type));
    }
}

void vehicle_control_get_snapshot(vehicle_snapshot_t *snapshot)
{
    if (!snapshot) return;
    xSemaphoreTake(s_context_mutex, portMAX_DELAY);
    *snapshot = s_context.snapshot;
    xSemaphoreGive(s_context_mutex);
}

bool vehicle_control_session_matches(const char *session_id)
{
    bool matches;
    xSemaphoreTake(s_context_mutex, portMAX_DELAY);
    matches = session_matches_locked(session_id);
    xSemaphoreGive(s_context_mutex);
    return matches;
}

bool vehicle_control_is_session_active(void)
{
    bool active;
    xSemaphoreTake(s_context_mutex, portMAX_DELAY);
    active = s_context.snapshot.session_active;
    xSemaphoreGive(s_context_mutex);
    return active;
}

void vehicle_control_build_hello(char *buffer, size_t buffer_size)
{
    if (!buffer || !buffer_size) return;
    vehicle_snapshot_t snapshot;
    vehicle_control_get_snapshot(&snapshot);

    const int written = snprintf(
        buffer, buffer_size,
        "{"
        "\"version\":%d,"
        "\"type\":\"HELLO\","
        "\"car_id\":\"%s\","
        "\"boot_id\":\"%s\","
        "\"firmware_version\":\"%s\","
        "\"state\":\"SYNCING\","
        "\"previous_state\":\"%s\","
        "\"previous_session_id\":\"%s\","
        "\"last_processed_cmd_seq\":%" PRIu32 ","
        "\"current_route_id\":%d,"
        "\"current_waypoint_id\":%d,"
        "\"current_phase\":\"%s\","
        "\"target_loaded\":%s,"
        "\"resume_allowed\":%s,"
        "\"motor_stopped\":true,"
        "\"error_code\":\"%s\""
        "}",
        PROTOCOL_VERSION, CAR_ID, snapshot.boot_id, FIRMWARE_VERSION,
        vehicle_state_to_string(snapshot.previous_state),
        snapshot.previous_session_id,
        snapshot.last_processed_cmd_seq,
        snapshot.target_loaded ? snapshot.target.route_id : -1,
        snapshot.target_loaded ? snapshot.target.waypoint_id : -1,
        drive_phase_to_string(snapshot.target.phase),
        snapshot.target_loaded ? "true" : "false",
        snapshot.resume_allowed ? "true" : "false",
        snapshot.error_code);

    if (written < 0 || (size_t)written >= buffer_size) {
        ESP_LOGE(TAG, "HELLO serialization exceeded buffer");
        if (buffer_size > 0) buffer[0] = '\0';
    }
}
