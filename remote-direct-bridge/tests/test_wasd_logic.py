import unittest

from wasd_logic import (
    advance_steering,
    compute_drive_intent,
    compute_throttle,
    expected_actuator,
    steering_direction,
)


class WasdLogicTests(unittest.TestCase):
    def test_no_keys_is_stop_center(self):
        intent = compute_drive_intent(set(), 0.0)
        self.assertEqual((intent.throttle, intent.steering), (0.0, 0.0))

    def test_forward_while_w_held(self):
        intent = compute_drive_intent({"w"}, 0.0)
        self.assertEqual((intent.throttle, intent.steering), (1.0, 0.0))

    def test_reverse_while_s_held(self):
        self.assertEqual(compute_throttle({"s"}), -1.0)

    def test_conflicting_forward_reverse_stops(self):
        self.assertEqual(compute_throttle({"w", "s"}), 0.0)

    def test_conflicting_left_right_centers(self):
        self.assertEqual(steering_direction({"a", "d"}), 0)
        self.assertEqual(advance_steering(0.7, {"a", "d"}), 0.0)

    def test_a_d_ramp_one_step(self):
        self.assertEqual(advance_steering(0.0, {"a"}), -0.1)
        self.assertEqual(advance_steering(0.0, {"d"}), 0.1)

    def test_shift_doubles_ramp_step(self):
        self.assertEqual(advance_steering(0.0, {"d", "shift_l"}), 0.2)

    def test_ramp_is_capped_at_operational_max(self):
        value = 0.0
        for _ in range(30):
            value = advance_steering(value, {"d"})
        self.assertEqual(value, 1.0)
        for _ in range(30):
            value = advance_steering(value, {"a"})
        self.assertEqual(value, -1.0)

    def test_direction_reversal_crosses_center_immediately(self):
        self.assertEqual(advance_steering(0.7, {"a"}), -0.1)
        self.assertEqual(advance_steering(-0.7, {"d"}), 0.1)

    def test_expected_calibration_v53(self):
        self.assertEqual(expected_actuator(1.0, 0.0), (27, 86.0, "FORWARD"))
        self.assertEqual(expected_actuator(1.0, 0.5), (45, 104.0, "FORWARD"))
        self.assertEqual(expected_actuator(-1.0, -1.0), (55, 50.0, "REVERSE"))

    def test_intermediate_steering_is_interpolated(self):
        duty, angle, direction = expected_actuator(1.0, 0.1)
        self.assertEqual(duty, 31)
        self.assertAlmostEqual(angle, 89.6)
        self.assertEqual(direction, "FORWARD")


if __name__ == "__main__":
    unittest.main()
