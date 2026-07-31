"""Entry point for the REMOTE_DIRECT notebook->ESP32 control bridge.

Run:
    python bridge.py

Standalone process. No Django, no DB, no Redis, no REST/WebSocket. Starts an
asyncio TCP server on 0.0.0.0:5000, drives one CAR_01 over persistent NDJSON TCP,
and gives you keyboard/CLI control for wireless RC driving (for YOLO data
collection and map testing).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

import config
from cli import OperatorConsole
from controller import Controller
from server import BridgeServer


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


async def _amain() -> None:
    controller = Controller()
    server = BridgeServer(controller)
    await server.start()

    loop = asyncio.get_running_loop()
    shutdown = asyncio.Event()

    console = OperatorConsole(loop, controller, request_shutdown=lambda: loop.call_soon_threadsafe(shutdown.set))
    console.start()

    tasks = [
        asyncio.create_task(controller.heartbeat_loop(), name="heartbeat"),
        asyncio.create_task(controller.direct_control_loop(), name="direct_control"),
        asyncio.create_task(controller.reliable_resend_loop(), name="reliable_resend"),
    ]

    logging.getLogger("bridge").info(
        "Bridge ready. Waiting for ESP32 (CAR_01) to connect on port %d. "
        "Type 'help' (or press keys on Windows).", config.PORT)

    await shutdown.wait()
    logging.getLogger("bridge").info("Shutting down...")
    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task


def main() -> None:
    _configure_logging()
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
