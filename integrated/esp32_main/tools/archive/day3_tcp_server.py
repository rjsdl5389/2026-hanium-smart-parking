#!/usr/bin/env python3
"""Laptop TCP test server for Hanium DAY3 v1."""

from __future__ import annotations

import json
import secrets
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any

HOST = "0.0.0.0"
PORT = 5000
CAR_ID = "CAR_01"
PROTOCOL_VERSION = 1
HEARTBEAT_PERIOD_S = 0.25


@dataclass
class ServerState:
    connection: socket.socket | None = None
    session_id: str = ""
    boot_id: str = ""
    next_seq: int = 1
    heartbeat_seq: int = 1
    heartbeat_enabled: bool = True
    route_id: int = 1
    waypoint_id: int = 1
    phase: str = "CRUISE"
    last_reliable_line: str = ""
    last_status_signature: tuple[Any, ...] | None = None


state = ServerState()
state_lock = threading.Lock()
send_lock = threading.Lock()
stop_event = threading.Event()


def compact(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def send_line(line: str, *, quiet: bool = False) -> bool:
    with send_lock:
        with state_lock:
            connection = state.connection
        if connection is None:
            print("[SERVER] No active ESP32 connection")
            return False
        try:
            connection.sendall((line + "\n").encode("utf-8"))
            if not quiet:
                print(f"[TX] {line}")
            return True
        except OSError as error:
            print(f"[SERVER] send failed: {error}")
            return False


def send_json(
    payload: dict[str, Any],
    remember: bool = False,
    *,
    quiet: bool = False,
) -> bool:
    line = compact(payload)
    sent = send_line(line, quiet=quiet)
    if sent and remember:
        with state_lock:
            state.last_reliable_line = line
    return sent


def allocate_seq() -> int:
    with state_lock:
        seq = state.next_seq
        state.next_seq += 1
    return seq


def require_session() -> str | None:
    with state_lock:
        session_id = state.session_id
    if not session_id:
        print("[SERVER] Wait for HELLO / HELLO_ACK synchronization")
        return None
    return session_id


def context() -> tuple[str, int, int, str]:
    with state_lock:
        return state.session_id, state.route_id, state.waypoint_id, state.phase


def send_hello_ack(hello: dict[str, Any]) -> None:
    boot_id = str(hello.get("boot_id", "UNKNOWN"))
    previous_state = str(hello.get("previous_state", "UNKNOWN"))
    session_id = "S" + secrets.token_hex(4).upper()
    locked = previous_state in {"EMERGENCY_STOP", "ERROR"}

    with state_lock:
        state.boot_id = boot_id
        state.session_id = session_id
        state.next_seq = 1
        state.heartbeat_seq = 1
        state.last_reliable_line = ""

    payload: dict[str, Any] = {
        "version": PROTOCOL_VERSION,
        "type": "HELLO_ACK",
        "car_id": CAR_ID,
        "boot_id": boot_id,
        "session_id": session_id,
        "result": "HOLD" if locked else "READY_ALLOWED",
        "command_seq_start": 1,
    }
    if locked:
        payload["hold_reason"] = "LOCKED_STATE"
        print("[SERVER] HELLO previous_state is locked; sending HOLD")
    send_json(payload)


def receiver_loop(connection: socket.socket) -> None:
    buffer = b""
    try:
        while not stop_event.is_set():
            chunk = connection.recv(2048)
            if not chunk:
                print("[SERVER] ESP32 disconnected")
                return
            buffer += chunk
            while b"\n" in buffer:
                raw_line, buffer = buffer.split(b"\n", 1)
                raw_line = raw_line.rstrip(b"\r")
                if not raw_line:
                    continue
                try:
                    line = raw_line.decode("utf-8")
                    payload = json.loads(line)
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    print(f"[SERVER] Invalid RX: {error}")
                    continue

                if payload.get("type") == "STATUS":
                    signature = (
                        payload.get("state"),
                        payload.get("command_result"),
                        payload.get("last_processed_cmd_seq"),
                        payload.get("rejected_seq"),
                        payload.get("route_id"),
                        payload.get("waypoint_id"),
                        payload.get("resume_allowed"),
                        payload.get("wait_reason"),
                        payload.get("duplicate"),
                    )
                    with state_lock:
                        changed = signature != state.last_status_signature
                        state.last_status_signature = signature
                    if changed or payload.get("command_result") != "NONE":
                        print(
                            "[STATUS] "
                            f"state={payload.get('state')} "
                            f"result={payload.get('command_result')} "
                            f"last_seq={payload.get('last_processed_cmd_seq')} "
                            f"rejected_seq={payload.get('rejected_seq')} "
                            f"route={payload.get('route_id')} "
                            f"wp={payload.get('waypoint_id')} "
                            f"resume={payload.get('resume_allowed')} "
                            f"wait={payload.get('wait_reason')} "
                            f"dup={payload.get('duplicate')}"
                        )
                else:
                    print(f"[RX] {line}")

                if payload.get("type") == "HELLO":
                    send_hello_ack(payload)
    except OSError as error:
        print(f"[SERVER] receiver stopped: {error}")
    finally:
        with state_lock:
            if state.connection is connection:
                state.connection = None
                state.session_id = ""
        try:
            connection.close()
        except OSError:
            pass


def accept_loop(server_socket: socket.socket) -> None:
    while not stop_event.is_set():
        try:
            connection, address = server_socket.accept()
        except OSError:
            return
        print(f"[SERVER] ESP32 connected from {address}")
        with state_lock:
            old = state.connection
            state.connection = connection
            state.session_id = ""
        if old is not None:
            try:
                old.close()
            except OSError:
                pass
        threading.Thread(target=receiver_loop, args=(connection,), daemon=True).start()


def heartbeat_loop() -> None:
    while not stop_event.is_set():
        time.sleep(HEARTBEAT_PERIOD_S)
        with state_lock:
            enabled = state.heartbeat_enabled
            session_id = state.session_id
            heartbeat_seq = state.heartbeat_seq
            if enabled and session_id:
                state.heartbeat_seq += 1
        if enabled and session_id:
            send_json({
                "version": PROTOCOL_VERSION,
                "type": "HEARTBEAT",
                "car_id": CAR_ID,
                "session_id": session_id,
                "heartbeat_seq": heartbeat_seq,
            }, quiet=True)


def send_waypoint(*, new_route: bool = False, next_waypoint: bool = False) -> None:
    session_id = require_session()
    if session_id is None:
        return
    with state_lock:
        if new_route:
            state.route_id += 1
            state.waypoint_id = 1
            state.phase = "CRUISE"
        elif next_waypoint:
            state.waypoint_id += 1
            state.phase = "ALIGN" if state.waypoint_id >= 3 else "CRUISE"
        route_id = state.route_id
        waypoint_id = state.waypoint_id
        phase = state.phase
    send_json({
        "version": PROTOCOL_VERSION,
        "type": "WAYPOINT",
        "car_id": CAR_ID,
        "session_id": session_id,
        "seq": allocate_seq(),
        "route_id": route_id,
        "waypoint_id": waypoint_id,
        "phase": phase,
        "x_cm": 50.0,
        "y_cm": 50.0,
        "target_heading_deg": 0.0,
        "motion_direction": "FORWARD",
        "arrival_mode": "STOP",
        "speed_cm_s": 5.0,
        "position_tolerance_cm": 5.0,
        "heading_tolerance_deg": 12.0,
        "heading_required": False,
        "is_final": phase == "FINAL",
    }, remember=True)


def send_go() -> None:
    session_id, route_id, waypoint_id, _ = context()
    if not session_id:
        print("[SERVER] No synchronized session")
        return
    send_json({
        "version": PROTOCOL_VERSION,
        "type": "GO",
        "car_id": CAR_ID,
        "session_id": session_id,
        "seq": allocate_seq(),
        "route_id": route_id,
        "waypoint_id": waypoint_id,
    }, remember=True)


def send_wait(reason: str) -> None:
    session_id, route_id, waypoint_id, _ = context()
    if not session_id:
        print("[SERVER] No synchronized session")
        return
    send_json({
        "version": PROTOCOL_VERSION,
        "type": "WAIT",
        "car_id": CAR_ID,
        "session_id": session_id,
        "seq": allocate_seq(),
        "route_id": route_id,
        "waypoint_id": waypoint_id,
        "reason": reason,
    }, remember=True)


def send_stop() -> None:
    session_id = require_session()
    if session_id is None:
        return
    send_json({
        "version": PROTOCOL_VERSION,
        "type": "STOP",
        "car_id": CAR_ID,
        "session_id": session_id,
        "seq": allocate_seq(),
        "reason": "EMERGENCY",
    }, remember=True)


def send_reset() -> None:
    session_id = require_session()
    if session_id is None:
        return
    send_json({
        "version": PROTOCOL_VERSION,
        "type": "RESET",
        "car_id": CAR_ID,
        "session_id": session_id,
        "seq": allocate_seq(),
    }, remember=True)


def resend_duplicate() -> None:
    with state_lock:
        line = state.last_reliable_line
    if not line:
        print("[SERVER] No previous reliable command")
        return
    send_line(line)


def send_conflict() -> None:
    with state_lock:
        line = state.last_reliable_line
        route_id = state.route_id
        waypoint_id = state.waypoint_id
    if not line:
        print("[SERVER] No previous reliable command")
        return
    payload = json.loads(line)
    # Keep the old seq but force a different, valid logical payload.
    if payload.get("type") == "GO":
        payload["waypoint_id"] = waypoint_id + 999
    else:
        payload = {
            "version": PROTOCOL_VERSION,
            "type": "GO",
            "car_id": CAR_ID,
            "session_id": payload["session_id"],
            "seq": payload["seq"],
            "route_id": route_id,
            "waypoint_id": waypoint_id,
        }
    send_json(payload)


def print_help() -> None:
    print(
        "\nCommands:\n"
        "  wp         Send current WAYPOINT; expect WAITING/AWAITING_START\n"
        "  go         Send GO; expect MOVING when allowed\n"
        "  wait       Send REMOTE_WAIT; target remains resumable\n"
        "  reached    Send WAYPOINT_REACHED; old target GO must fail\n"
        "  next       Increment waypoint_id and send next WAYPOINT\n"
        "  final      Send FINAL_WAYPOINT_REACHED\n"
        "  newroute   Increment route_id and send new WAYPOINT\n"
        "  stop       Send STOP; expect EMERGENCY_STOP\n"
        "  reset      Send RESET; expect READY\n"
        "  dup        Resend exact previous reliable command\n"
        "  conflict   Reuse previous seq with different logical payload\n"
        "  hb_off     Stop heartbeat; expect COMM_TIMEOUT\n"
        "  hb_on      Enable heartbeat\n"
        "  raw JSON   Send raw NDJSON object\n"
        "  help       Show this help\n"
        "  quit       Exit\n"
    )


def console_loop() -> None:
    print_help()
    while not stop_event.is_set():
        try:
            command = input("day3> ").strip()
        except (EOFError, KeyboardInterrupt):
            command = "quit"

        if command == "wp":
            send_waypoint()
        elif command == "go":
            send_go()
        elif command == "wait":
            send_wait("REMOTE_WAIT")
        elif command == "reached":
            send_wait("WAYPOINT_REACHED")
        elif command == "next":
            send_waypoint(next_waypoint=True)
        elif command == "final":
            send_wait("FINAL_WAYPOINT_REACHED")
        elif command == "newroute":
            send_waypoint(new_route=True)
        elif command == "stop":
            send_stop()
        elif command == "reset":
            send_reset()
        elif command == "dup":
            resend_duplicate()
        elif command == "conflict":
            send_conflict()
        elif command == "hb_off":
            with state_lock:
                state.heartbeat_enabled = False
            print("[SERVER] heartbeat disabled")
        elif command == "hb_on":
            with state_lock:
                state.heartbeat_enabled = True
            print("[SERVER] heartbeat enabled")
        elif command.startswith("raw "):
            send_line(command[4:].strip())
        elif command == "help":
            print_help()
        elif command == "quit":
            stop_event.set()
        elif command:
            print("[SERVER] Unknown command; type help")


def main() -> None:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(2)
    print(f"[SERVER] Listening on {HOST}:{PORT}")
    print("[SERVER] Allow Python through Windows Firewall on private networks.")

    threading.Thread(target=accept_loop, args=(server_socket,), daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()

    try:
        console_loop()
    finally:
        stop_event.set()
        try:
            server_socket.close()
        except OSError:
            pass
        with state_lock:
            connection = state.connection
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass


if __name__ == "__main__":
    main()
