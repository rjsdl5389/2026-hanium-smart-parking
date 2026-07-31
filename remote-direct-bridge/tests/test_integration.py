"""End-to-end test over a real loopback TCP socket with a mock ESP32 client.

Exercises the actual BridgeServer + Controller + asyncio framing:
HELLO -> HELLO_ACK (boot_id echo) -> SET_MODE received -> STATUS ack ->
DIRECT_CONTROL streamed -> HEARTBEAT streamed.
"""

import asyncio
import json
import unittest

import config
from controller import Controller
from server import BridgeServer


async def read_message(reader: asyncio.StreamReader, timeout: float = 2.0) -> dict:
    line = await asyncio.wait_for(reader.readline(), timeout=timeout)
    if not line:
        raise AssertionError("connection closed while awaiting a message")
    return json.loads(line.decode("utf-8").strip())


async def read_until(reader: asyncio.StreamReader, mtype: str, timeout: float = 3.0) -> dict:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        msg = await read_message(reader, timeout=deadline - loop.time())
        if msg.get("type") == mtype:
            return msg
    raise AssertionError(f"did not receive {mtype} within {timeout}s")


def hello_line(boot_id="BOOT42") -> bytes:
    return (json.dumps({
        "version": 1, "type": "HELLO", "car_id": config.CAR_ID,
        "boot_id": boot_id, "firmware_version": "0.2.0-day3-v1",
        "state": "SYNCING", "previous_state": "BOOT", "previous_session_id": "",
        "last_processed_cmd_seq": 0, "current_route_id": -1,
        "current_waypoint_id": -1, "current_phase": "NONE",
        "target_loaded": False, "resume_allowed": False,
        "motor_stopped": True, "error_code": "NONE",
    }) + "\n").encode()


def status_line(session_id, **overrides) -> bytes:
    base = {
        "version": 1, "type": "STATUS", "car_id": config.CAR_ID, "boot_id": "BOOT42",
        "session_id": session_id, "status_seq": 1, "last_processed_cmd_seq": 0,
        "rejected_seq": 0, "command_result": "NONE",
        "state": "READY", "mode": "WAYPOINT_AUTO", "target_loaded": False,
        "resume_allowed": False, "wait_reason": "NONE", "error_code": "NONE",
    }
    base.update(overrides)
    return (json.dumps(base) + "\n").encode()


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.controller = Controller()
        self.server = BridgeServer(self.controller)
        srv = await self.server.start(host="127.0.0.1", port=0)
        self.port = srv.sockets[0].getsockname()[1]
        self.tasks = [
            asyncio.create_task(self.controller.heartbeat_loop()),
            asyncio.create_task(self.controller.direct_control_loop()),
            asyncio.create_task(self.controller.reliable_resend_loop()),
        ]

    async def asyncTearDown(self):
        for t in self.tasks:
            t.cancel()
        if self.server._server:
            self.server._server.close()

    async def test_full_handshake_and_streaming(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)

        # 1) HELLO -> HELLO_ACK echoing boot_id
        writer.write(hello_line("BOOTZZ"))
        await writer.drain()
        ack = await read_until(reader, "HELLO_ACK")
        self.assertEqual(ack["boot_id"], "BOOTZZ")
        session_id = ack["session_id"]
        self.assertTrue(session_id.startswith("S"))

        # 2) initial READY snapshot gates mode changes
        writer.write(status_line(session_id, status_seq=1, state="READY", mode="WAYPOINT_AUTO"))
        await writer.drain()
        await asyncio.sleep(0.05)

        # 3) mode remote -> SET_MODE reaches the mock ESP32
        await self.controller.cmd_mode_remote()
        set_mode = await read_until(reader, "SET_MODE")
        self.assertEqual(set_mode["mode"], "REMOTE_DIRECT")
        self.assertEqual(set_mode["seq"], 1)
        self.assertEqual(set_mode["session_id"], session_id)

        # 4) ESP32 acks via STATUS -> outstanding cleared
        writer.write(status_line(session_id, status_seq=2, last_processed_cmd_seq=1,
                                 command_result="ACCEPTED", mode="REMOTE_DIRECT"))
        await writer.drain()
        await asyncio.sleep(0.05)
        self.assertFalse(self.controller.session.has_outstanding())

        # 5) throttle set -> DIRECT_CONTROL streamed at 10 Hz
        self.controller.cmd_set_throttle(0.10)
        # The controller deliberately arms at neutral first. Skip any queued
        # neutral frame and wait for the new non-zero intent.
        while True:
            dc = await read_until(reader, "DIRECT_CONTROL")
            if abs(float(dc.get("throttle", 0.0)) - 0.10) < 1e-6:
                break
        self.assertAlmostEqual(dc["throttle"], 0.10, places=3)
        self.assertIn("control_seq", dc)
        self.assertEqual(dc["session_id"], session_id)

        # 6) HEARTBEAT streamed
        hb = await read_until(reader, "HEARTBEAT", timeout=1.0)
        self.assertEqual(hb["session_id"], session_id)

        writer.close()

    async def test_reconnect_gets_new_session(self):
        r1, w1 = await asyncio.open_connection("127.0.0.1", self.port)
        w1.write(hello_line("BOOTA"))
        await w1.drain()
        ack1 = await read_until(r1, "HELLO_ACK")
        w1.close()
        await asyncio.sleep(0.05)

        r2, w2 = await asyncio.open_connection("127.0.0.1", self.port)
        w2.write(hello_line("BOOTB"))
        await w2.drain()
        ack2 = await read_until(r2, "HELLO_ACK")
        self.assertNotEqual(ack1["session_id"], ack2["session_id"])
        self.assertEqual(ack2["boot_id"], "BOOTB")
        w2.close()


if __name__ == "__main__":
    unittest.main()
