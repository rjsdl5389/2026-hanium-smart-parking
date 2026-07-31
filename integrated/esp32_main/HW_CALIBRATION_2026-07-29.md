# HW calibration integrated — 2026-07-29

This v3 firmware incorporates the completed wired control/encoder tests before the first wireless integration test.

## Pins

- Motor PWM: GPIO25
- Motor DIR: GPIO26 (`HIGH=forward`, `LOW=reverse`)
- Servo PWM: GPIO27
- Encoder A: GPIO34
- Encoder B: GPIO35

GPIO34/35 are input-only and have no internal pull-up. The tested wiring uses encoder VCC=3.3V, common GND, and no level shifter. If edges become unstable while the motor is powered, inspect grounding/wiring first and then consider external pull-up resistors.

## 8-bit motor calibration

- PWM range: 0..255
- Straight minimum/default: 15 / 23
- Weak turn minimum/default: 35 / 40
- Strong turn default: 50
- Reverse remains disabled for the first wireless test.

`throttle=1.0` means the current calibrated default for the active steering profile, not unrestricted 255 duty.

## Steering calibration

- `steering=-1.0` -> 30° strong left
- `steering=-0.5` -> 60° weak left
- `steering=0.0` -> 86° center
- `steering=+0.5` -> 112° weak right
- `steering=+1.0` -> 122° strong right

22°/130° are mechanical-limit checks only and are not used for normal operation.

Servo timing mirrors the successful Arduino test: 50 Hz, 500–2400 us pulse range. At boot the firmware initializes and centers the servo first, waits 500 ms, then configures motor PWM. When a steering target changes during REMOTE_DIRECT, the motor is stopped for one 20 ms servo period before the new motor duty is restored.

## Encoder integration

- Both A/B pins use any-edge interrupts.
- ISR only reads A/B and updates the quadrature count.
- The count is protected by a FreeRTOS critical section.
- REMOTE_DIRECT STATUS includes `encoder_count`.
- The bridge derives and prints `encoder_delta` from consecutive STATUS messages.
- RPM, distance, and speed are intentionally not calculated until PPR and gearbox ratio are confirmed.

If forward motion produces the unwanted count sign, change this one setting in `main/app_config.h`:

```c
#define ENCODER_DIRECTION_SIGN -1
```


## Final PWM confirmation (2026-07-29)
- Motor PWM frequency: 20,000 Hz (20 kHz)
- Resolution: 8 bit
- Duty range: 0..255
- Calibrated values 15/23/40/50 are all based on this exact configuration.
