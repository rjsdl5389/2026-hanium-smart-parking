# Hardware Wiring

## 1. Overview

This document summarizes the hardware wiring structure of the RC car system.

The wiring is divided into four parts:

- Main power wiring
- Motor driver wiring
- ESP32 control wiring
- Servo and communication wiring

The most important rule is that power wiring must be stable, and all signal-related modules must share common ground.

---

## 2. Main Power Wiring

```text
Battery
  ↓
XT60 Connector
  ↓
Fuse
  ↓
Power Switch
  ↓
Power Distribution Terminal
  ├── Motor Driver Power Input
  ├── DC-DC Step-down Converter Input
  └── Other Modules
```

## 2.1 Power Wiring Notes

- Use thick wires for the main power line.
- Place the fuse close to the battery side.
- Check polarity before connecting the motor driver.
- Check solder joints before high PWM testing.
- Secure wires physically to reduce vibration during RC car movement.

---

## 3. Motor Driver Wiring

| Motor Driver Pin | Connected To | Note |
|---|---|---|
| B+ | Battery positive through fuse and switch | Main motor power input |
| B- | Battery ground | Main motor power ground |
| M+ | DC motor terminal | Motor output |
| M- | DC motor terminal | Motor output |
| PWM | ESP32 GPIO 25 | Motor speed control |
| DIR | ESP32 GPIO 26 | Motor direction control |
| GND | ESP32 GND | Common ground required |

## 3.1 Motor Driver Notes

- B+ and B- must be firmly connected.
- Loose power input can cause unstable behavior or fuse issues.
- Start testing from low PWM values.
- Check motor direction at low speed before increasing PWM.
- If the motor direction is reversed, swap M+ and M- or adjust DIR logic in code.

---

## 4. ESP32 Pin Map

| Function | ESP32 GPIO | Description |
|---|---:|---|
| Motor PWM | GPIO 25 | PWM signal to motor driver |
| Motor DIR | GPIO 26 | Direction signal to motor driver |
| Servo PWM | GPIO 27 | Steering servo signal |
| UART RX | TBD | Receive command from Raspberry Pi |
| UART TX | TBD | Send response to Raspberry Pi |
| GND | GND | Common ground |

---

## 5. Servo Wiring

| Servo Wire | Connected To | Note |
|---|---|---|
| VCC | DC-DC converter 5V output | Do not power servo directly from ESP32 3.3V |
| GND | Common GND | Must be connected to ESP32 GND |
| Signal | ESP32 GPIO 27 | PWM signal for steering |

## 5.1 Servo Notes

- Servo power should come from a stable 5V source.
- ESP32 only provides the signal line.
- Servo GND and ESP32 GND must be connected.
- Test left, center, and right values before driving the RC car.
- Avoid forcing the servo mechanically beyond the steering limit.

---

## 6. Raspberry Pi and ESP32 Communication Wiring

The initial communication method is UART or USB Serial.

```text
Raspberry Pi TX  ─────→  ESP32 RX
Raspberry Pi RX  ←─────  ESP32 TX
Raspberry Pi GND ──────  ESP32 GND
```

If USB Serial is used, the USB cable can handle data communication. Still, common ground should be considered when external motor and servo power systems are connected.

---

## 7. Grounding Rule

All control signals require a shared reference ground.

```text
Battery GND
  ├── Motor Driver B-
  ├── DC-DC Converter GND
  ├── Servo GND
  ├── ESP32 GND
  └── Raspberry Pi GND
```

Without common ground, PWM and UART signals may behave unpredictably.

---

## 8. Recommended Test Order

| Step | Test | Purpose |
|---:|---|---|
| 1 | Power line continuity check | Confirm no short circuit |
| 2 | DC-DC converter output check | Confirm stable 5V output |
| 3 | Motor driver power check | Confirm B+ and B- wiring |
| 4 | DC motor low PWM test | Check basic movement |
| 5 | Servo center test | Check steering neutral position |
| 6 | Servo left/right test | Check steering limits |
| 7 | Motor + servo integrated test | Check actual driving |
| 8 | Raspberry Pi command test | Check communication |

---

## 9. Safety Checklist Before Power On

- [ ] Battery polarity checked
- [ ] Fuse installed
- [ ] Switch connected correctly
- [ ] B+ and B- connected correctly
- [ ] DC-DC converter output voltage checked
- [ ] ESP32 GND and motor driver GND connected
- [ ] Servo signal and power wiring checked
- [ ] Wires physically fixed to avoid vibration
- [ ] First test starts from low PWM

---

## 10. Known Issues

| Date | Issue | Possible Cause | Action |
|---|---|---|---|
| 2026-07-02 | Fuse blown during high PWM test | Unstable B+/B- contact or sudden current spike | Reinforce soldering and restart from low PWM |
| 2026-07-02 | DC-DC converter solder joint disconnected | Weak soldering or vibration | Resolder and physically secure the module |

---

## 11. Future Wiring Improvements

- Add clearer wire labels
- Add strain relief for power wires
- Fix DC-DC converter and motor driver firmly to the RC car frame
- Separate high-current power wires from signal wires as much as possible
- Add a wiring diagram image in `assets/diagrams/`
