"""Operator input for the bridge: keyboard (Windows) and line commands.

Runs in a dedicated OS thread so blocking key/line reads never stall the asyncio
event loop. Every intent is marshalled back onto the loop with
``loop.call_soon_threadsafe`` so all session mutation happens on the loop thread.

Keyboard (Windows, via stdlib ``msvcrt``):
    W forward+   S slow/0   A steer left   D steer right   C center
    Space/X STOP   R RESET   M SET_MODE REMOTE_DIRECT   Q quit

Line commands (all platforms):
    mode remote | forward <v> | throttle <v> | steer <v> | center |
    neutral | stop | reset | status | help | quit
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
from typing import Callable

import config
from controller import Controller

log = logging.getLogger("bridge.cli")

try:
    import msvcrt  # type: ignore
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False


HELP_TEXT = """
commands:
  mode remote     SET_MODE(REMOTE_DIRECT)         (key: M)
  forward <v>     throttle forward, v in 0..1     (key: W adds +%.2f)
  throttle <v>    set throttle, v in -1..1
  steer <v>       set steering, v in -1..1        (keys: A/D)
  straight        throttle=1.0, steering=0.0       (PWM 23)
  left weak       throttle=1.0, steering=-0.5      (60°, PWM 40)
  right weak      throttle=1.0, steering=+0.5      (112°, PWM 40)
  left strong     throttle=1.0, steering=-1.0      (30°, PWM 50)
  right strong    throttle=1.0, steering=+1.0      (122°, PWM 50)
  center          steering -> 0                    (key: C)
  neutral         throttle -> 0 (keep steering)    (key: S)
  stop            STOP -> EMERGENCY_STOP           (keys: Space/X)
  reset           RESET -> READY                   (key: R)
  status          print latest STATUS
  stream pause    stop DIRECT_CONTROL only (firmware timeout test)
  stream resume   resume DIRECT_CONTROL after timeout test
  help            this help
  quit            stop the bridge                  (key: Q)
""" % (config.THROTTLE_STEP,)


class OperatorConsole:
    def __init__(self, loop: asyncio.AbstractEventLoop, controller: Controller,
                 request_shutdown: Callable[[], None]) -> None:
        self.loop = loop
        self.controller = controller
        self.request_shutdown = request_shutdown
        self._thread = threading.Thread(target=self._run, name="OperatorConsole",
                                        daemon=True)

    def start(self) -> None:
        self._thread.start()

    # -- marshalling helpers ------------------------------------------------
    def _call_async(self, coro_factory: Callable[[], "asyncio.coroutines"]) -> None:
        def schedule() -> None:
            asyncio.ensure_future(coro_factory())
        self.loop.call_soon_threadsafe(schedule)

    def _call_sync(self, fn: Callable[[], None]) -> None:
        self.loop.call_soon_threadsafe(fn)

    # -- dispatch -----------------------------------------------------------
    def dispatch_line(self, line: str) -> bool:
        """Handle a typed command line. Return False to request shutdown."""
        line = line.strip()
        if not line:
            return True
        parts = line.split()
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None

        if cmd in ("quit", "exit"):
            self.request_shutdown()
            return False
        if cmd == "help":
            print(HELP_TEXT)
            return True
        if cmd == "status":
            self._call_sync(lambda: print(self.controller.status_line()))
            return True
        if cmd == "stream" and arg == "pause":
            self._call_sync(self.controller.cmd_pause_direct_stream)
            return True
        if cmd == "stream" and arg == "resume":
            self._call_sync(self.controller.cmd_resume_direct_stream)
            return True
        if cmd == "mode" and arg == "remote":
            self._call_async(self.controller.cmd_mode_remote)
            return True
        if cmd == "stop":
            self._call_async(self.controller.cmd_stop)
            return True
        if cmd == "reset":
            self._call_async(self.controller.cmd_reset)
            return True
        if cmd == "straight":
            self._call_sync(lambda: self.controller.cmd_set_drive(1.0, 0.0))
            return True
        if cmd in ("left", "right") and arg in ("weak", "strong"):
            steering = -0.5 if cmd == "left" and arg == "weak" else \
                       -1.0 if cmd == "left" else \
                        0.5 if arg == "weak" else 1.0
            self._call_sync(lambda s=steering: self.controller.cmd_set_drive(1.0, s))
            return True
        if cmd == "center":
            self._call_sync(self.controller.cmd_center)
            return True
        if cmd == "neutral":
            self._call_sync(self.controller.cmd_neutral)
            return True
        if cmd in ("forward", "throttle") and arg is not None:
            try:
                value = float(arg)
            except ValueError:
                print(f"invalid number: {arg}")
                return True
            self._call_sync(lambda v=value: self.controller.cmd_set_throttle(v))
            return True
        if cmd == "steer" and arg is not None:
            try:
                value = float(arg)
            except ValueError:
                print(f"invalid number: {arg}")
                return True
            self._call_sync(lambda v=value: self.controller.cmd_set_steering(v))
            return True

        print(f"unknown command: {line!r} (type 'help')")
        return True

    def dispatch_key(self, key: str) -> bool:
        """Handle a single keypress. Return False to request shutdown."""
        key = key.lower()
        if key == config.KEY_QUIT:
            self.request_shutdown()
            return False
        if key == config.KEY_FORWARD:
            self._call_sync(lambda: self.controller.cmd_nudge_throttle(config.THROTTLE_STEP))
        elif key == config.KEY_SLOW:
            self._call_sync(self.controller.cmd_neutral)
        elif key == config.KEY_LEFT:
            self._call_sync(lambda: self.controller.cmd_nudge_steering(-config.STEERING_STEP))
        elif key == config.KEY_RIGHT:
            self._call_sync(lambda: self.controller.cmd_nudge_steering(config.STEERING_STEP))
        elif key == config.KEY_CENTER:
            self._call_sync(self.controller.cmd_center)
        elif key in (config.KEY_STOP_A, config.KEY_STOP_B):
            self._call_async(self.controller.cmd_stop)
        elif key == config.KEY_RESET:
            self._call_async(self.controller.cmd_reset)
        elif key == config.KEY_MODE_REMOTE:
            self._call_async(self.controller.cmd_mode_remote)
        return True

    # -- thread body --------------------------------------------------------
    def _run(self) -> None:
        if HAS_MSVCRT:
            log.info("Keyboard control active (Windows). Press 'help key' keys; "
                     "type is disabled in key mode. Q to quit.")
            self._run_keyboard()
        else:
            log.info("Line-command mode (no msvcrt). Type 'help' then Enter. "
                     "On Windows you also get W/A/S/D live keys.")
            self._run_lines()

    def _run_keyboard(self) -> None:
        # Windows console does not expose key-up events via msvcrt. We therefore
        # treat the OS key-repeat stream as a deadman signal: while W/A/D/S/C is
        # held, repeated keypresses refresh the timer; after the repeats stop for
        # KEYBOARD_DEADMAN_S we force throttle back to zero.
        print(HELP_TEXT)
        last_drive_key_at = 0.0
        deadman_neutral_sent = True
        drive_keys = {
            config.KEY_FORWARD, config.KEY_SLOW, config.KEY_LEFT,
            config.KEY_RIGHT, config.KEY_CENTER,
        }
        while True:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    if msvcrt.kbhit():
                        msvcrt.getwch()
                    continue
                if ch == ";":
                    try:
                        line = input("cmd> ")
                    except EOFError:
                        self.request_shutdown()
                        return
                    if not self.dispatch_line(line):
                        return
                    continue
                if ch.lower() in drive_keys:
                    last_drive_key_at = time.monotonic()
                    deadman_neutral_sent = False
                if not self.dispatch_key(ch):
                    return
            else:
                if (not deadman_neutral_sent and last_drive_key_at > 0.0 and
                        time.monotonic() - last_drive_key_at >= config.KEYBOARD_DEADMAN_S):
                    self._call_sync(self.controller.cmd_neutral)
                    deadman_neutral_sent = True
                    log.warning("Keyboard deadman: no repeated drive key -> throttle 0")
                time.sleep(0.02)

    def _run_lines(self) -> None:
        print(HELP_TEXT)
        while True:
            try:
                line = input("bridge> ")
            except EOFError:
                self.request_shutdown()
                return
            if not self.dispatch_line(line):
                return
