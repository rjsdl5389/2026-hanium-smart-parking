"""Tkinter REMOTE_DIRECT launcher with an asyncio TCP backend."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import queue
import threading
import tkinter as tk
from pathlib import Path
from typing import Any

import config
import controller as controller_module
import wasd_gui as wasd_gui_module
from controller import BRIDGE_BUILD_ID, Controller
from server import BridgeServer
from wasd_gui import WasdControlWindow


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


class AsyncBridgeBackend:
    def __init__(self) -> None:
        self.status_queue: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self.connection_queue: "queue.Queue[bool]" = queue.Queue()
        self._thread = threading.Thread(
            target=self._thread_main,
            name="BridgeAsyncio",
            daemon=True,
        )
        self._ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._shutdown_event: asyncio.Event | None = None
        self._controller: Controller | None = None
        self._startup_error: BaseException | None = None

    def start(self) -> None:
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError("bridge backend startup timed out")
        if self._startup_error is not None:
            raise RuntimeError(f"bridge backend failed: {self._startup_error}")

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._amain())
        except BaseException as exc:
            self._startup_error = exc
            logging.getLogger("bridge.gui").exception("async backend failed")
            self._ready.set()

    async def _amain(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._shutdown_event = asyncio.Event()
        controller = Controller()
        self._controller = controller
        controller.add_status_listener(lambda msg: self.status_queue.put(dict(msg)))
        controller.add_connection_listener(
            lambda connected: self.connection_queue.put(bool(connected))
        )

        server = BridgeServer(controller)
        await server.start()
        tasks = [
            asyncio.create_task(controller.heartbeat_loop(), name="heartbeat"),
            asyncio.create_task(controller.direct_control_loop(), name="direct_control"),
            asyncio.create_task(controller.reliable_resend_loop(), name="reliable_resend"),
        ]
        log = logging.getLogger("bridge.gui")
        log.info("BUILD %s", BRIDGE_BUILD_ID)
        log.info("controller.py loaded from %s", Path(controller_module.__file__).resolve())
        log.info("wasd_gui.py loaded from %s", Path(wasd_gui_module.__file__).resolve())
        log.info("GUI bridge ready on port %d. Press M only once after READY.", config.PORT)
        self._ready.set()
        await self._shutdown_event.wait()

        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await server.close()

    def _call(self, fn, *args) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(fn, *args)

    def _coro(self, coro_factory) -> None:
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(coro_factory(), self._loop)

    def set_drive(self, throttle: float, steering: float) -> None:
        if self._controller is not None:
            self._call(self._controller.cmd_set_drive, throttle, steering)

    def mode_remote(self) -> None:
        if self._controller is not None:
            self._coro(self._controller.cmd_mode_remote)

    def emergency_stop(self) -> None:
        if self._controller is not None:
            self._coro(self._controller.cmd_stop)

    def reset(self) -> None:
        if self._controller is not None:
            self._coro(self._controller.cmd_reset)

    def shutdown(self) -> None:
        if self._loop is not None and self._shutdown_event is not None:
            self._loop.call_soon_threadsafe(self._shutdown_event.set)


def main() -> None:
    _configure_logging()
    backend = AsyncBridgeBackend()
    backend.start()

    root = tk.Tk()
    WasdControlWindow(
        root,
        set_drive=backend.set_drive,
        set_mode_remote=backend.mode_remote,
        emergency_stop=backend.emergency_stop,
        reset=backend.reset,
        shutdown=backend.shutdown,
        status_queue=backend.status_queue,
        connection_queue=backend.connection_queue,
        build_id=BRIDGE_BUILD_ID,
    )
    root.mainloop()


if __name__ == "__main__":
    main()
