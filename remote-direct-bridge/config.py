"""Static configuration for the REMOTE_DIRECT notebook->ESP32 control bridge.

All values are plain constants so the bridge can run with the Python standard
library only. Nothing here touches Django, Redis, a database, or the network
until :func:`bridge.main` starts the asyncio server.

The wire contract mirrors the ESP32 firmware in ``hanium_day3_v1`` and the
architecture document ``임베디드 시스템 아키텍처(3).docx``. If you change a
value here that also appears in the firmware (port, car_id, protocol version,
line length), change it in ``app_config.h`` too.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# TCP server
# ---------------------------------------------------------------------------
HOST: str = "0.0.0.0"          # listen on every interface so the ESP32 can reach us
PORT: int = 5000               # must equal SERVER_PORT in app_config.h
PROTOCOL_VERSION: int = 1      # must equal PROTOCOL_VERSION in app_config.h
CAR_ID: str = "CAR_01"         # must equal CAR_ID in app_config.h (this bridge = 1 car)

# NDJSON framing.
# The firmware rejects *inbound* command lines longer than 512 bytes, so every
# message we send stays <= this. STATUS lines are also kept within the same 512-byte architecture cap.
TX_MAX_LINE_BYTES: int = 512
RX_MAX_LINE_BYTES: int = 512
STREAM_BUFFER_LIMIT: int = 4096   # drop/reset the RX buffer past this (garbage guard)

# ---------------------------------------------------------------------------
# Timing (seconds)
# ---------------------------------------------------------------------------
HEARTBEAT_PERIOD_S: float = 0.250       # notebook -> ESP32 HEARTBEAT, 250 ms
DIRECT_CONTROL_PERIOD_S: float = 0.100  # notebook -> ESP32 DIRECT_CONTROL, 10 Hz
RELIABLE_RESEND_TIMEOUT_S: float = 0.30  # default reliable-command retry interval
STOP_RESEND_TIMEOUT_S: float = 0.10      # architecture target: STOP response/retry 50-100 ms
WAIT_RESEND_TIMEOUT_S: float = 0.10      # architecture target: WAIT response/retry about 100 ms
RELIABLE_RESEND_POLL_S: float = 0.05     # lets STOP/WAIT retries hit their shorter deadlines
RELIABLE_MAX_RESENDS: int = 5            # give up (and log) after this many resends
STATUS_PRINT_MIN_INTERVAL_S: float = 0.0  # 0 = print every changed STATUS

# ---------------------------------------------------------------------------
# Control value limits (normalized, ESP32 maps to PWM/servo)
# ---------------------------------------------------------------------------
THROTTLE_MIN: float = -1.0
THROTTLE_MAX: float = 1.0
STEERING_MIN: float = -1.0
STEERING_MAX: float = 1.0

# Step sizes for keyboard nudging.
THROTTLE_STEP: float = 0.05
STEERING_STEP: float = 0.10
DEFAULT_FORWARD_THROTTLE: float = 0.10  # first bench test value from the spec
KEYBOARD_DEADMAN_S: float = 0.75  # no repeated drive key -> throttle 0 (Windows key mode)

# Keyboard bindings (documented in README). Values are single characters.
KEY_FORWARD = "w"
KEY_LEFT = "a"
KEY_RIGHT = "d"
KEY_SLOW = "s"       # decelerate toward throttle 0
KEY_CENTER = "c"     # steering -> center
KEY_STOP_A = " "     # space
KEY_STOP_B = "x"
KEY_RESET = "r"
KEY_MODE_REMOTE = "m"
KEY_QUIT = "q"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = "INFO"  # DEBUG for full wire dump
