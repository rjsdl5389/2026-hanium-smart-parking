"""In-memory protocol/session state for one ESP32 vehicle.

The bridge intentionally keeps this state in RAM only.  A reconnect creates a
fresh session and never resumes motion automatically.

v5.3 hardening rules
--------------------
* reliable commands are completed only by an explicit terminal STATUS whose
  result belongs to the exact command seq; periodic ``command_result=NONE``
  never acknowledges a command;
* STATUS snapshots are monotonic by ``status_seq``.  Older snapshots may still
  carry a useful command acknowledgement, but they must not roll the GUI/state
  or encoder delta backward;
* reliable ``seq`` and streaming ``control_seq`` remain independent.
"""

from __future__ import annotations

import itertools
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Optional


TERMINAL_COMMAND_RESULTS = frozenset({
    "ACCEPTED",
    "ALREADY_STOPPED",
    "INVALID_STATE",
    "SESSION_MISMATCH",
    "SEQ_CONFLICT",
    "STALE_SEQ",
    "TARGET_MISMATCH",
    "TARGET_NOT_LOADED",
    "NEW_ROUTE_REQUIRED",
    "STALE_ROUTE",
    "POSE_REQUIRED",
    "LOCKED_STATE",
    "PROTOCOL_ERROR",
    "HOLD",
    "REJECTED",
})

NEGATIVE_COMMAND_RESULTS = TERMINAL_COMMAND_RESULTS - {"ACCEPTED", "ALREADY_STOPPED"}


def new_session_id() -> str:
    """Return a short uppercase session id such as ``S1A2B3C4``."""
    return "S" + secrets.token_hex(4).upper()


@dataclass
class OutstandingCommand:
    """A reliable command awaiting an explicit terminal STATUS."""

    seq: int
    message: dict[str, Any]
    fingerprint: str
    sent_at: float
    resend_timeout_s: float = 0.30
    resends: int = 0

    @property
    def message_type(self) -> str:
        return str(self.message.get("type", "UNKNOWN"))


@dataclass
class VehicleSession:
    """All mutable state for the one connected vehicle."""

    session_id: str
    boot_id: str
    command_seq_start: int = 1

    _seq_counter: "itertools.count" = field(init=False, repr=False)
    outstanding: Optional[OutstandingCommand] = None

    _control_seq_counter: "itertools.count" = field(init=False, repr=False)
    _heartbeat_counter: "itertools.count" = field(init=False, repr=False)

    desired_throttle: float = 0.0
    desired_steering: float = 0.0

    last_status: Optional[dict[str, Any]] = None
    last_status_at: float = 0.0
    last_status_seq: int = -1

    def __post_init__(self) -> None:
        self._seq_counter = itertools.count(self.command_seq_start)
        self._control_seq_counter = itertools.count(1)
        self._heartbeat_counter = itertools.count(1)

    def next_seq(self) -> int:
        return next(self._seq_counter)

    def next_control_seq(self) -> int:
        return next(self._control_seq_counter)

    def next_heartbeat_seq(self) -> int:
        return next(self._heartbeat_counter)

    def set_outstanding(self, cmd: OutstandingCommand) -> None:
        self.outstanding = cmd

    def clear_outstanding(self) -> None:
        self.outstanding = None

    def has_outstanding(self) -> bool:
        return self.outstanding is not None

    @staticmethod
    def _terminal_result_matches(status: dict[str, Any], seq: int) -> bool:
        result = str(status.get("command_result", "NONE"))
        if result not in TERMINAL_COMMAND_RESULTS:
            return False

        acked = status.get("last_processed_cmd_seq")
        rejected = status.get("rejected_seq")

        # Normal accepted/invalid-state responses update last_processed_cmd_seq.
        if isinstance(acked, int) and acked == seq:
            return True

        # Parse/session/sequence rejection paths may report the rejected seq
        # separately without advancing last_processed_cmd_seq.
        if isinstance(rejected, int) and rejected == seq:
            return True

        return False

    def consume_terminal_result(self, status: dict[str, Any]) -> Optional[OutstandingCommand]:
        """Clear and return the outstanding command only on an exact final result.

        A periodic STATUS repeats ``last_processed_cmd_seq`` with
        ``command_result=NONE``.  Treating that as an acknowledgement caused the
        original intermittent SET_MODE race, so it is explicitly ignored.
        """
        cmd = self.outstanding
        if cmd is None:
            return None
        if not self._terminal_result_matches(status, cmd.seq):
            return None
        self.outstanding = None
        return cmd

    def is_stale_snapshot(self, status: dict[str, Any]) -> bool:
        seq = status.get("status_seq")
        if not isinstance(seq, int):
            return False
        return seq <= self.last_status_seq

    def record_snapshot(self, status: dict[str, Any]) -> None:
        self.last_status = status
        self.last_status_at = time.monotonic()
        seq = status.get("status_seq")
        if isinstance(seq, int) and seq > self.last_status_seq:
            self.last_status_seq = seq
