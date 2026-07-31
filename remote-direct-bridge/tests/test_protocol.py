import json
import unittest

import config
import protocol


class ProtocolBuildTests(unittest.TestCase):
    def test_hello_ack_echoes_boot_id(self):
        msg = protocol.build_hello_ack(session_id="S1", boot_id="BOOTXYZ")
        self.assertEqual(msg["type"], "HELLO_ACK")
        self.assertEqual(msg["boot_id"], "BOOTXYZ")
        self.assertEqual(msg["car_id"], config.CAR_ID)
        self.assertEqual(msg["result"], "READY_ALLOWED")
        self.assertEqual(msg["command_seq_start"], 1)

    def test_set_mode_fields(self):
        msg = protocol.build_set_mode("S1", 7, "REMOTE_DIRECT")
        self.assertEqual(msg["seq"], 7)
        self.assertEqual(msg["mode"], "REMOTE_DIRECT")

    def test_direct_control_clamps_and_rounds(self):
        msg = protocol.build_direct_control("S1", 5, throttle=2.0, steering=-3.0)
        self.assertEqual(msg["throttle"], 1.0)   # clamped
        self.assertEqual(msg["steering"], -1.0)  # clamped
        self.assertEqual(msg["control_seq"], 5)

    def test_direct_control_rejects_nan(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.build_direct_control("S1", 5, throttle=float("nan"), steering=0.0)

    def test_encode_line_has_newline_and_is_compact(self):
        raw = protocol.encode_line(protocol.build_heartbeat("S1", 1))
        self.assertTrue(raw.endswith(b"\n"))
        self.assertNotIn(b", ", raw)  # compact separators

    def test_encode_line_rejects_oversized(self):
        big = {"version": 1, "type": "X", "car_id": config.CAR_ID, "blob": "y" * 600}
        with self.assertRaises(protocol.ProtocolError):
            protocol.encode_line(big)


class ProtocolParseTests(unittest.TestCase):
    def _status(self, **overrides):
        base = {
            "version": 1, "type": "STATUS", "car_id": config.CAR_ID,
            "boot_id": "B1", "session_id": "S1", "status_seq": 3,
            "last_processed_cmd_seq": 1, "state": "READY", "mode": "REMOTE_DIRECT",
        }
        base.update(overrides)
        return json.dumps(base)


    def test_compact_remote_status_fits_512_bytes(self):
        # Mirrors the practical fixed-format IDs used by this bridge/firmware.
        status = {
            "version": 1, "type": "STATUS", "car_id": config.CAR_ID,
            "boot_id": "B12345678", "session_id": "S12345678",
            "status_seq": 4294967295, "last_processed_cmd_seq": 4294967295,
            "rejected_seq": 4294967295, "command_result": "SESSION_MISMATCH",
            "state": "EMERGENCY_STOP", "mode": "REMOTE_DIRECT",
            "target_loaded": False, "resume_allowed": False,
            "wait_reason": "DIRECT_CONTROL_TIMEOUT", "error_code": "E" * 31,
            "latest_control_seq": 4294967295,
            "applied_throttle": -1.0, "applied_steering": -1.0,
        }
        raw = json.dumps(status, separators=(",", ":")).encode("utf-8")
        self.assertLessEqual(len(raw), config.RX_MAX_LINE_BYTES)

    def test_parse_valid_status(self):
        msg = protocol.parse_line(self._status())
        self.assertEqual(msg["type"], "STATUS")
        self.assertEqual(msg["state"], "READY")

    def test_parse_rejects_bad_version(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_line(self._status(version=2))

    def test_parse_rejects_car_id_mismatch(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_line(self._status(car_id="CAR_09"))

    def test_parse_rejects_garbage(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_line("{not json")

    def test_parse_rejects_empty(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_line("   ")


class FingerprintTests(unittest.TestCase):
    def test_same_mode_same_fingerprint(self):
        a = protocol.build_set_mode("S1", 1, "REMOTE_DIRECT")
        b = protocol.build_set_mode("S1", 1, "REMOTE_DIRECT")
        self.assertEqual(protocol.reliable_fingerprint(a),
                         protocol.reliable_fingerprint(b))

    def test_different_mode_different_fingerprint(self):
        a = protocol.build_set_mode("S1", 1, "REMOTE_DIRECT")
        b = protocol.build_set_mode("S1", 1, "WAYPOINT_AUTO")
        self.assertNotEqual(protocol.reliable_fingerprint(a),
                            protocol.reliable_fingerprint(b))


if __name__ == "__main__":
    unittest.main()
