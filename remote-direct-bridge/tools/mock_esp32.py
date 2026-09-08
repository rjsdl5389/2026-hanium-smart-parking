"""Mock ESP32 client for validating the bridge WITHOUT hardware.

Run the bridge in one terminal (``python bridge.py``) and this in another
(``python tools/mock_esp32.py``). It speaks the same NDJSON wire protocol as the
real firmware closely enough to exercise the full handshake, SET_MODE idempotency,
DIRECT_CONTROL application, control_seq monotonicity, the 500 ms DIRECT_CONTROL
timeout, STOP/RESET, and periodic STATUS.

It is a *simulation aid only* — the real state machine lives in the ESP32 firmware
(vehicle_control.c). Use this for "2단계 mock 통신 시험" when you are not ready to
flash. Stdlib only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time

HOST_DEFAULT = "127.0.0.1"
PORT_DEFAULT = 5000
CAR_ID = "CAR_01"
VERSION = 1
STATUS_PERIOD_S = 0.20
DIRECT_TIMEOUT_S = 0.50
HEARTBEAT_TIMEOUT_S = 1.0

SERVO_LEFT_STRONG = 46.0
SERVO_LEFT_WEAK = 66.0
SERVO_CENTER = 86.0
SERVO_RIGHT_WEAK = 106.0
SERVO_RIGHT_STRONG = 126.0
MOTOR_MAX_PWM = 255
PWM_FORWARD_MIN = 16
PWM_FORWARD_DEFAULT = 25
PWM_TURN_MIN = 34
PWM_TURN_DEFAULT = 43
PWM_STRONG_TURN_MIN = 40
PWM_STRONG_TURN_DEFAULT = 54
MOTOR_DEADBAND = 0.02



class MockEsp32:
    def __init__(self, actuator_output: bool = False):
        self.boot_id = "B%08X" % random.getrandbits(32)
        self.session_id = ""
        self.session_active = False
        self.state = "SYNCING"
        self.mode = "WAYPOINT_AUTO"
        self.last_processed_cmd_seq = 0
        self.last_seq = None
        self.last_fp = None
        self.last_result = "NONE"
        self.status_seq = 0
        self.wait_reason = "NONE"
        self.error_code = "NONE"
        self.actuator_output = actuator_output

        self.applied_control_seq = 0
        self.applied_throttle = 0.0
        self.applied_steering = 0.0
        self.motor_pwm = 0
        self.motor_direction = "FORWARD"
        self.servo_angle = SERVO_CENTER
        self.last_direct_apply = 0.0
        self.last_heartbeat = time.monotonic()
        self.encoder_count = 0

    # -- helpers -----------------------------------------------------------
    def fingerprint(self, msg):
        t = msg["type"]
        if t == "SET_MODE":
            return f"SET_MODE|{msg['mode']}"
        if t == "STOP":
            return f"STOP|{msg.get('reason','EMERGENCY')}"
        if t == "RESET":
            return "RESET"
        return t

    def safe_stop(self, reason, wait_reason=None, emergency=False, comm=False):
        self.motor_pwm = 0
        self.applied_throttle = 0.0
        self.servo_angle = SERVO_CENTER
        self.applied_steering = 0.0
        self.applied_control_seq = self.applied_control_seq  # keep
        if emergency:
            self.state = "EMERGENCY_STOP"
        elif comm:
            self.state = "COMM_TIMEOUT"
            self.session_active = False
        else:
            self.state = "WAITING"
        if wait_reason:
            self.wait_reason = wait_reason
        # After any safe stop, streaming control is invalidated.
        self.last_direct_apply = 0.0

    @staticmethod
    def _lerp(a, b, t):
        t = min(max(t, 0.0), 1.0)
        return a + (b - a) * t

    @classmethod
    def steering_to_angle(cls, steering):
        s = min(max(steering, -1.0), 1.0)
        if s <= -0.5:
            return cls._lerp(SERVO_LEFT_STRONG, SERVO_LEFT_WEAK, (s + 1.0) / 0.5)
        if s < 0.0:
            return cls._lerp(SERVO_LEFT_WEAK, SERVO_CENTER, (s + 0.5) / 0.5)
        if s <= 0.5:
            return cls._lerp(SERVO_CENTER, SERVO_RIGHT_WEAK, s / 0.5)
        return cls._lerp(SERVO_RIGHT_WEAK, SERVO_RIGHT_STRONG, (s - 0.5) / 0.5)

    @classmethod
    def throttle_to_pwm(cls, throttle, steering):
        magnitude = min(abs(throttle), 1.0)
        if magnitude <= MOTOR_DEADBAND:
            return 0
        abs_steering = min(abs(steering), 1.0)
        if abs_steering <= 0.5:
            t = abs_steering / 0.5
            min_pwm = cls._lerp(PWM_FORWARD_MIN, PWM_TURN_MIN, t)
            default_pwm = cls._lerp(PWM_FORWARD_DEFAULT, PWM_TURN_DEFAULT, t)
        else:
            t = (abs_steering - 0.5) / 0.5
            min_pwm = cls._lerp(PWM_TURN_MIN, PWM_STRONG_TURN_MIN, t)
            default_pwm = cls._lerp(PWM_TURN_DEFAULT, PWM_STRONG_TURN_DEFAULT, t)
        return min(MOTOR_MAX_PWM, round(cls._lerp(min_pwm, default_pwm, magnitude)))

    def apply_direct(self, throttle, steering):
        self.motor_direction = "REVERSE" if throttle < 0 else "FORWARD"
        self.motor_pwm = self.throttle_to_pwm(throttle, steering)
        self.applied_throttle = throttle
        self.applied_steering = steering
        self.servo_angle = self.steering_to_angle(steering)
        self.last_direct_apply = time.monotonic()

    def build_hello(self):
        return {
            "version": VERSION, "type": "HELLO", "car_id": CAR_ID,
            "boot_id": self.boot_id, "firmware_version": "mock-esp32",
            "state": "SYNCING", "previous_state": "BOOT", "previous_session_id": "",
            "last_processed_cmd_seq": self.last_processed_cmd_seq,
            "current_route_id": -1, "current_waypoint_id": -1, "current_phase": "NONE",
            "target_loaded": False, "resume_allowed": False,
            "motor_stopped": True, "error_code": self.error_code,
        }

    def build_status(self, result="NONE", rejected_seq=0, duplicate=False):
        self.status_seq += 1
        base = {
            "version": VERSION, "type": "STATUS", "car_id": CAR_ID,
            "boot_id": self.boot_id, "session_id": self.session_id,
            "status_seq": self.status_seq,
            "last_processed_cmd_seq": self.last_processed_cmd_seq,
            "rejected_seq": rejected_seq, "command_result": result,
            "state": self.state, "mode": self.mode,
            "target_loaded": False, "resume_allowed": False,
            "wait_reason": self.wait_reason, "error_code": self.error_code,
        }
        if self.mode == "REMOTE_DIRECT":
            base.update({
                "latest_control_seq": self.applied_control_seq,
                "applied_throttle": round(self.applied_throttle, 3),
                "applied_steering": round(self.applied_steering, 3),
                "encoder_count": self.encoder_count,
            })
        else:
            base.update({"route_id": -1, "waypoint_id": -1, "phase": "NONE"})
        return base



async def run(host: str, port: int, actuator_output: bool):
    esp = MockEsp32(actuator_output)
    reader, writer = await asyncio.open_connection(host, port)
    print(f"[mock-esp32] connected to {host}:{port} boot_id={esp.boot_id}")

    async def send(msg):
        writer.write((json.dumps(msg, separators=(",", ":")) + "\n").encode())
        await writer.drain()

    async def reliable(msg) -> None:
        """Idempotent reliable-command handling like the firmware."""
        seq = msg["seq"]
        fp = esp.fingerprint(msg)
        if seq == esp.last_processed_cmd_seq:
            if fp == esp.last_fp:
                await send(esp.build_status(result=esp.last_result, duplicate=True))
            else:
                await send(esp.build_status(result="SEQ_CONFLICT", rejected_seq=seq))
            return
        if seq < esp.last_processed_cmd_seq:
            await send(esp.build_status(result="STALE_SEQ", rejected_seq=seq))
            return

        result = "ACCEPTED"
        t = msg["type"]
        if t == "SET_MODE":
            if esp.state in ("EMERGENCY_STOP", "ERROR", "COMM_TIMEOUT", "MOVING"):
                result = "INVALID_STATE"
            else:
                esp.mode = msg["mode"]
                if esp.mode == "REMOTE_DIRECT":
                    esp.applied_control_seq = 0
        elif t == "STOP":
            esp.safe_stop("STOP", emergency=True)
        elif t == "RESET":
            if esp.state in ("EMERGENCY_STOP", "ERROR"):
                esp.state = "READY"
                esp.mode = "WAYPOINT_AUTO"
                esp.wait_reason = "NONE"
                esp.error_code = "NONE"
            else:
                result = "INVALID_STATE"
        esp.last_processed_cmd_seq = seq
        esp.last_fp = fp
        esp.last_result = result
        print(f"[mock-esp32] RELIABLE {t} seq={seq} -> {result} (state={esp.state} mode={esp.mode})")
        await send(esp.build_status(result=result))

    def direct(msg):
        if not esp.session_active or msg.get("session_id") != esp.session_id:
            return
        if esp.mode != "REMOTE_DIRECT":
            return
        if esp.state in ("EMERGENCY_STOP", "ERROR", "COMM_TIMEOUT"):
            return
        cseq = msg["control_seq"]
        if cseq <= esp.applied_control_seq:
            return  # stale control_seq dropped
        esp.applied_control_seq = cseq
        thr, steer = msg["throttle"], msg["steering"]
        esp.apply_direct(thr, steer)
        if esp.motor_pwm > 0:
            esp.state = "MOVING"
            esp.wait_reason = "NONE"
        else:
            esp.state = "READY"
            esp.wait_reason = "NONE"

    async def rx_loop():
        buf = b""
        while True:
            chunk = await reader.read(512)
            if not chunk:
                print("[mock-esp32] bridge closed connection")
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                msg = json.loads(line.decode())
                t = msg.get("type")
                if t == "HELLO_ACK":
                    esp.session_id = msg["session_id"]
                    esp.session_active = True
                    esp.last_processed_cmd_seq = msg.get("command_seq_start", 1) - 1
                    esp.last_heartbeat = time.monotonic()
                    if msg.get("result") == "HOLD":
                        esp.state = "SYNCING"
                        print(f"[mock-esp32] HELLO_ACK HOLD session={esp.session_id}")
                        await send(esp.build_status(result="HOLD"))
                    else:
                        esp.state = "READY"
                        esp.mode = "WAYPOINT_AUTO"
                        print(f"[mock-esp32] HELLO_ACK session={esp.session_id} -> READY")
                        await send(esp.build_status(result="ACCEPTED"))
                elif t == "HEARTBEAT":
                    esp.last_heartbeat = time.monotonic()
                elif t in ("SET_MODE", "STOP", "RESET"):
                    await reliable(msg)
                elif t == "DIRECT_CONTROL":
                    direct(msg)

    async def periodic():
        # HELLO retransmit until session, then periodic STATUS + timeouts.
        next_status = time.monotonic()
        while True:
            now = time.monotonic()
            if not esp.session_active:
                await send(esp.build_hello())
                await asyncio.sleep(0.5)
                continue
            # Crude encoder simulation for bridge/status validation only.
            if esp.state == "MOVING" and esp.motor_pwm > 0:
                direction = -1 if esp.motor_direction == "REVERSE" else 1
                esp.encoder_count += direction * max(1, esp.motor_pwm // 8)

            # DIRECT_CONTROL timeout (only while actively MOVING).
            if (esp.mode == "REMOTE_DIRECT" and esp.state == "MOVING"
                    and esp.last_direct_apply
                    and now - esp.last_direct_apply >= DIRECT_TIMEOUT_S):
                esp.safe_stop("DIRECT_CONTROL_TIMEOUT",
                              wait_reason="DIRECT_CONTROL_TIMEOUT")
                print("[mock-esp32] DIRECT_CONTROL timeout -> WAITING")
                await send(esp.build_status(result="NONE"))
            # HEARTBEAT timeout.
            if esp.session_active and now - esp.last_heartbeat >= HEARTBEAT_TIMEOUT_S:
                esp.safe_stop("COMM_TIMEOUT", comm=True)
                print("[mock-esp32] HEARTBEAT timeout -> COMM_TIMEOUT")
                await send(esp.build_status(result="NONE"))
                esp.last_heartbeat = now  # avoid spamming
            if now >= next_status:
                next_status = now + STATUS_PERIOD_S
                await send(esp.build_status(result="NONE"))
            await asyncio.sleep(0.02)

    try:
        await asyncio.gather(rx_loop(), periodic())
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        writer.close()


def main():
    ap = argparse.ArgumentParser(description="Mock ESP32 for the REMOTE_DIRECT bridge")
    ap.add_argument("--host", default=HOST_DEFAULT)
    ap.add_argument("--port", type=int, default=PORT_DEFAULT)
    ap.add_argument("--actuator-output", action="store_true",
                    help="mark the mock as physical-output simulation (not sent in compact STATUS)")
    args = ap.parse_args()
    try:
        asyncio.run(run(args.host, args.port, args.actuator_output))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
