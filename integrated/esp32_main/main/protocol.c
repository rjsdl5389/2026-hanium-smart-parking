#include "protocol.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "app_config.h"

static void copy_text(char *dst, size_t size, const char *src)
{
    if (dst && size) {
        (void)snprintf(dst, size, "%s", src ? src : "");
    }
}

static void fail(char *error, size_t size, const char *text)
{
    copy_text(error, size, text);
}

static uint64_t fnv1a(const char *text)
{
    uint64_t hash = UINT64_C(14695981039346656037);
    while (text && *text) {
        hash ^= (uint8_t)*text++;
        hash *= UINT64_C(1099511628211);
    }
    return hash;
}

static bool req_string(const cJSON *root, const char *name, char *dst, size_t size,
                       char *error, size_t error_size)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(root, name);
    if (!cJSON_IsString(item) || !item->valuestring) {
        char msg[96];
        (void)snprintf(msg, sizeof(msg), "missing/invalid string: %s", name);
        fail(error, error_size, msg);
        return false;
    }
    if (strlen(item->valuestring) >= size) {
        char msg[96];
        (void)snprintf(msg, sizeof(msg), "string field too long: %s", name);
        fail(error, error_size, msg);
        return false;
    }
    copy_text(dst, size, item->valuestring);
    return true;
}

static bool opt_string(const cJSON *root, const char *name, char *dst, size_t size)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(root, name);
    if (!cJSON_IsString(item) || !item->valuestring ||
        strlen(item->valuestring) >= size) {
        if (dst && size) dst[0] = '\0';
        return false;
    }
    copy_text(dst, size, item->valuestring);
    return true;
}

static bool req_u32(const cJSON *root, const char *name, uint32_t *dst,
                    char *error, size_t error_size)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(root, name);
    if (!cJSON_IsNumber(item) || !isfinite(item->valuedouble) ||
        item->valuedouble < 0.0 || item->valuedouble > 4294967295.0 ||
        floor(item->valuedouble) != item->valuedouble) {
        char msg[96];
        (void)snprintf(msg, sizeof(msg), "missing/invalid uint32: %s", name);
        fail(error, error_size, msg);
        return false;
    }
    *dst = (uint32_t)item->valuedouble;
    return true;
}

static bool req_int(const cJSON *root, const char *name, int min, int max, int *dst,
                    char *error, size_t error_size)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(root, name);
    if (!cJSON_IsNumber(item) || !isfinite(item->valuedouble) ||
        item->valuedouble < min || item->valuedouble > max ||
        floor(item->valuedouble) != item->valuedouble) {
        char msg[96];
        (void)snprintf(msg, sizeof(msg), "missing/out-of-range integer: %s", name);
        fail(error, error_size, msg);
        return false;
    }
    *dst = item->valueint;
    return true;
}

static bool req_double(const cJSON *root, const char *name, double min, double max,
                       double *dst, char *error, size_t error_size)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(root, name);
    if (!cJSON_IsNumber(item) || !isfinite(item->valuedouble) ||
        item->valuedouble < min || item->valuedouble > max) {
        char msg[96];
        (void)snprintf(msg, sizeof(msg), "missing/out-of-range number: %s", name);
        fail(error, error_size, msg);
        return false;
    }
    *dst = item->valuedouble;
    return true;
}

static bool req_bool(const cJSON *root, const char *name, bool *dst,
                     char *error, size_t error_size)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(root, name);
    if (!cJSON_IsBool(item)) {
        char msg[96];
        (void)snprintf(msg, sizeof(msg), "missing/invalid bool: %s", name);
        fail(error, error_size, msg);
        return false;
    }
    *dst = cJSON_IsTrue(item);
    return true;
}

static protocol_message_type_t parse_type(const char *s)
{
    if (!s) return PROTOCOL_MSG_INVALID;
    if (!strcmp(s, "HELLO_ACK")) return PROTOCOL_MSG_HELLO_ACK;
    if (!strcmp(s, "HEARTBEAT")) return PROTOCOL_MSG_HEARTBEAT;
    if (!strcmp(s, "WAYPOINT")) return PROTOCOL_MSG_WAYPOINT;
    if (!strcmp(s, "WAIT")) return PROTOCOL_MSG_WAIT;
    if (!strcmp(s, "GO")) return PROTOCOL_MSG_GO;
    if (!strcmp(s, "STOP")) return PROTOCOL_MSG_STOP;
    if (!strcmp(s, "RESET")) return PROTOCOL_MSG_RESET;
    if (!strcmp(s, "SET_MODE")) return PROTOCOL_MSG_SET_MODE;
    if (!strcmp(s, "DIRECT_CONTROL")) return PROTOCOL_MSG_DIRECT_CONTROL;
    return PROTOCOL_MSG_INVALID;
}

/* Returns true and sets *out on a recognized mode string; false otherwise. */
static bool parse_mode(const char *s, control_mode_t *out)
{
    if (!s) return false;
    if (!strcmp(s, "MANUAL_SERIAL")) { *out = CONTROL_MODE_MANUAL_SERIAL; return true; }
    if (!strcmp(s, "REMOTE_DIRECT")) { *out = CONTROL_MODE_REMOTE_DIRECT; return true; }
    if (!strcmp(s, "WAYPOINT_AUTO")) { *out = CONTROL_MODE_WAYPOINT_AUTO; return true; }
    return false;
}

static drive_phase_t parse_phase(const char *s)
{
    if (!s) return DRIVE_PHASE_NONE;
    if (!strcmp(s, "CRUISE")) return DRIVE_PHASE_CRUISE;
    if (!strcmp(s, "APPROACH")) return DRIVE_PHASE_APPROACH;
    if (!strcmp(s, "ALIGN")) return DRIVE_PHASE_ALIGN;
    if (!strcmp(s, "ENTRY")) return DRIVE_PHASE_ENTRY;
    if (!strcmp(s, "FINAL")) return DRIVE_PHASE_FINAL;
    return DRIVE_PHASE_NONE;
}

static wait_reason_t parse_wait_reason(const char *s)
{
    if (!s) return WAIT_REASON_NONE;
    if (!strcmp(s, "REMOTE_WAIT")) return WAIT_REASON_REMOTE_WAIT;
    if (!strcmp(s, "COLLISION_RISK")) return WAIT_REASON_COLLISION_RISK;
    if (!strcmp(s, "OBSTACLE")) return WAIT_REASON_OBSTACLE;
    if (!strcmp(s, "REROUTING")) return WAIT_REASON_REROUTING;
    if (!strcmp(s, "WAYPOINT_REACHED")) return WAIT_REASON_WAYPOINT_REACHED;
    if (!strcmp(s, "FINAL_WAYPOINT_REACHED")) return WAIT_REASON_FINAL_WAYPOINT_REACHED;
    if (!strcmp(s, "OPERATOR_REQUEST")) return WAIT_REASON_OPERATOR_REQUEST;
    return WAIT_REASON_NONE;
}

static hello_result_t parse_hello_result(const char *s)
{
    if (!s) return HELLO_RESULT_INVALID;
    if (!strcmp(s, "READY_ALLOWED")) return HELLO_RESULT_READY_ALLOWED;
    if (!strcmp(s, "HOLD")) return HELLO_RESULT_HOLD;
    if (!strcmp(s, "REJECTED")) return HELLO_RESULT_REJECTED;
    return HELLO_RESULT_INVALID;
}

bool protocol_is_reliable_command(protocol_message_type_t type)
{
    return type == PROTOCOL_MSG_WAYPOINT || type == PROTOCOL_MSG_WAIT ||
           type == PROTOCOL_MSG_GO || type == PROTOCOL_MSG_STOP ||
           type == PROTOCOL_MSG_RESET || type == PROTOCOL_MSG_SET_MODE;
}

static uint64_t fingerprint(const protocol_message_t *m)
{
    char normalized[512];
    switch (m->type) {
        case PROTOCOL_MSG_WAYPOINT:
            (void)snprintf(normalized, sizeof(normalized),
                "WAYPOINT|%d|%d|%s|%.17g|%.17g|%.17g|%s|%s|%.17g|%.17g|%.17g|%d|%d",
                m->target.route_id, m->target.waypoint_id,
                drive_phase_to_string(m->target.phase),
                m->target.x_cm, m->target.y_cm, m->target.target_heading_deg,
                motion_direction_to_string(m->target.motion_direction),
                arrival_mode_to_string(m->target.arrival_mode),
                m->target.speed_cm_s, m->target.position_tolerance_cm,
                m->target.heading_tolerance_deg,
                m->target.heading_required ? 1 : 0,
                m->target.is_final ? 1 : 0);
            break;
        case PROTOCOL_MSG_WAIT:
            (void)snprintf(normalized, sizeof(normalized), "WAIT|%d|%d|%s",
                m->route_id, m->waypoint_id, wait_reason_to_string(m->wait_reason));
            break;
        case PROTOCOL_MSG_GO:
            (void)snprintf(normalized, sizeof(normalized), "GO|%d|%d",
                m->route_id, m->waypoint_id);
            break;
        case PROTOCOL_MSG_STOP:
            (void)snprintf(normalized, sizeof(normalized), "STOP|%s", m->reason);
            break;
        case PROTOCOL_MSG_RESET:
            (void)snprintf(normalized, sizeof(normalized), "RESET");
            break;
        case PROTOCOL_MSG_SET_MODE:
            (void)snprintf(normalized, sizeof(normalized), "SET_MODE|%s",
                control_mode_to_string(m->mode));
            break;
        default:
            normalized[0] = '\0';
            break;
    }
    return fnv1a(normalized);
}

int protocol_parse_line(const char *line, protocol_message_t *out, char *error, size_t error_size)
{
    if (!line || !out) {
        fail(error, error_size, "null protocol argument");
        return -1;
    }

    memset(out, 0, sizeof(*out));
    out->route_id = out->waypoint_id = -1;
    out->target.route_id = out->target.waypoint_id = -1;

    cJSON *root = cJSON_Parse(line);
    if (!root) {
        fail(error, error_size, "invalid JSON");
        return -1;
    }

    int rc = -1;
    const cJSON *version = cJSON_GetObjectItemCaseSensitive(root, "version");
    if (!cJSON_IsNumber(version) || version->valueint != PROTOCOL_VERSION) {
        fail(error, error_size, "unsupported/missing version");
        goto done;
    }

    char text[64];
    if (!req_string(root, "type", text, sizeof(text), error, error_size)) goto done;
    out->type = parse_type(text);
    if (out->type == PROTOCOL_MSG_INVALID) {
        fail(error, error_size, "unsupported message type");
        goto done;
    }

    if (!req_string(root, "car_id", out->car_id, sizeof(out->car_id), error, error_size)) goto done;
    if (strcmp(out->car_id, CAR_ID)) {
        fail(error, error_size, "car_id mismatch");
        goto done;
    }

    switch (out->type) {
        case PROTOCOL_MSG_HELLO_ACK:
            if (!req_string(root, "boot_id", out->boot_id, sizeof(out->boot_id), error, error_size)) goto done;
            if (!req_string(root, "result", text, sizeof(text), error, error_size)) goto done;
            out->hello_result = parse_hello_result(text);
            if (out->hello_result == HELLO_RESULT_INVALID) {
                fail(error, error_size, "unsupported HELLO_ACK result");
                goto done;
            }
            if (out->hello_result == HELLO_RESULT_REJECTED) {
                (void)opt_string(root, "reject_reason", out->reject_reason, sizeof(out->reject_reason));
                break;
            }
            if (!req_string(root, "session_id", out->session_id, sizeof(out->session_id), error, error_size)) goto done;
            if (!req_u32(root, "command_seq_start", &out->command_seq_start, error, error_size)) goto done;
            if (out->hello_result == HELLO_RESULT_HOLD) {
                (void)opt_string(root, "hold_reason", out->hold_reason, sizeof(out->hold_reason));
            }
            break;

        case PROTOCOL_MSG_HEARTBEAT:
            if (!req_string(root, "session_id", out->session_id, sizeof(out->session_id), error, error_size)) goto done;
            if (!req_u32(root, "heartbeat_seq", &out->heartbeat_seq, error, error_size)) goto done;
            break;

        case PROTOCOL_MSG_WAYPOINT: {
            char phase[24], motion[24], arrival[24];
            if (!req_string(root, "session_id", out->session_id, sizeof(out->session_id), error, error_size)) goto done;
            if (!req_u32(root, "seq", &out->seq, error, error_size)) goto done;
            if (!req_int(root, "route_id", 1, MAX_ROUTE_ID, &out->target.route_id, error, error_size)) goto done;
            if (!req_int(root, "waypoint_id", 1, MAX_WAYPOINT_ID, &out->target.waypoint_id, error, error_size)) goto done;
            if (!req_string(root, "phase", phase, sizeof(phase), error, error_size)) goto done;
            out->target.phase = parse_phase(phase);
            if (out->target.phase == DRIVE_PHASE_NONE) { fail(error, error_size, "unsupported phase"); goto done; }
            if (!req_double(root, "x_cm", 0.0, MAX_COORDINATE_CM, &out->target.x_cm, error, error_size)) goto done;
            if (!req_double(root, "y_cm", 0.0, MAX_COORDINATE_CM, &out->target.y_cm, error, error_size)) goto done;
            if (!req_double(root, "target_heading_deg", 0.0, 359.999, &out->target.target_heading_deg, error, error_size)) goto done;
            if (!req_string(root, "motion_direction", motion, sizeof(motion), error, error_size)) goto done;
            if (!strcmp(motion, "FORWARD")) out->target.motion_direction = MOTION_DIRECTION_FORWARD;
            else if (!strcmp(motion, "REVERSE")) out->target.motion_direction = MOTION_DIRECTION_REVERSE;
            else { fail(error, error_size, "unsupported motion_direction"); goto done; }
            if (!req_string(root, "arrival_mode", arrival, sizeof(arrival), error, error_size)) goto done;
            if (!strcmp(arrival, "STOP")) out->target.arrival_mode = ARRIVAL_MODE_STOP;
            else if (!strcmp(arrival, "PASS")) out->target.arrival_mode = ARRIVAL_MODE_PASS;
            else { fail(error, error_size, "unsupported arrival_mode"); goto done; }
            if (!req_double(root, "speed_cm_s", 0.01, MAX_SPEED_CM_S, &out->target.speed_cm_s, error, error_size)) goto done;
            if (!req_double(root, "position_tolerance_cm", 0.01, MAX_POSITION_TOLERANCE_CM, &out->target.position_tolerance_cm, error, error_size)) goto done;
            if (!req_double(root, "heading_tolerance_deg", 0.0, MAX_HEADING_TOLERANCE_DEG, &out->target.heading_tolerance_deg, error, error_size)) goto done;
            if (!req_bool(root, "heading_required", &out->target.heading_required, error, error_size)) goto done;
            if (!req_bool(root, "is_final", &out->target.is_final, error, error_size)) goto done;
            out->route_id = out->target.route_id;
            out->waypoint_id = out->target.waypoint_id;
            break;
        }

        case PROTOCOL_MSG_WAIT:
            if (!req_string(root, "session_id", out->session_id, sizeof(out->session_id), error, error_size)) goto done;
            if (!req_u32(root, "seq", &out->seq, error, error_size)) goto done;
            if (!req_int(root, "route_id", 0, MAX_ROUTE_ID, &out->route_id, error, error_size)) goto done;
            if (!req_int(root, "waypoint_id", 0, MAX_WAYPOINT_ID, &out->waypoint_id, error, error_size)) goto done;
            if (!req_string(root, "reason", text, sizeof(text), error, error_size)) goto done;
            out->wait_reason = parse_wait_reason(text);
            if (out->wait_reason == WAIT_REASON_NONE) { fail(error, error_size, "unsupported WAIT reason"); goto done; }
            break;

        case PROTOCOL_MSG_GO:
            if (!req_string(root, "session_id", out->session_id, sizeof(out->session_id), error, error_size)) goto done;
            if (!req_u32(root, "seq", &out->seq, error, error_size)) goto done;
            if (!req_int(root, "route_id", 1, MAX_ROUTE_ID, &out->route_id, error, error_size)) goto done;
            if (!req_int(root, "waypoint_id", 1, MAX_WAYPOINT_ID, &out->waypoint_id, error, error_size)) goto done;
            break;

        case PROTOCOL_MSG_STOP:
            if (!req_string(root, "session_id", out->session_id, sizeof(out->session_id), error, error_size)) goto done;
            if (!req_u32(root, "seq", &out->seq, error, error_size)) goto done;
            if (!opt_string(root, "reason", out->reason, sizeof(out->reason))) copy_text(out->reason, sizeof(out->reason), "EMERGENCY");
            break;

        case PROTOCOL_MSG_RESET:
            if (!req_string(root, "session_id", out->session_id, sizeof(out->session_id), error, error_size)) goto done;
            if (!req_u32(root, "seq", &out->seq, error, error_size)) goto done;
            break;

        case PROTOCOL_MSG_SET_MODE:
            if (!req_string(root, "session_id", out->session_id, sizeof(out->session_id), error, error_size)) goto done;
            if (!req_u32(root, "seq", &out->seq, error, error_size)) goto done;
            if (!req_string(root, "mode", text, sizeof(text), error, error_size)) goto done;
            if (!parse_mode(text, &out->mode)) { fail(error, error_size, "unsupported mode"); goto done; }
            break;

        case PROTOCOL_MSG_DIRECT_CONTROL:
            /* Streaming message: uses control_seq, NOT the reliable seq. */
            if (!req_string(root, "session_id", out->session_id, sizeof(out->session_id), error, error_size)) goto done;
            if (!req_u32(root, "control_seq", &out->control_seq, error, error_size)) goto done;
            /* req_double rejects NaN/infinity via isfinite(). */
            if (!req_double(root, "throttle", -1.0, 1.0, &out->throttle, error, error_size)) goto done;
            if (!req_double(root, "steering", -1.0, 1.0, &out->steering, error, error_size)) goto done;
            break;

        default:
            fail(error, error_size, "internal dispatch error");
            goto done;
    }

    if (protocol_is_reliable_command(out->type)) {
        if (out->seq == 0) {
            fail(error, error_size, "reliable command seq must be >= 1");
            goto done;
        }
        out->logical_fingerprint = fingerprint(out);
    }
    rc = 0;

done:
    cJSON_Delete(root);
    return rc;
}
