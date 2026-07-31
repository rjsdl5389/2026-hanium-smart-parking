# V4 bridge pairing

This bridge is paired with ESP32 firmware v0.4.0.

The bridge still sends normalized `throttle` and `steering`; it does not send raw PWM.
The ESP32 maps the normalized values to the final 20 kHz, 8-bit motor calibration.

Preset commands:
- `straight` -> steering 0.0, calibrated PWM 23
- `left weak` -> steering -0.5, calibrated PWM 40
- `right weak` -> steering +0.5, calibrated PWM 40
- `left strong` -> steering -1.0, calibrated PWM 50
- `right strong` -> steering +1.0, calibrated PWM 50

Windows live keys:
- M: enter REMOTE_DIRECT
- W: increase forward throttle
- A/D: steering left/right
- S: throttle zero
- C: steering center
- Space or X: emergency STOP
- R: RESET
- Q: quit
- `;`: open command prompt mode

> Superseded by `V5_FINAL_CONFIGURATION.md`.
