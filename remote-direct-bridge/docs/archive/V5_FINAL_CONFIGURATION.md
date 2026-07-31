# V5 final configuration

- Firmware: `0.5.0-wasd-hold-reverse-encoder`
- Recommended launcher: `python bridge_gui.py`
- Motor: GPIO25, 20 kHz, 8 bit
- DIR: GPIO26 HIGH=forward, LOW=reverse
- Reverse: enabled for wheels-off-ground validation; initial PWM profiles equal forward profiles
- Servo: GPIO27, 50 Hz, 500–2400 us
- Encoder: GPIO34/GPIO35
- Input: true KeyPress/KeyRelease, simultaneous WASD, focus-loss neutral
- Safety: STOP, RESET gate, 500ms direct timeout, 1s heartbeat timeout, no auto-resume
