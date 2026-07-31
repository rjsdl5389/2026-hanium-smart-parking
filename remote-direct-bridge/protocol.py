"""NDJSON message construction and parsing for the REMOTE_DIRECT bridge.

This module is a pure, side-effect-free translation layer between Python dicts
and the exact JSON line format the ESP32 firmware parses/emits. It is fully unit
testable without a socket.

Notebook -> ESP32 messages built here:
    HELLO_ACK, HEARTBEAT, SET_MODE, DIRECT_CONTROL, STOP, RESET

ESP32 -> Notebook messages parsed here:
    HELLO, STATUS   (and any other type is returned as a generic dict)

Framing: one compact JSON object per line, terminated by ``\\n`` (NDJSON).
"""

from __future__ import annotations

import json
import math
from typing import Any

import config


class ProtocolError(ValueError):
    """Raised when an inbound line cannot be turned into a valid message."""


# ---------------------------------------------------------------------------
# Framing helpers
# ---------------------------------------------------------------------------
def encode_line(message: dict[str, Any]) -> bytes:
    """Serialize a message dict to a single NDJSON line (bytes, trailing \\n).

    ``separators`` keeps the JSON compact so we stay under the firmware's
    512-byte inbound line limit.
    """
    text = json.dumps(message, separators=(",", ":"), ensure_ascii=False)
    raw = text.encode("utf-8") + b"\n"
    if len(raw) > config.TX_MAX_LINE_BYTES:
        raise ProtocolError(
            f"outbound line {len(raw)}B exceeds TX limit {config.TX_MAX_LINE_BYTES}B: {text}"
        )
    return raw


def parse_line(line: str) -> dict[str, Any]:
    """Parse one inbound NDJSON line into a validated message dict.

    Validates version, type presence, and car_id. Returns the raw dict with an
    added ``type`` guaranteed to be a non-empty string. Raises ProtocolError on
    anything malformed so the caller can log-and-drop without executing.
    """
    line = line.strip()
    if not line:
        raise ProtocolError("empty line")
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ProtocolError("top-level JSON is not an object")

    version = obj.get("version")
    if version != config.PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported/missing version: {version!r}")

    msg_type = obj.get("type")
    if not isinstance(msg_type, str) or not msg_type:
        raise ProtocolError("missing/invalid type")

    car_id = obj.get("car_id")
    if car_id != config.CAR_ID:
        raise ProtocolError(f"car_id mismatch: {car_id!r}")

    return obj


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------
def clamp(value: float, low: float, high: float) -> float:
    """Clamp *value* to [low, high]; reject NaN/inf up front."""
    if not math.isfinite(value):
        raise ProtocolError(f"non-finite control value: {value!r}")
    return max(low, min(high, value))


# ---------------------------------------------------------------------------
# Outbound builders (notebook -> ESP32)
# ---------------------------------------------------------------------------
def build_hello_ack(session_id: str, boot_id: str, command_seq_start: int = 1,
                    result: str = "READY_ALLOWED", reason: str = "") -> dict[str, Any]:
    """Build HELLO_ACK and echo the ESP32 ``boot_id``.

    ``reason`` is serialized as ``hold_reason`` for HOLD or ``reject_reason``
    for REJECTED. Keeping this in the builder prevents the transport/controller
    layers from inventing slightly different wire formats.
    """
    message = {
        "version": config.PROTOCOL_VERSION,
        "type": "HELLO_ACK",
        "car_id": config.CAR_ID,
        "boot_id": boot_id,
        "session_id": session_id,
        "result": result,
        "command_seq_start": command_seq_start,
    }
    if reason:
        if result == "HOLD":
            message["hold_reason"] = reason
        elif result == "REJECTED":
            message["reject_reason"] = reason
    return message


def build_heartbeat(session_id: str, heartbeat_seq: int) -> dict[str, Any]:
    return {
        "version": config.PROTOCOL_VERSION,
        "type": "HEARTBEAT",
        "car_id": config.CAR_ID,
        "session_id": session_id,
        "heartbeat_seq": heartbeat_seq,
    }


def build_set_mode(session_id: str, seq: int, mode: str) -> dict[str, Any]:
    """SET_MODE is a reliability command; caller supplies the shared seq."""
    return {
        "version": config.PROTOCOL_VERSION,
        "type": "SET_MODE",
        "car_id": config.CAR_ID,
        "session_id": session_id,
        "seq": seq,
        "mode": mode,
    }


def build_direct_control(session_id: str, control_seq: int,
                         throttle: float, steering: float) -> dict[str, Any]:
    """DIRECT_CONTROL streaming message; uses control_seq, never the reliable seq."""
    return {
        "version": config.PROTOCOL_VERSION,
        "type": "DIRECT_CONTROL",
        "car_id": config.CAR_ID,
        "session_id": session_id,
        "control_seq": control_seq,
        "throttle": round(clamp(throttle, config.THROTTLE_MIN, config.THROTTLE_MAX), 4),
        "steering": round(clamp(steering, config.STEERING_MIN, config.STEERING_MAX), 4),
    }


def build_stop(session_id: str, seq: int, reason: str = "EMERGENCY") -> dict[str, Any]:
    return {
        "version": config.PROTOCOL_VERSION,
        "type": "STOP",
        "car_id": config.CAR_ID,
        "session_id": session_id,
        "seq": seq,
        "reason": reason,
    }


def build_reset(session_id: str, seq: int) -> dict[str, Any]:
    return {
        "version": config.PROTOCOL_VERSION,
        "type": "RESET",
        "car_id": config.CAR_ID,
        "session_id": session_id,
        "seq": seq,
    }


# ---------------------------------------------------------------------------
# Logical fingerprint for reliable payloads
# ---------------------------------------------------------------------------
def reliable_fingerprint(message: dict[str, Any]) -> str:
    """Return a stable fingerprint of a reliable command's *logical* payload.

    Used to decide same-seq-same-payload (retransmit) vs same-seq-different
    -payload (SEQ_CONFLICT), matching the firmware's field-based comparison
    (never the raw JSON string). seq is intentionally excluded because two
    messages with the same seq are compared *by payload*.
    """
    t = message["type"]
    if t == "SET_MODE":
        return f"SET_MODE|{message['mode']}"
    if t == "STOP":
        return f"STOP|{message.get('reason', 'EMERGENCY')}"
    if t == "RESET":
        return "RESET"
    if t == "WAYPOINT":
        return "WAYPOINT|" + "|".join(str(message.get(k)) for k in (
            "route_id", "waypoint_id", "phase", "x_cm", "y_cm",
            "target_heading_deg", "motion_direction", "arrival_mode",
            "speed_cm_s", "position_tolerance_cm", "heading_tolerance_deg",
            "heading_required", "is_final"))
    if t == "WAIT":
        return "WAIT|" + "|".join(str(message.get(k)) for k in (
            "route_id", "waypoint_id", "reason"))
    if t == "GO":
        return "GO|" + "|".join(str(message.get(k)) for k in ("route_id", "waypoint_id"))
    return t


RELIABLE_TYPES = frozenset({"SET_MODE", "STOP", "RESET", "WAYPOINT", "WAIT", "GO"})
