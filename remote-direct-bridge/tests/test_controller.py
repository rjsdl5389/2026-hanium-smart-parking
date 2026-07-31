import unittest

import config
from controller import BRIDGE_BUILD_ID, Controller


class FakeTransport:
    def __init__(self):
        self.sent = []

    async def sender(self, message):
        self.sent.append(message)

    def by_type(self, mtype):
        return [m for m in self.sent if m.get("type") == mtype]


class ControllerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tx = FakeTransport()
        self.ctl = Controller()
        self.ctl.attach(self.tx.sender)

    async def _hello(self, boot_id="BOOT01"):
        await self.ctl.on_message({
            "version": 1,
            "type": "HELLO",
            "car_id": "CAR_01",
            "boot_id": boot_id,
            "firmware_version": "0.5.3",
            "previous_state": "BOOT",
            "previous_session_id": "",
            "last_processed_cmd_seq": 0,
            "target_loaded": False,
            "resume_allowed": False,
            "motor_stopped": True,
            "error_code": "NONE",
        })

    def _status(self, **overrides):
        base = {
            "version": 1,
            "type": "STATUS",
            "car_id": "CAR_01",
            "session_id": self.ctl.session.session_id,
            "status_seq": 1,
            "last_processed_cmd_seq": 0,
            "command_result": "NONE",
            "rejected_seq": 0,
            "state": "READY",
            "mode": "WAYPOINT_AUTO",
            "encoder_count": 0,
            "wait_reason": "NONE",
            "error_code": "NONE",
        }
        base.update(overrides)
        return base

    async def _ready(self, mode="WAYPOINT_AUTO", status_seq=1):
        await self._hello()
        self.ctl._on_status(self._status(status_seq=status_seq, mode=mode))

    async def test_build_id_is_v53(self):
        self.assertIn("v5.3", BRIDGE_BUILD_ID)

    async def test_hello_produces_ack_and_repeated_hello_reuses_session(self):
        await self._hello("BOOTABC")
        first = self.tx.by_type("HELLO_ACK")[-1]
        await self._hello("BOOTABC")
        second = self.tx.by_type("HELLO_ACK")[-1]
        self.assertEqual(first["boot_id"], "BOOTABC")
        self.assertEqual(first["session_id"], second["session_id"])

    async def test_mode_waits_for_explicit_acceptance_not_periodic_none(self):
        await self._ready()
        await self.ctl.cmd_mode_remote()
        self.assertEqual(len(self.tx.by_type("SET_MODE")), 1)
        self.assertFalse(self.ctl._direct_streaming)
        self.assertTrue(self.ctl.session.has_outstanding())

        self.ctl._on_status(self._status(
            status_seq=2,
            last_processed_cmd_seq=1,
            command_result="NONE",
            mode="REMOTE_DIRECT",
        ))
        self.assertFalse(self.ctl._direct_streaming)
        self.assertTrue(self.ctl.session.has_outstanding())

        self.ctl._on_status(self._status(
            status_seq=3,
            last_processed_cmd_seq=1,
            command_result="ACCEPTED",
            mode="REMOTE_DIRECT",
        ))
        self.assertTrue(self.ctl._direct_streaming)
        self.assertFalse(self.ctl.session.has_outstanding())

    async def test_delayed_lower_status_seq_ack_arms_without_regressing_snapshot(self):
        await self._ready()
        await self.ctl.cmd_mode_remote()
        self.ctl._on_status(self._status(
            status_seq=20,
            last_processed_cmd_seq=1,
            command_result="NONE",
            mode="REMOTE_DIRECT",
            state="READY",
            encoder_count=100,
        ))
        self.assertFalse(self.ctl._direct_streaming)
        self.assertEqual(self.ctl.session.last_status_seq, 20)

        self.ctl._on_status(self._status(
            status_seq=19,
            last_processed_cmd_seq=1,
            command_result="ACCEPTED",
            mode="REMOTE_DIRECT",
            state="MOVING",
            encoder_count=999,
        ))
        self.assertTrue(self.ctl._direct_streaming)
        self.assertEqual(self.ctl.session.last_status_seq, 20)
        self.assertEqual(self.ctl.session.last_status["state"], "READY")
        self.assertEqual(self.ctl.session.last_status["encoder_count"], 100)

    async def test_duplicate_mode_request_while_pending_is_ignored(self):
        await self._ready()
        await self.ctl.cmd_mode_remote()
        await self.ctl.cmd_mode_remote()
        self.assertEqual(len(self.tx.by_type("SET_MODE")), 1)

    async def test_mode_when_already_remote_rearms_without_new_reliable_command(self):
        await self._ready(mode="REMOTE_DIRECT")
        await self.ctl.cmd_mode_remote()
        self.assertEqual(len(self.tx.by_type("SET_MODE")), 0)
        self.assertTrue(self.ctl._direct_streaming)
        self.assertEqual(self.ctl.session.desired_throttle, 0.0)

    async def test_nonzero_drive_ignored_until_armed(self):
        await self._ready()
        self.ctl.cmd_set_drive(1.0, 0.5)
        self.assertEqual(self.ctl.session.desired_throttle, 0.0)
        self.assertEqual(self.ctl.session.desired_steering, 0.0)

    async def test_reset_ignored_while_ready(self):
        await self._ready()
        await self.ctl.cmd_reset()
        self.assertEqual(len(self.tx.by_type("RESET")), 0)

    async def test_stop_reset_mode_recovery_sequence(self):
        await self._ready()
        await self.ctl.cmd_mode_remote()
        self.ctl._on_status(self._status(
            status_seq=2,
            last_processed_cmd_seq=1,
            command_result="ACCEPTED",
            mode="REMOTE_DIRECT",
        ))
        self.assertTrue(self.ctl._direct_streaming)

        await self.ctl.cmd_stop()
        self.assertFalse(self.ctl._direct_streaming)
        self.ctl._on_status(self._status(
            status_seq=3,
            last_processed_cmd_seq=2,
            command_result="ACCEPTED",
            state="EMERGENCY_STOP",
            mode="REMOTE_DIRECT",
        ))

        await self.ctl.cmd_reset()
        self.assertEqual(len(self.tx.by_type("RESET")), 1)
        self.ctl._on_status(self._status(
            status_seq=4,
            last_processed_cmd_seq=3,
            command_result="ACCEPTED",
            state="READY",
            mode="WAYPOINT_AUTO",
        ))

        await self.ctl.cmd_mode_remote()
        self.assertEqual(len(self.tx.by_type("SET_MODE")), 2)
        self.ctl._on_status(self._status(
            status_seq=5,
            last_processed_cmd_seq=4,
            command_result="ACCEPTED",
            state="READY",
            mode="REMOTE_DIRECT",
        ))
        self.assertTrue(self.ctl._direct_streaming)
        self.ctl.cmd_set_drive(1.0, 0.0)
        self.assertEqual(self.ctl.session.desired_throttle, 1.0)

    async def test_stop_preempts_pending_mode(self):
        await self._ready()
        await self.ctl.cmd_mode_remote()
        await self.ctl.cmd_stop()
        self.assertEqual(len(self.tx.by_type("STOP")), 1)
        self.assertIsNone(self.ctl._pending_remote_mode_seq)
        self.assertAlmostEqual(
            self.ctl.session.outstanding.resend_timeout_s,
            config.STOP_RESEND_TIMEOUT_S,
        )

    async def test_encoder_delta_ignores_stale_snapshot(self):
        await self._ready(mode="REMOTE_DIRECT")
        self.ctl._on_status(self._status(status_seq=2, mode="REMOTE_DIRECT", encoder_count=100))
        self.ctl._on_status(self._status(status_seq=4, mode="REMOTE_DIRECT", encoder_count=110))
        self.assertEqual(self.ctl.session.last_status["encoder_delta"], 10)
        self.ctl._on_status(self._status(status_seq=3, mode="REMOTE_DIRECT", encoder_count=90))
        self.assertEqual(self.ctl.session.last_status["encoder_count"], 110)
        self.assertEqual(self.ctl.session.last_status["encoder_delta"], 10)

    async def test_wrong_session_status_is_ignored(self):
        await self._hello()
        self.ctl._on_status({
            "version": 1,
            "type": "STATUS",
            "car_id": "CAR_01",
            "session_id": "S_OTHER",
            "status_seq": 1,
            "state": "MOVING",
            "mode": "REMOTE_DIRECT",
        })
        self.assertIsNone(self.ctl.session.last_status)


if __name__ == "__main__":
    unittest.main()
