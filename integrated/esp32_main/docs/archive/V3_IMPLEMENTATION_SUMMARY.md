# v3 implementation summary

Based on the 2026-07-29 wired HW tests, this version changes only the standalone bridge and ESP32 firmware.

## Firmware changes

- Motor LEDC changed to 8-bit PWM (0..255).
- Verified DIR polarity: HIGH=forward, LOW=reverse.
- Calibrated PWM profiles: straight 15/23, weak turn 35/40, strong turn 50.
- Piecewise steering map: -1=30°, -0.5=60°, 0=86°, +0.5=112°, +1=122°.
- Servo timing: 50 Hz, 500–2400 us.
- Servo is initialized and centered first, waits 500 ms, then motor PWM is initialized.
- When steering target changes, motor PWM is held at zero for 20 ms before applying the new calibrated duty.
- Added GPIO34/GPIO35 any-edge quadrature encoder module.
- Added raw `encoder_count` to REMOTE_DIRECT STATUS.
- RPM/speed/distance intentionally deferred until PPR and gear ratio are confirmed.

## Safety still preserved

- Reverse disabled.
- Actual output disabled by default (`ENABLE_ACTUATOR_OUTPUT=0`).
- 500 ms DIRECT_CONTROL timeout and 1 s communication timeout unchanged.
- STOP remains highest priority.
- No automatic restart after reconnect/RESET.

## Unverified on this machine

The files passed Python tests and C syntax/format checks with ESP-IDF API stubs, including both mock and real-output compile paths. A real `idf.py build`, flash, and vehicle test must be run in the user's ESP-IDF v6.0.2 Windows environment.


## Final PWM confirmation (2026-07-29)
- Motor PWM frequency: 20,000 Hz (20 kHz)
- Resolution: 8 bit
- Duty range: 0..255
- Calibrated values 15/23/40/50 are all based on this exact configuration.
