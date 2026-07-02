# Hardware Wiring

## 1. Power Wiring

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
  ├── DC-DC Step-down Converter
  └── Other Modules

  2. ESP32 Pin Map
Function	ESP32 GPIO	Note
Motor PWM	GPIO 25	Motor driver PWM input
Motor DIR	GPIO 26	Motor direction control
Servo PWM	GPIO 27	Steering servo signal
UART RX	TBD	From Raspberry Pi
UART TX	TBD	To Raspberry Pi
GND	GND	Common ground required
3. Motor Driver Connection
Motor Driver Pin	Connected To
B+	Battery positive through fuse/switch
B-	Battery ground
M+ / M-	DC motor
PWM	ESP32 GPIO 25
DIR	ESP32 GPIO 26
GND	ESP32 GND
4. Servo Connection
Servo Wire	Connected To
VCC	Step-down converter 5V output
GND	Common GND
Signal	ESP32 GPIO 27
5. Notes
Motor power line should use thicker wires.
ESP32, motor driver, servo power supply, and Raspberry Pi should share common GND when signal communication is used.
Before high PWM testing, check solder joints and power input stability.

---

# 8. 트러블슈팅 문서 만들기

`docs/troubleshooting.md` 파일.

```md
# Troubleshooting

## 1. Fuse blown during high PWM motor test

### Date
2026-07-02

### Situation
The fuse was blown after increasing the motor PWM value during the driving test.

### Possible Causes
- Motor driver B+ / B- input contact instability
- Sudden current spike during motor startup or high PWM operation
- Weak soldering joint on the DC-DC step-down converter module
- Wiring vibration during RC car testing

### Action
- Reinforce soldering joints
- Recheck B+ / B- connection
- Restart PWM test from low duty values
- Record current behavior and minimum driving PWM

### Result
TBD

---

## 2. DC-DC converter solder joint disconnected

### Date
2026-07-02

### Situation
The soldered part of the step-down converter was disconnected.

### Action
- Resolder the disconnected joint
- Check converter output voltage before connecting modules
- Fix the converter physically to reduce vibration

### Result
TBD