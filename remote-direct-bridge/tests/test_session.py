import unittest

from session import OutstandingCommand, VehicleSession, new_session_id


class SessionTests(unittest.TestCase):
    def test_session_id_format(self):
        sid = new_session_id()
        self.assertTrue(sid.startswith("S"))
        self.assertEqual(len(sid), 9)

    def test_reliable_and_control_sequences_are_independent(self):
        s = VehicleSession(session_id="S1", boot_id="B1", command_seq_start=1)
        self.assertEqual(s.next_control_seq(), 1)
        self.assertEqual(s.next_seq(), 1)
        self.assertEqual(s.next_control_seq(), 2)
        self.assertEqual(s.next_seq(), 2)

    def _outstanding(self, seq=1):
        return OutstandingCommand(
            seq=seq,
            message={"type": "SET_MODE"},
            fingerprint="SET_MODE|REMOTE_DIRECT",
            sent_at=0.0,
        )

    def test_periodic_none_does_not_clear_outstanding(self):
        s = VehicleSession(session_id="S1", boot_id="B1")
        s.set_outstanding(self._outstanding(1))
        completed = s.consume_terminal_result({
            "last_processed_cmd_seq": 1,
            "command_result": "NONE",
        })
        self.assertIsNone(completed)
        self.assertTrue(s.has_outstanding())

    def test_explicit_accepted_exact_seq_clears_outstanding(self):
        s = VehicleSession(session_id="S1", boot_id="B1")
        s.set_outstanding(self._outstanding(1))
        completed = s.consume_terminal_result({
            "last_processed_cmd_seq": 1,
            "command_result": "ACCEPTED",
        })
        self.assertIsNotNone(completed)
        self.assertFalse(s.has_outstanding())

    def test_newer_command_result_does_not_ack_older_by_greater_equal(self):
        s = VehicleSession(session_id="S1", boot_id="B1")
        s.set_outstanding(self._outstanding(3))
        completed = s.consume_terminal_result({
            "last_processed_cmd_seq": 4,
            "command_result": "ACCEPTED",
        })
        self.assertIsNone(completed)
        self.assertTrue(s.has_outstanding())

    def test_rejected_seq_can_complete_conflict(self):
        s = VehicleSession(session_id="S1", boot_id="B1")
        s.set_outstanding(self._outstanding(7))
        completed = s.consume_terminal_result({
            "last_processed_cmd_seq": 6,
            "rejected_seq": 7,
            "command_result": "SEQ_CONFLICT",
        })
        self.assertIsNotNone(completed)
        self.assertFalse(s.has_outstanding())

    def test_status_snapshot_monotonicity(self):
        s = VehicleSession(session_id="S1", boot_id="B1")
        s.record_snapshot({"status_seq": 10, "state": "READY"})
        self.assertTrue(s.is_stale_snapshot({"status_seq": 10}))
        self.assertTrue(s.is_stale_snapshot({"status_seq": 9}))
        self.assertFalse(s.is_stale_snapshot({"status_seq": 11}))


if __name__ == "__main__":
    unittest.main()
