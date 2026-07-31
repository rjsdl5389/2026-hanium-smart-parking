"""Tkinter press-and-hold WASD window for REMOTE_DIRECT v5.3."""

from __future__ import annotations

import queue
import time
import tkinter as tk
from tkinter import ttk
from typing import Callable

from wasd_logic import (
    STEERING_RAMP_INTERVAL_MS,
    advance_steering,
    compute_drive_intent,
    expected_actuator,
    steering_direction,
)

COMMAND_COOLDOWN_S = 0.75


class WasdControlWindow:
    """Control window with deadman keys, steering ramp and command debouncing."""

    def __init__(
        self,
        root: tk.Tk,
        *,
        set_drive: Callable[[float, float], None],
        set_mode_remote: Callable[[], None],
        emergency_stop: Callable[[], None],
        reset: Callable[[], None],
        shutdown: Callable[[], None],
        status_queue: "queue.Queue[dict]",
        connection_queue: "queue.Queue[bool]",
        build_id: str = "v5.3",
    ) -> None:
        self.root = root
        self.set_drive = set_drive
        self.set_mode_remote = set_mode_remote
        self.emergency_stop = emergency_stop
        self.reset_command = reset
        self.shutdown = shutdown
        self.status_queue = status_queue
        self.connection_queue = connection_queue
        self.build_id = build_id

        self.pressed: set[str] = set()
        self.command_keys_down: set[str] = set()
        self.current_steering = 0.0
        self.last_sent = (None, None)
        self.last_action_at: dict[str, float] = {}
        self.latest_state = "-"
        self.latest_mode = "-"
        self.remote_armed = False
        self.pending_mode_seq: int | None = None

        root.title(f"Hanium RC Car — REMOTE_DIRECT {build_id}")
        root.geometry("680x560")
        root.minsize(620, 510)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.connection_var = tk.StringVar(value="ESP32: 연결 대기")
        self.state_var = tk.StringVar(value="state: -")
        self.mode_var = tk.StringVar(value="mode: -")
        self.arm_var = tk.StringVar(value="stream: DISARMED")
        self.drive_var = tk.StringVar(value="STOP / CENTER")
        self.values_var = tk.StringVar(value="throttle=0.0  steering=0.0")
        self.output_var = tk.StringVar(value="예상 PWM=0  servo=86.0°  DIR=FORWARD")
        self.encoder_var = tk.StringVar(value="encoder: -")
        self.notice_var = tk.StringVar(value="READY 확인 후 M을 한 번만 누르세요.")

        outer = ttk.Frame(root, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="RC카 WASD 직접제어", font=("Malgun Gothic", 18, "bold")).pack(anchor="w")
        ttk.Label(outer, text=f"bridge build: {build_id}").pack(anchor="w")
        ttk.Label(outer, textvariable=self.connection_var, font=("Malgun Gothic", 11, "bold")).pack(anchor="w", pady=(6, 0))

        status = ttk.Frame(outer)
        status.pack(fill="x", pady=8)
        ttk.Label(status, textvariable=self.state_var).grid(row=0, column=0, sticky="w", padx=(0, 24))
        ttk.Label(status, textvariable=self.mode_var).grid(row=0, column=1, sticky="w", padx=(0, 24))
        ttk.Label(status, textvariable=self.arm_var).grid(row=0, column=2, sticky="w")
        ttk.Label(status, textvariable=self.encoder_var).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        drive_box = ttk.LabelFrame(outer, text="현재 명령", padding=12)
        drive_box.pack(fill="x", pady=8)
        ttk.Label(drive_box, textvariable=self.drive_var, font=("Consolas", 18, "bold")).pack()
        ttk.Label(drive_box, textvariable=self.values_var, font=("Consolas", 12)).pack(pady=(6, 0))
        ttk.Label(drive_box, textvariable=self.output_var, font=("Consolas", 11)).pack(pady=(4, 0))

        keys = ttk.LabelFrame(outer, text="조작", padding=12)
        keys.pack(fill="x", pady=8)
        instruction = (
            "W 전진 / S 후진, A·D를 오래 누를수록 10%씩 조향 증가\n"
            "Shift+A/D는 증가속도 2배, 좌50°·중앙86°·우122°\n"
            "W+S 정지, A+D 중앙, M 모드, Space STOP, R RESET, Q 종료\n"
            "STOP 복구: Space → R → READY 확인 → M 1회 → W"
        )
        ttk.Label(keys, text=instruction, justify="left").pack(anchor="w")

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=10)
        ttk.Button(buttons, text="M  REMOTE_DIRECT", command=self._mode).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="R  RESET", command=self._reset).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="SPACE  비상 STOP", command=self._stop).pack(side="left")

        ttk.Label(outer, textvariable=self.notice_var, wraplength=630, foreground="#8a3b00").pack(anchor="w", pady=(8, 0))
        ttk.Label(outer, text="※ 비제로 WASD 입력은 stream=ARMED일 때만 전송됩니다.").pack(anchor="w", pady=(8, 0))

        root.bind_all("<KeyPress>", self._on_key_press)
        root.bind_all("<KeyRelease>", self._on_key_release)
        root.bind("<FocusOut>", self._on_focus_out)
        root.after(100, self._poll_backend)
        root.after(STEERING_RAMP_INTERVAL_MS, self._steering_ramp_tick)
        root.after(150, root.focus_force)

    @staticmethod
    def _normalize_key(keysym: str) -> str:
        key = keysym.lower()
        if key in ("shift_l", "shift_r"):
            return key
        return "space" if key == "space" else key

    def _allow_action(self, name: str) -> bool:
        now = time.monotonic()
        previous = self.last_action_at.get(name, -1e9)
        if now - previous < COMMAND_COOLDOWN_S:
            self.notice_var.set(f"{name.upper()} 중복 입력 무시")
            return False
        self.last_action_at[name] = now
        return True

    def _on_key_press(self, event: tk.Event) -> None:
        key = self._normalize_key(str(event.keysym))
        if key in {"space", "m", "r", "q"}:
            if key in self.command_keys_down:
                return
            self.command_keys_down.add(key)
            if key == "space":
                self._stop()
            elif key == "m":
                self._mode()
            elif key == "r":
                self._reset()
            else:
                self._on_close()
            return

        if key not in {"w", "a", "s", "d", "shift_l", "shift_r"}:
            return
        if key in self.pressed:
            return
        self.pressed.add(key)
        if key in {"a", "d"}:
            self.current_steering = advance_steering(self.current_steering, self.pressed)
        self._apply_keys()

    def _on_key_release(self, event: tk.Event) -> None:
        key = self._normalize_key(str(event.keysym))
        self.command_keys_down.discard(key)
        if key not in self.pressed:
            return
        self.pressed.discard(key)
        if key in {"a", "d"}:
            if steering_direction(self.pressed) == 0:
                self.current_steering = 0.0
            else:
                self.current_steering = advance_steering(0.0, self.pressed)
        self._apply_keys()

    def _steering_ramp_tick(self) -> None:
        direction = steering_direction(self.pressed)
        next_steering = advance_steering(self.current_steering, self.pressed) if direction != 0 else 0.0
        if next_steering != self.current_steering:
            self.current_steering = next_steering
            self._apply_keys()
        self.root.after(STEERING_RAMP_INTERVAL_MS, self._steering_ramp_tick)

    def _on_focus_out(self, _event: tk.Event) -> None:
        self._clear_drive("창 포커스 이탈 → 정지")

    def _apply_keys(self) -> None:
        intent = compute_drive_intent(self.pressed, self.current_steering)
        current = (intent.throttle, intent.steering)
        if current != self.last_sent:
            self.set_drive(*current)
            self.last_sent = current
        duty, angle, direction = expected_actuator(*current)
        self.drive_var.set(intent.label)
        self.values_var.set(f"throttle={intent.throttle:+.1f}  steering={intent.steering:+.1f}")
        self.output_var.set(f"예상 PWM={duty}  servo={angle:.1f}°  DIR={direction}")

    def _clear_drive(self, notice: str | None = None) -> None:
        self.pressed.clear()
        self.current_steering = 0.0
        self.set_drive(0.0, 0.0)
        self.last_sent = (0.0, 0.0)
        self.drive_var.set("STOP / CENTER")
        self.values_var.set("throttle=+0.0  steering=+0.0")
        self.output_var.set("예상 PWM=0  servo=86.0°  DIR=FORWARD")
        if notice:
            self.notice_var.set(notice)

    def _refocus(self) -> None:
        self.root.after_idle(self.root.focus_force)

    def _mode(self) -> None:
        if not self._allow_action("mode"):
            return
        self._clear_drive()
        self.set_mode_remote()
        self.notice_var.set("REMOTE_DIRECT 요청/재무장. ARMED 표시 전까지 WASD는 중립 유지.")
        self._refocus()

    def _stop(self) -> None:
        if not self._allow_action("stop"):
            return
        self._clear_drive()
        self.emergency_stop()
        self.notice_var.set("비상 STOP 전송. 복구는 R → READY → M 순서입니다.")
        self._refocus()

    def _reset(self) -> None:
        if not self._allow_action("reset"):
            return
        self._clear_drive()
        self.reset_command()
        self.notice_var.set("RESET 요청. READY/WAYPOINT_AUTO 확인 후 M을 한 번 누르세요.")
        self._refocus()

    def _poll_backend(self) -> None:
        try:
            while True:
                connected = self.connection_queue.get_nowait()
                self.connection_var.set("ESP32: 연결됨" if connected else "ESP32: 연결 끊김")
        except queue.Empty:
            pass

        try:
            while True:
                msg = self.status_queue.get_nowait()
                self.latest_state = str(msg.get("state", "-"))
                self.latest_mode = str(msg.get("mode", "-"))
                self.remote_armed = bool(msg.get("bridge_direct_streaming", False))
                self.pending_mode_seq = msg.get("bridge_pending_mode_seq")
                self.state_var.set(f"state: {self.latest_state}")
                self.mode_var.set(f"mode: {self.latest_mode}")
                self.arm_var.set("stream: ARMED" if self.remote_armed else "stream: DISARMED")
                enc = msg.get("encoder_count", "-")
                denc = msg.get("encoder_delta", 0)
                self.encoder_var.set(f"encoder: {enc}   delta: {denc}")
                if self.latest_state == "EMERGENCY_STOP":
                    self.notice_var.set("EMERGENCY_STOP: R → READY 확인 → M 1회")
                elif self.latest_state == "COMM_TIMEOUT":
                    self.notice_var.set("COMM_TIMEOUT: 재연결 후 자동 재출발하지 않습니다.")
                elif msg.get("wait_reason") == "DIRECT_CONTROL_TIMEOUT":
                    self.notice_var.set("DIRECT_CONTROL_TIMEOUT 안전정지. M으로 중립 재무장 후 입력하세요.")
                elif self.remote_armed and self.latest_mode == "REMOTE_DIRECT":
                    self.notice_var.set("REMOTE_DIRECT ARMED: WASD 입력 가능")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_backend)

    def _on_close(self) -> None:
        self._clear_drive()
        self.emergency_stop()
        self.root.after(300, self._finish_close)

    def _finish_close(self) -> None:
        self.shutdown()
        self.root.destroy()
