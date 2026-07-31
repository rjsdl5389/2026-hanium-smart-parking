# V4 final REMOTE_DIRECT configuration

Finalized on 2026-07-29 from the completed HW tests.

## Motor
- PWM pin: GPIO25
- DIR pin: GPIO26
- Forward DIR level: HIGH
- Reverse DIR level: LOW
- PWM frequency: **20,000 Hz**
- PWM resolution: **8 bit**
- PWM range: **0..255**
- Straight minimum/default: 15 / 23
- Weak-turn minimum/default: 35 / 40
- Strong-turn default: 50
- Reverse remains disabled by default.

## Steering
- PWM pin: GPIO27
- Frequency: 50 Hz
- Pulse range: 500..2400 us
- Strong left / weak left / center / weak right / strong right:
  30 / 60 / 86 / 112 / 122 degrees
- Servo is initialized and centered before the motor LEDC timer is initialized.

## Encoder
- A: GPIO34
- B: GPIO35
- Any-edge quadrature ISR
- Raw encoder_count is reported in STATUS.
- RPM/distance are intentionally deferred until PPR and gear ratio are confirmed.

## Safety defaults
- ENABLE_ACTUATOR_OUTPUT=0
- MOTOR_ALLOW_REVERSE=0
- DIRECT_CONTROL timeout=500 ms
- HEARTBEAT timeout=1000 ms
