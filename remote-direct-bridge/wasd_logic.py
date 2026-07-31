"""Pure key-state and steering-ramp logic for the Tkinter controller.

The GUI keeps a normalized steering value in the range ``[-1.0, 1.0]``.
Holding A or D increases steering gradually; releasing the steering keys returns
immediately to center.  The module has no GUI/network dependency, so the
safety-critical mapping stays unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import AbstractSet


STEERING_RAMP_STEP = 0.10
STEERING_RAMP_FAST_STEP = 0.20
STEERING_RAMP_INTERVAL_MS = 100

# Mirrors ESP32 v5.1 calibration. The firmware remains GPIO authority.
PWM_FORWARD_MIN = 15.0
PWM_FORWARD_DEFAULT = 27.0
PWM_TURN_MIN = 35.0
PWM_TURN_DEFAULT = 45.0
PWM_STRONG_TURN_DEFAULT = 55.0


@dataclass(frozen=True)
class DriveIntent:
    throttle: float
    steering: float
    label: str


def _keys(pressed: AbstractSet[str]) -> set[str]:
    return {key.lower() for key in pressed}


def compute_throttle(pressed: AbstractSet[str]) -> float:
    """Return +1, -1 or 0 from the currently held W/S keys."""
    keys = _keys(pressed)
    forward = "w" in keys
    reverse = "s" in keys
    if forward == reverse:
        return 0.0
    return 1.0 if forward else -1.0


def steering_direction(pressed: AbstractSet[str]) -> int:
    """Return -1 for A, +1 for D, and 0 for neither/both."""
    keys = _keys(pressed)
    left = "a" in keys
    right = "d" in keys
    if left == right:
        return 0
    return -1 if left else 1


def advance_steering(current: float, pressed: AbstractSet[str]) -> float:
    """Advance steering one safe ramp step toward the held direction.

    A/D alone changes normalized steering by 0.10 every tick. Holding either
    Shift key changes it by 0.20 per tick. The value is always clamped to
    ``[-1.0, 1.0]``. If the requested direction reverses, steering crosses the
    center immediately and starts at one step in the new direction.
    """
    keys = _keys(pressed)
    direction = steering_direction(keys)
    if direction == 0:
        return 0.0

    strong = bool({"shift_l", "shift_r", "shift"} & keys)
    step = STEERING_RAMP_FAST_STEP if strong else STEERING_RAMP_STEP
    value = max(-1.0, min(1.0, float(current)))

    # Do not keep steering right while the driver is already commanding left,
    # or vice versa. Cross center first, then begin the new ramp.
    if value * direction < 0.0:
        value = 0.0

    value += direction * step
    return round(max(-1.0, min(1.0, value)), 3)


def compute_drive_intent(
    pressed: AbstractSet[str],
    steering: float | None = None,
) -> DriveIntent:
    """Build a normalized drive intent from held keys and ramped steering.

    ``steering`` should be supplied by the GUI's ramp state.  When omitted, the
    legacy weak/strong mapping is retained for callers that only need a
    stateless key-to-intent conversion.
    """
    keys = _keys(pressed)
    throttle = compute_throttle(keys)

    if steering is None:
        direction = steering_direction(keys)
        strong = bool({"shift_l", "shift_r", "shift"} & keys)
        steering = direction * (1.0 if strong else 0.5)

    steering = max(-1.0, min(1.0, float(steering)))
    direction_label = (
        "STOP" if throttle == 0.0 else ("FORWARD" if throttle > 0 else "REVERSE")
    )
    if abs(steering) < 1e-9:
        turn_label = "CENTER"
    else:
        side = "LEFT" if steering < 0.0 else "RIGHT"
        turn_label = f"{side} {round(abs(steering) * 100):d}%"

    return DriveIntent(
        throttle=throttle,
        steering=steering,
        label=f"{direction_label} / {turn_label}",
    )


def expected_actuator(throttle: float, steering: float) -> tuple[int, float, str]:
    """Return expected calibrated PWM, servo angle and direction.

    Steering is piecewise interpolated through the verified operational points:
    -1.0=50°, -0.5=68°, 0=86°, +0.5=104°, +1.0=122°.  These endpoints remain
    inside the separately measured mechanical limits.
    """
    throttle = max(-1.0, min(1.0, float(throttle)))
    steering = max(-1.0, min(1.0, float(steering)))

    if steering <= -0.5:
        t = (steering + 1.0) / 0.5
        angle = 50.0 + (68.0 - 50.0) * t
    elif steering < 0.0:
        t = (steering + 0.5) / 0.5
        angle = 68.0 + (86.0 - 68.0) * t
    elif steering <= 0.5:
        t = steering / 0.5
        angle = 86.0 + (104.0 - 86.0) * t
    else:
        t = (steering - 0.5) / 0.5
        angle = 104.0 + (122.0 - 104.0) * t

    magnitude = abs(throttle)
    if magnitude <= 0.02:
        duty = 0
    else:
        abs_steer = abs(steering)
        if abs_steer <= 0.5:
            t = abs_steer / 0.5
            min_duty = PWM_FORWARD_MIN + (PWM_TURN_MIN - PWM_FORWARD_MIN) * t
            default_duty = PWM_FORWARD_DEFAULT + (
                PWM_TURN_DEFAULT - PWM_FORWARD_DEFAULT
            ) * t
        else:
            t = (abs_steer - 0.5) / 0.5
            min_duty = PWM_TURN_MIN + (
                PWM_STRONG_TURN_DEFAULT - PWM_TURN_MIN
            ) * t
            default_duty = PWM_TURN_DEFAULT + (
                PWM_STRONG_TURN_DEFAULT - PWM_TURN_DEFAULT
            ) * t
        duty = round(min_duty + (default_duty - min_duty) * magnitude)

    direction = "REVERSE" if throttle < 0.0 else "FORWARD"
    return int(max(0, min(255, duty))), round(angle, 1), direction
