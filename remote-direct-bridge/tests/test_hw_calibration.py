import importlib.util
import json
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "mock_esp32.py"
SPEC = importlib.util.spec_from_file_location("mock_esp32_for_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
mock_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mock_module)
MockEsp32 = mock_module.MockEsp32


class HardwareCalibrationTests(unittest.TestCase):
    def test_piecewise_servo_points(self):
        self.assertAlmostEqual(MockEsp32.steering_to_angle(-1.0), 46.0)
        self.assertAlmostEqual(MockEsp32.steering_to_angle(-0.5), 66.0)
        self.assertAlmostEqual(MockEsp32.steering_to_angle(0.0), 86.0)
        self.assertAlmostEqual(MockEsp32.steering_to_angle(0.5), 106.0)
        self.assertAlmostEqual(MockEsp32.steering_to_angle(1.0), 126.0)

    def test_8bit_pwm_profiles(self):
        self.assertEqual(MockEsp32.throttle_to_pwm(0.0, 0.0), 0)
        self.assertEqual(MockEsp32.throttle_to_pwm(1.0, 0.0), 25)
        self.assertEqual(MockEsp32.throttle_to_pwm(1.0, 0.5), 43)
        self.assertEqual(MockEsp32.throttle_to_pwm(1.0, 1.0), 54)
        self.assertEqual(MockEsp32.throttle_to_pwm(0.1, 0.0), 17)
        self.assertEqual(MockEsp32.throttle_to_pwm(0.1, 0.5), 35)

    def test_reverse_uses_same_calibrated_profile(self):
        esp = MockEsp32()
        esp.apply_direct(-1.0, 0.0)
        self.assertEqual(esp.applied_throttle, -1.0)
        self.assertEqual(esp.motor_direction, "REVERSE")
        self.assertEqual(esp.motor_pwm, 25)

    def test_remote_status_with_encoder_stays_under_512_bytes(self):
        esp = MockEsp32()
        esp.session_id = "S12345678"
        esp.session_active = True
        esp.mode = "REMOTE_DIRECT"
        esp.encoder_count = 123456789
        line = json.dumps(esp.build_status(), separators=(",", ":")).encode() + b"\n"
        self.assertLessEqual(len(line), 512)


class CurrentConfigurationContractTests(unittest.TestCase):
    def test_tracked_example_matches_verified_and_safe_defaults(self):
        firmware = (
            Path(__file__).resolve().parents[2]
            / "integrated"
            / "esp32_main"
            / "main"
            / "app_config.example.h"
        )
        text = firmware.read_text(encoding="utf-8")
        self.assertIn("#define ENABLE_ACTUATOR_OUTPUT 0", text)
        self.assertIn("#define ENABLE_WAYPOINT_AUTO_CONTROL 0", text)
        self.assertIn("#define DAY3_ALLOW_GO_WITHOUT_POSE 0", text)
        self.assertIn("#define MOTOR_ALLOW_REVERSE 1", text)
        self.assertIn("#define MOTOR_PWM_FREQ_HZ 20000", text)
        self.assertIn("#define MOTOR_PWM_RES_BITS 8", text)
        self.assertIn("#define MOTOR_FORWARD_DIR_LEVEL 1", text)
        self.assertIn("#define MOTOR_REVERSE_DIR_LEVEL 0", text)
        self.assertIn("#define ENCODER_DIRECTION_SIGN -1", text)
        self.assertIn('#define FIRMWARE_VERSION "0.5.6-transport-rto1000"', text)
        self.assertIn("#define PWM_FORWARD_MIN 16", text)
        self.assertIn("#define PWM_FORWARD_DEFAULT 25", text)
        self.assertIn("#define PWM_TURN_MIN 34", text)
        self.assertIn("#define PWM_TURN_DEFAULT 43", text)
        self.assertIn("#define PWM_STRONG_TURN_MIN 40", text)
        self.assertIn("#define PWM_STRONG_TURN_DEFAULT 54", text)
        self.assertIn("#define DIRECT_STALL_TIMEOUT_MS 2000", text)
        self.assertIn("#define DIRECT_STALL_BOOST_MS 300", text)
        self.assertIn(
            "#define DIRECT_STALL_BOOST_PWM PWM_STRONG_TURN_DEFAULT", text
        )
        self.assertIn("#define STOP_MOTOR_DURING_STEER_UPDATE 0", text)
        self.assertIn("#define SERVO_LEFT_STRONG_DEG 46.0", text)
        self.assertIn("#define SERVO_LEFT_WEAK_DEG 66.0", text)
        self.assertIn("#define SERVO_CENTER_DEG 86.0", text)
        self.assertIn("#define SERVO_RIGHT_WEAK_DEG 106.0", text)
        self.assertIn("#define SERVO_RIGHT_STRONG_DEG 126.0", text)

        vehicle_control = firmware.parent / "vehicle_control.c"
        vehicle_text = vehicle_control.read_text(encoding="utf-8")
        self.assertIn("actuator_start_motion();", vehicle_text)
        self.assertIn("COMMAND_RESULT_HOLD", vehicle_text)


if __name__ == "__main__":
    unittest.main()
