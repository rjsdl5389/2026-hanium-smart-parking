"""Safety-focused control logic for the REMOTE_DIRECT bridge.

v5.3 fixes the intermittent recovery failure seen after STOP -> RESET -> MODE:

* periodic STATUS(result=NONE) can no longer complete or reject SET_MODE;
* a delayed command ACK is still consumed even when its status_seq is older,
  while the stale snapshot is prevented from rolling GUI/state backward;
* repeated M/R/Space requests are idempotently gated in the controller;
* non-zero drive input is ignored until REMOTE_DIRECT is positively armed;
* reliable-command timeout clears any associated pending mode gate.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import config
import protocol
from session import (
    NEGATIVE_COMMAND_RESULTS,
    OutstandingCommand,
    VehicleSession,
    new_session_id,
)

BRIDGE_BUILD_ID = "v5.3-logic-hardening"
BRIDGE_SOURCE_PATH = str(Path(__file__).resolve())

log = logging.getLogger("bridge.controller")
Sender = Callable[[dict[str, Any]], Awaitable[None]]


class Controller:
    """Own session state and translate GUI intents into wire messages."""

    def __init__(self) -> None:
        self.session: Optional[VehicleSession] = None
        self.sender: Optional[Sender] = None
        self._direct_streaming = False
        self._pending_remote_mode_seq: Optional[int] = None
        self._hello_result = ""
        self._hello_reason = ""
        self._last_printed_status_key: Optional[tuple] = None
        self._last_encoder_count: Optional[int] = None
        self._status_listeners: list[Callable[[dict[str, Any]], None]] = []
        self._connection_listeners: list[Callable[[bool], None]] = []
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Transport wiring
    # ------------------------------------------------------------------
    def add_status_listener(self, listener: Callable[[dict[str, Any]], None]) -> None:
        self._status_listeners.append(listener)

    def add_connection_listener(self, listener: Callable[[bool], None]) -> None:
        self._connection_listeners.append(listener)

    def _notify_connection(self, connected: bool) -> None:
        for listener in tuple(self._connection_listeners):
            try:
                listener(connected)
            except Exception as exc:  # noqa: BLE001
                log.debug("connection listener failed: %s", exc)

    def _notify_status(self, message: dict[str, Any]) -> None:
        published = dict(message)
        published["bridge_build"] = BRIDGE_BUILD_ID
        published["bridge_direct_streaming"] = self._direct_streaming
        published["bridge_pending_mode_seq"] = self._pending_remote_mode_seq
        for listener in tuple(self._status_listeners):
            try:
                listener(dict(published))
            except Exception as exc:  # noqa: BLE001
                log.debug("status listener failed: %s", exc)

    def attach(self, sender: Sender) -> None:
        self.sender = sender
        self._notify_connection(True)

    def _neutralize_desired(self) -> None:
        if self.session is not None:
            self.session.desired_throttle = 0.0
            self.session.desired_steering = 0.0

    def detach(self) -> None:
        self._neutralize_desired()
        self.sender = None
        self._direct_streaming = False
        self._pending_remote_mode_seq = None
        self._hello_result = ""
        self._hello_reason = ""
        self._last_encoder_count = None
        self._last_printed_status_key = None
        if self.session is not None:
            log.warning("Connection dropped; discarding session %s", self.session.session_id)
        self.session = None
        self._notify_connection(False)

    async def _send(self, message: dict[str, Any]) -> None:
        sender = self.sender
        if sender is None:
            return
        try:
            await sender(message)
        except Exception as exc:  # noqa: BLE001
            log.warning("send failed (%s): %s", message.get("type"), exc)

    # ------------------------------------------------------------------
    # Inbound dispatch
    # ------------------------------------------------------------------
    async def on_message(self, message: dict[str, Any]) -> None:
        mtype = message.get("type")
        if mtype == "HELLO":
            await self._on_hello(message)
        elif mtype == "STATUS":
            self._on_status(message)
        else:
            log.debug("RX unhandled type=%s", mtype)

    async def _on_hello(self, message: dict[str, Any]) -> None:
        boot_id = message.get("boot_id")
        if not isinstance(boot_id, str) or not boot_id:
            log.warning("HELLO missing boot_id; ignoring")
            return

        if (
            self.session is not None
            and self.session.boot_id == boot_id
            and message.get("previous_session_id") != self.session.session_id
        ):
            ack = protocol.build_hello_ack(
                session_id=self.session.session_id,
                boot_id=boot_id,
                command_seq_start=self.session.command_seq_start,
                result=self._hello_result or "READY_ALLOWED",
                reason=self._hello_reason,
            )
            log.info(
                "Repeated HELLO boot_id=%s -> reusing session_id=%s",
                boot_id,
                self.session.session_id,
            )
            await self._send(ack)
            return

        previous_state = message.get("previous_state")
        motor_stopped = message.get("motor_stopped")
        error_code = message.get("error_code")
        result = "READY_ALLOWED"
        reason = ""
        if previous_state in ("ERROR", "EMERGENCY_STOP"):
            result, reason = "HOLD", f"PREVIOUS_STATE_{previous_state}"
        elif motor_stopped is not True:
            result, reason = "HOLD", "MOTOR_NOT_CONFIRMED_STOPPED"
        elif error_code not in (None, "", "NONE"):
            result, reason = "HOLD", f"ERROR_{error_code}"

        session = VehicleSession(
            session_id=new_session_id(),
            boot_id=boot_id,
            command_seq_start=1,
        )
        self.session = session
        self._direct_streaming = False
        self._pending_remote_mode_seq = None
        self._hello_result = result
        self._hello_reason = reason
        self._last_encoder_count = None
        self._last_printed_status_key = None

        ack = protocol.build_hello_ack(
            session_id=session.session_id,
            boot_id=boot_id,
            command_seq_start=session.command_seq_start,
            result=result,
            reason=reason,
        )
        log.info(
            "HELLO from boot_id=%s fw=%s -> session_id=%s result=%s",
            boot_id,
            message.get("firmware_version"),
            session.session_id,
            result,
        )
        await self._send(ack)
        if result == "READY_ALLOWED":
            log.info("HELLO_ACK READY_ALLOWED sent. Issue M once before driving.")
        else:
            log.warning("HELLO_ACK HOLD sent (%s). RESET is required; driving is locked.", reason)

    @staticmethod
    def _result_matches_seq(message: dict[str, Any], seq: int) -> bool:
        result = str(message.get("command_result", "NONE"))
        if result == "NONE":
            return False
        acked = message.get("last_processed_cmd_seq")
        rejected = message.get("rejected_seq")
        return acked == seq or rejected == seq

    def _finish_pending_mode_from_status(self, message: dict[str, Any]) -> None:
        pending_seq = self._pending_remote_mode_seq
        if pending_seq is None or not self._result_matches_seq(message, pending_seq):
            return

        result = str(message.get("command_result", "NONE"))
        mode = message.get("mode")
        if result == "ACCEPTED" and mode == "REMOTE_DIRECT":
            self._direct_streaming = True
            self._pending_remote_mode_seq = None
            log.info("REMOTE_DIRECT acknowledged; DIRECT_CONTROL streaming enabled.")
            return

        if result in NEGATIVE_COMMAND_RESULTS or mode != "REMOTE_DIRECT":
            self._direct_streaming = False
            self._pending_remote_mode_seq = None
            self._neutralize_desired()
            log.warning("REMOTE_DIRECT rejected (result=%s, mode=%s).", result, mode)

    def _on_status(self, message: dict[str, Any]) -> None:
        session = self.session
        if session is None:
            return
        if message.get("session_id") != session.session_id:
            return

        # Command completion is processed before status_seq filtering because the
        # firmware's separate high/latest queues could historically deliver an
        # older command ACK after a newer periodic STATUS.
        completed = session.consume_terminal_result(message)
        self._finish_pending_mode_from_status(message)
        if completed is not None:
            log.debug(
                "Reliable command completed: %s seq=%d result=%s",
                completed.message_type,
                completed.seq,
                message.get("command_result"),
            )

        if session.is_stale_snapshot(message):
            log.debug(
                "Ignoring stale STATUS snapshot status_seq=%s (latest=%s), result=%s seq_ack=%s",
                message.get("status_seq"),
                session.last_status_seq,
                message.get("command_result"),
                message.get("last_processed_cmd_seq"),
            )
            return

        encoder_count = message.get("encoder_count")
        if isinstance(encoder_count, int):
            previous = self._last_encoder_count
            message = dict(message)
            message["encoder_delta"] = 0 if previous is None else encoder_count - previous
            self._last_encoder_count = encoder_count

        state = message.get("state")
        mode = message.get("mode")
        if state in {"EMERGENCY_STOP", "ERROR", "COMM_TIMEOUT", "SYNCING"}:
            self._direct_streaming = False
            self._pending_remote_mode_seq = None
            self._neutralize_desired()
        elif mode != "REMOTE_DIRECT" and self._direct_streaming:
            self._direct_streaming = False
            self._neutralize_desired()

        session.record_snapshot(message)
        self._notify_status(message)
        self._print_status(message)

    # ------------------------------------------------------------------
    # High-level intents
    # ------------------------------------------------------------------
    def _latest_state_mode(self) -> tuple[Optional[str], Optional[str]]:
        if self.session is None or self.session.last_status is None:
            return None, None
        status = self.session.last_status
        return status.get("state"), status.get("mode")

    async def cmd_mode_remote(self) -> None:
        session = self.session
        if session is None:
            log.warning("No active session; SET_MODE dropped.")
            return

        if self._pending_remote_mode_seq is not None:
            log.info("SET_MODE ignored: REMOTE_DIRECT request seq=%d is already pending.",
                     self._pending_remote_mode_seq)
            return

        state, mode = self._latest_state_mode()
        if state != "READY":
            log.warning("SET_MODE ignored: vehicle state must be READY (current=%s).", state)
            return

        # Idempotent re-arm: if the latest verified snapshot already says the
        # vehicle is READY/REMOTE_DIRECT, no reliable command is necessary.
        if mode == "REMOTE_DIRECT":
            self._neutralize_desired()
            self._direct_streaming = True
            log.info("REMOTE_DIRECT already active; streaming safely re-armed at neutral.")
            return

        seq = await self._send_reliable(
            lambda sid, command_seq: protocol.build_set_mode(
                sid, command_seq, "REMOTE_DIRECT"
            )
        )
        if seq is None:
            return
        self._neutralize_desired()
        self._direct_streaming = False
        self._pending_remote_mode_seq = seq
        log.info("SET_MODE(REMOTE_DIRECT) sent seq=%d; waiting for explicit ACCEPTED.", seq)

    async def cmd_stop(self) -> None:
        state, _ = self._latest_state_mode()
        self._direct_streaming = False
        self._pending_remote_mode_seq = None
        self._neutralize_desired()
        if state == "EMERGENCY_STOP" and self.session is not None and not self.session.has_outstanding():
            log.info("STOP ignored: vehicle is already in EMERGENCY_STOP.")
            return
        seq = await self._send_reliable(protocol.build_stop, preempt=True)
        if seq is not None:
            log.warning("STOP sent -> EMERGENCY_STOP. Recover with R, wait READY, then M once.")

    async def cmd_reset(self) -> None:
        state, _ = self._latest_state_mode()
        allowed = state in {"EMERGENCY_STOP", "ERROR"}
        if state == "SYNCING" and self._hello_result == "HOLD":
            allowed = True
        if not allowed:
            log.warning("RESET ignored: valid only in EMERGENCY_STOP/ERROR/HOLD (current=%s).", state)
            return

        self._direct_streaming = False
        self._pending_remote_mode_seq = None
        self._neutralize_desired()
        seq = await self._send_reliable(protocol.build_reset)
        if seq is not None:
            log.info("RESET sent. Wait for READY/WAYPOINT_AUTO, then press M once.")

    def cmd_set_throttle(self, value: float) -> None:
        if self.session is None:
            return
        value = protocol.clamp(value, config.THROTTLE_MIN, config.THROTTLE_MAX)
        if value != 0.0 and not self._direct_streaming:
            self.session.desired_throttle = 0.0
            return
        self.session.desired_throttle = value

    def cmd_set_steering(self, value: float) -> None:
        if self.session is None:
            return
        value = protocol.clamp(value, config.STEERING_MIN, config.STEERING_MAX)
        if value != 0.0 and not self._direct_streaming:
            self.session.desired_steering = 0.0
            return
        self.session.desired_steering = value

    def cmd_set_drive(self, throttle: float, steering: float) -> None:
        if self.session is None:
            return
        throttle = protocol.clamp(throttle, config.THROTTLE_MIN, config.THROTTLE_MAX)
        steering = protocol.clamp(steering, config.STEERING_MIN, config.STEERING_MAX)
        if not self._direct_streaming and (throttle != 0.0 or steering != 0.0):
            self._neutralize_desired()
            return
        self.session.desired_throttle = throttle
        self.session.desired_steering = steering

    def cmd_nudge_throttle(self, delta: float) -> None:
        if self.session is not None:
            self.cmd_set_throttle(self.session.desired_throttle + delta)

    def cmd_nudge_steering(self, delta: float) -> None:
        if self.session is not None:
            self.cmd_set_steering(self.session.desired_steering + delta)

    def cmd_center(self) -> None:
        if self.session is not None:
            self.session.desired_steering = 0.0

    def cmd_neutral(self) -> None:
        if self.session is not None:
            self.session.desired_throttle = 0.0

    def cmd_pause_direct_stream(self) -> None:
        self._direct_streaming = False
        self._neutralize_desired()
        log.warning("DIRECT_CONTROL streaming paused; firmware should safe-stop after timeout.")

    def cmd_resume_direct_stream(self) -> None:
        state, mode = self._latest_state_mode()
        if mode != "REMOTE_DIRECT" or state not in {"READY", "WAITING"}:
            log.warning("Cannot resume stream: state=%s mode=%s.", state, mode)
            return
        self._neutralize_desired()
        self._direct_streaming = True
        log.info("DIRECT_CONTROL streaming resumed at neutral.")

    def status_line(self) -> str:
        if self.session is None or self.session.last_status is None:
            return "no STATUS yet (waiting for ESP32 HELLO/STATUS)"
        return _format_status(self.session.last_status)

    # ------------------------------------------------------------------
    # Reliable command send/resend
    # ------------------------------------------------------------------
    async def _send_reliable(self, builder, preempt: bool = False) -> Optional[int]:
        async with self._lock:
            session = self.session
            if session is None:
                log.warning("No active session; command dropped.")
                return None
            if session.has_outstanding() and not preempt:
                log.warning(
                    "Previous reliable command seq=%d (%s) still outstanding; request ignored.",
                    session.outstanding.seq,
                    session.outstanding.message_type,
                )
                return None
            seq = session.next_seq()
            message = builder(session.session_id, seq)
            fp = protocol.reliable_fingerprint(message)
            mtype = message.get("type")
            if mtype == "STOP":
                resend_timeout_s = config.STOP_RESEND_TIMEOUT_S
            elif mtype == "WAIT":
                resend_timeout_s = config.WAIT_RESEND_TIMEOUT_S
            else:
                resend_timeout_s = config.RELIABLE_RESEND_TIMEOUT_S
            session.set_outstanding(
                OutstandingCommand(
                    seq=seq,
                    message=message,
                    fingerprint=fp,
                    sent_at=time.monotonic(),
                    resend_timeout_s=resend_timeout_s,
                )
            )
            await self._send(message)
            log.info("TX %s seq=%d", message["type"], seq)
            return seq

    async def heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(config.HEARTBEAT_PERIOD_S)
            session = self.session
            if session is None or self.sender is None:
                continue
            await self._send(
                protocol.build_heartbeat(session.session_id, session.next_heartbeat_seq())
            )

    async def direct_control_loop(self) -> None:
        while True:
            await asyncio.sleep(config.DIRECT_CONTROL_PERIOD_S)
            session = self.session
            if session is None or self.sender is None or not self._direct_streaming:
                continue
            state, mode = self._latest_state_mode()
            if mode != "REMOTE_DIRECT" or state in {
                "EMERGENCY_STOP", "ERROR", "COMM_TIMEOUT", "SYNCING",
                "BOOT", "WIFI_CONNECTING",
            }:
                self._direct_streaming = False
                self._neutralize_desired()
                continue
            await self._send(
                protocol.build_direct_control(
                    session.session_id,
                    session.next_control_seq(),
                    session.desired_throttle,
                    session.desired_steering,
                )
            )

    async def reliable_resend_loop(self) -> None:
        while True:
            await asyncio.sleep(config.RELIABLE_RESEND_POLL_S)
            session = self.session
            if session is None or self.sender is None or not session.has_outstanding():
                continue
            cmd = session.outstanding
            if time.monotonic() - cmd.sent_at < cmd.resend_timeout_s:
                continue
            if cmd.resends >= config.RELIABLE_MAX_RESENDS:
                log.error(
                    "Reliable command seq=%d (%s) unacked after %d resends; giving up.",
                    cmd.seq,
                    cmd.message_type,
                    cmd.resends,
                )
                session.clear_outstanding()
                if self._pending_remote_mode_seq == cmd.seq:
                    self._pending_remote_mode_seq = None
                    self._direct_streaming = False
                    self._neutralize_desired()
                continue
            cmd.resends += 1
            cmd.sent_at = time.monotonic()
            await self._send(cmd.message)
            log.info("RESEND %s seq=%d (attempt %d)", cmd.message_type, cmd.seq, cmd.resends)

    def _print_status(self, status: dict[str, Any]) -> None:
        key = (
            status.get("state"),
            status.get("mode"),
            status.get("wait_reason"),
            status.get("error_code"),
            status.get("command_result"),
            status.get("last_processed_cmd_seq"),
            status.get("latest_control_seq"),
            _round(status.get("applied_throttle")),
            _round(status.get("applied_steering")),
            status.get("encoder_count"),
            status.get("encoder_delta"),
        )
        if key == self._last_printed_status_key:
            return
        self._last_printed_status_key = key
        log.info("STATUS %s", _format_status(status))


def _round(value: Any) -> Any:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return value


def _format_status(s: dict[str, Any]) -> str:
    def g(key: str, default: str = "?") -> str:
        return str(s.get(key, default))

    parts = [
        f"state={g('state')}",
        f"mode={g('mode')}",
        f"seq_ack={g('last_processed_cmd_seq')}",
        f"result={g('command_result')}",
    ]
    if "latest_control_seq" in s:
        parts.extend([
            f"ctl_seq={g('latest_control_seq')}",
            f"thr={g('applied_throttle')}",
            f"str={g('applied_steering')}",
        ])
    if "encoder_count" in s:
        parts.extend([f"enc={g('encoder_count')}", f"denc={g('encoder_delta')}"])
    parts.extend([
        f"wait={g('wait_reason')}",
        f"err={g('error_code')}",
        f"status_seq={g('status_seq')}",
    ])
    return " ".join(parts)
