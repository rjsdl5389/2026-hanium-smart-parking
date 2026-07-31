"""Asyncio TCP server for the REMOTE_DIRECT bridge.

* ``asyncio.start_server`` on 0.0.0.0:5000, persistent connection.
* NDJSON receive buffer: accumulate bytes, split on ``\\n``, parse complete
  lines only, discard oversized/garbage lines.
* Single car (CAR_01): a new accepted connection supersedes any previous one;
  late messages from the old socket are ignored because the controller drops
  the old session and STATUS from a stale session_id is filtered.

The controller holds all protocol/session logic; this file is only transport.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import config
import protocol
from controller import Controller

log = logging.getLogger("bridge.server")


class BridgeServer:
    def __init__(self, controller: Controller) -> None:
        self.controller = controller
        self._active_writer: asyncio.StreamWriter | None = None
        self._server: asyncio.AbstractServer | None = None

    async def start(self, host: str | None = None, port: int | None = None) -> asyncio.AbstractServer:
        self._server = await asyncio.start_server(
            self._handle_client,
            host=config.HOST if host is None else host,
            port=config.PORT if port is None else port)
        sockets = ", ".join(str(s.getsockname()) for s in self._server.sockets or [])
        log.info("TCP bridge listening on %s (car_id=%s, protocol v%d)",
                 sockets, config.CAR_ID, config.PROTOCOL_VERSION)
        return self._server


    async def close(self) -> None:
        """Close the listening socket and the active ESP32 connection."""
        if self._active_writer is not None and not self._active_writer.is_closing():
            self._active_writer.close()
            with contextlib.suppress(Exception):
                await self._active_writer.wait_closed()
        self._active_writer = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(self, reader: asyncio.StreamReader,
                             writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        log.info("ESP32 connected from %s", peer)

        # Supersede any previous connection (single-car bridge). Invalidate the
        # old session BEFORE attaching the new socket so heartbeat/direct tasks
        # cannot leak an old session_id onto the fresh connection.
        if self._active_writer is not None and not self._active_writer.is_closing():
            log.warning("New connection supersedes previous socket; closing old one.")
            try:
                self._active_writer.close()
            except Exception:  # noqa: BLE001
                pass
            self.controller.detach()
        self._active_writer = writer

        send_lock = asyncio.Lock()

        async def sender(message: dict[str, Any]) -> None:
            if writer.is_closing():
                return
            # HEARTBEAT, reliable resend and DIRECT_CONTROL tasks share one
            # StreamWriter. Serialize each complete NDJSON write+drain so two
            # coroutines cannot race on transport backpressure.
            async with send_lock:
                if writer.is_closing():
                    return
                writer.write(protocol.encode_line(message))
                await writer.drain()

        self.controller.attach(sender)

        buffer = bytearray()
        try:
            while not reader.at_eof():
                chunk = await reader.read(512)
                if not chunk:
                    break
                buffer.extend(chunk)
                if len(buffer) > config.STREAM_BUFFER_LIMIT:
                    log.error("RX stream buffer overflow (%dB); resetting.", len(buffer))
                    buffer.clear()
                    continue
                await self._drain_lines(buffer)
        except (ConnectionResetError, asyncio.IncompleteReadError):
            log.warning("ESP32 connection reset by peer.")
        except Exception as exc:  # noqa: BLE001
            log.warning("RX loop error: %s", exc)
        finally:
            log.warning("ESP32 disconnected (%s)", peer)
            if self._active_writer is writer:
                self._active_writer = None
                self.controller.detach()
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass

    async def _drain_lines(self, buffer: bytearray) -> None:
        while True:
            nl = buffer.find(b"\n")
            if nl == -1:
                if len(buffer) > config.RX_MAX_LINE_BYTES:
                    log.error("Inbound line exceeds %dB with no newline; resetting.",
                              config.RX_MAX_LINE_BYTES)
                    buffer.clear()
                return
            raw = bytes(buffer[:nl])
            del buffer[:nl + 1]
            if not raw or len(raw) > config.RX_MAX_LINE_BYTES:
                if raw:
                    log.error("Oversized inbound line discarded (%dB).", len(raw))
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                log.warning("Non-UTF8 line discarded.")
                continue
            try:
                message = protocol.parse_line(text)
            except protocol.ProtocolError as exc:
                log.warning("Protocol reject: %s | %s", exc, text)
                continue
            await self.controller.on_message(message)
