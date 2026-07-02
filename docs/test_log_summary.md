# Test Log Summary

## 1. DC Motor PWM Test

| Date | PWM | Condition | Result | Note |
|---|---:|---|---|---|
| TBD | 100 | Rear wheels lifted | TBD | TBD |
| TBD | 120 | Rear wheels lifted | TBD | TBD |
| TBD | 140 | On floor | TBD | TBD |
| TBD | 160 | On floor | TBD | TBD |
| TBD | 180 | On floor | TBD | TBD |
| TBD | 200 | On floor | TBD | TBD |
| TBD | 220 | On floor | TBD | Check fuse stability |

## 2. Servo Steering Test

| Date | Command | Servo Value | Result | Note |
|---|---|---:|---|---|
| TBD | L | TBD | TBD | Max left steering |
| TBD | C | TBD | TBD | Center |
| TBD | R | TBD | TBD | Max right steering |

## 3. Integrated Driving Test

| Date | Steering | PWM | Result | Note |
|---|---|---:|---|---|
| TBD | Center | TBD | TBD | Straight driving |
| TBD | Left | TBD | TBD | Left turn |
| TBD | Right | TBD | TBD | Right turn |
# Test Log Summary

## 1. Purpose

This document summarizes the main hardware and software tests for the RC car project.

Detailed daily notes are written in `docs/development_log.md`, while this file focuses on measurable test results.

The main goal is to record:

- Test condition
- PWM value
- Servo value
- Actual RC car behavior
- Fuse status
- Issue and next action

---

## 2. Test Status Overview

| Category | Test Item | Status | Related File |
|---|---|---|---|
| Motor Control | DC motor basic PWM test | Planned | `firmware_esp32/01_motor_basic_test/` |
| Servo Control | Servo left/center/right test | Planned | `firmware_esp32/02_servo_steering_test/` |
| Integrated Control | Motor + servo integrated test | Planned | `firmware_esp32/03_drive_servo_integrated_test/` |
| PWM Tuning | PWM sweep test | Planned | `firmware_esp32/04_pwm_sweep_test/` |
| Communication | Raspberry Pi to ESP32 command test | Planned | `raspberry_pi/01_uart_sender_test/` |
| Vision | Camera frame and map visibility test | Planned | `raspberry_pi/02_camera_test/` |
| Final Demo | RC car driving on parking map | Planned | `integrated/` |

---

## 3. DC Motor PWM Test

## 3.1 Test Purpose

Measure the PWM range where the RC car can actually move.

This test should be done in two stages:

1. Rear wheels lifted from the ground
2. RC car placed on the floor

The second test is more important because actual floor driving requires more torque and current.

## 3.2 Test Table

| Date | PWM | Test Condition | Motor Response | RC Car Movement | Fuse Status | Result | Note |
|---|---:|---|---|---|---|---|---|
| TBD | 80 | Rear wheels lifted | TBD | N/A | OK / Blown / TBD | TBD | Low PWM response check |
| TBD | 100 | Rear wheels lifted | TBD | N/A | OK / Blown / TBD | TBD | Low PWM response check |
| TBD | 120 | Rear wheels lifted | TBD | N/A | OK / Blown / TBD | TBD | Wheel rotation check |
| TBD | 140 | On floor | TBD | TBD | OK / Blown / TBD | TBD | Floor driving check |
| TBD | 160 | On floor | TBD | TBD | OK / Blown / TBD | TBD | Minimum driving PWM candidate |
| TBD | 180 | On floor | TBD | TBD | OK / Blown / TBD | TBD | Stable driving PWM candidate |
| TBD | 200 | On floor | TBD | TBD | OK / Blown / TBD | TBD | Higher PWM stability check |
| TBD | 220 | On floor | TBD | TBD | OK / Blown / TBD | TBD | Check previous fuse issue |

## 3.3 What To Record

- Whether the motor rotates
- Whether the RC car actually moves on the floor
- Whether the fuse remains stable
- Whether motor driver or wiring becomes hot
- Whether the movement is weak, unstable, or stable
- Minimum PWM required for actual driving

## 3.4 Result Summary

| Item | Value |
|---|---|
| Minimum PWM for wheel rotation | TBD |
| Minimum PWM for actual floor driving | TBD |
| Stable straight driving PWM | TBD |
| PWM value where issue occurred | TBD |
| Recommended default PWM | TBD |

---

## 4. Servo Steering Test

## 4.1 Test Purpose

Find safe and usable servo values for steering.

The goal is not to force the maximum servo angle, but to find the maximum steering range that does not mechanically stress the RC car.

## 4.2 Test Table

| Date | Command | Servo Value / Angle | Wheel Direction | Mechanical Interference | Result | Note |
|---|---|---:|---|---|---|---|
| TBD | C | TBD | Center | No / Yes / TBD | TBD | Neutral steering |
| TBD | L | TBD | Left | No / Yes / TBD | TBD | Maximum safe left steering |
| TBD | R | TBD | Right | No / Yes / TBD | TBD | Maximum safe right steering |

## 4.3 What To Record

- Center servo value
- Maximum safe left value
- Maximum safe right value
- Whether wheels hit the chassis
- Whether servo vibrates or makes noise
- Whether steering returns to center properly

## 4.4 Result Summary

| Item | Value |
|---|---|
| Center servo value | TBD |
| Maximum safe left value | TBD |
| Maximum safe right value | TBD |
| Recommended left command value | TBD |
| Recommended right command value | TBD |

---

## 5. Integrated Motor + Servo Driving Test

## 5.1 Test Purpose

Measure how much PWM is required when the RC car drives while steering.

Turning usually requires more torque than straight driving because of mechanical resistance.

## 5.2 Test Table

| Date | Steering Command | Servo Value | PWM | Test Condition | RC Car Movement | Fuse Status | Result | Note |
|---|---|---:|---:|---|---|---|---|---|
| TBD | C | TBD | 140 | On floor | TBD | OK / Blown / TBD | TBD | Straight driving low PWM |
| TBD | C | TBD | 160 | On floor | TBD | OK / Blown / TBD | TBD | Straight driving candidate |
| TBD | C | TBD | 180 | On floor | TBD | OK / Blown / TBD | TBD | Straight driving stable check |
| TBD | L | TBD | 160 | On floor | TBD | OK / Blown / TBD | TBD | Left turn low PWM |
| TBD | L | TBD | 180 | On floor | TBD | OK / Blown / TBD | TBD | Left turn candidate |
| TBD | L | TBD | 200 | On floor | TBD | OK / Blown / TBD | TBD | Left turn stable check |
| TBD | R | TBD | 160 | On floor | TBD | OK / Blown / TBD | TBD | Right turn low PWM |
| TBD | R | TBD | 180 | On floor | TBD | OK / Blown / TBD | TBD | Right turn candidate |
| TBD | R | TBD | 200 | On floor | TBD | OK / Blown / TBD | TBD | Right turn stable check |

## 5.3 Result Summary

| Item | Value |
|---|---|
| Recommended straight driving PWM | TBD |
| Minimum left turn PWM | TBD |
| Minimum right turn PWM | TBD |
| Stable left turn PWM | TBD |
| Stable right turn PWM | TBD |
| Turning issue found | TBD |

---

## 6. UART / Serial Command Test

## 6.1 Test Purpose

Check whether Raspberry Pi can send driving commands to ESP32 correctly.

## 6.2 Command Table

| Command | Meaning | Expected ESP32 Action | Test Status |
|---|---|---|---|
| F | Forward | Motor starts forward movement | Planned |
| S | Stop | Motor stops | Planned |
| L | Left | Servo moves left | Planned |
| R | Right | Servo moves right | Planned |
| C | Center | Servo returns to center | Planned |

## 6.3 Test Table

| Date | Sender | Receiver | Command | Expected Action | Actual Action | Result | Note |
|---|---|---|---|---|---|---|---|
| TBD | Raspberry Pi | ESP32 | F | Motor forward | TBD | TBD | TBD |
| TBD | Raspberry Pi | ESP32 | S | Motor stop | TBD | TBD | TBD |
| TBD | Raspberry Pi | ESP32 | L | Servo left | TBD | TBD | TBD |
| TBD | Raspberry Pi | ESP32 | R | Servo right | TBD | TBD | TBD |
| TBD | Raspberry Pi | ESP32 | C | Servo center | TBD | TBD | TBD |

---

## 7. Camera Test

## 7.1 Test Purpose

Check whether the camera can capture the full parking map with enough visibility.

## 7.2 Test Table

| Date | Camera Position | Height | Angle | Resolution | Map Fully Visible | Result | Note |
|---|---|---:|---|---|---|---|---|
| TBD | Background stand + clamp | TBD | Top-down | TBD | Yes / No / TBD | TBD | First camera test |
| TBD | Background stand + clamp | TBD | Adjusted | TBD | Yes / No / TBD | TBD | After height adjustment |

## 7.3 What To Record

- Camera height
- Camera angle
- Whether the full map is visible
- Whether parking spaces are clearly visible
- Lighting condition
- Delay or frame drop
- Screenshot or short video link

---

## 8. Issue-Linked Test Record

Use this table when a test causes a failure or unexpected behavior.

| Date | Related Test | Issue | Possible Cause | Action | Result | Related Document |
|---|---|---|---|---|---|---|
| 2026-07-02 | High PWM motor test | Fuse blown | B+/B- instability or sudden current spike | Reinforce soldering and restart from low PWM | TBD | `docs/troubleshooting.md` |
| 2026-07-02 | Power wiring check | DC-DC converter solder joint disconnected | Weak soldering or vibration | Resolder and check output voltage | TBD | `docs/troubleshooting.md` |

---

## 9. Demo Evidence

Instead of uploading large video files directly to GitHub, upload videos to Google Drive, YouTube unlisted, or Notion and record links here.

| Date | Demo Type | Description | Link |
|---|---|---|---|
| TBD | Video | DC motor PWM test | TBD |
| TBD | Video | Servo steering test | TBD |
| TBD | Video | Integrated driving test | TBD |
| TBD | Photo | Wiring overview | TBD |
| TBD | Photo | RC car top view | TBD |
| TBD | Screenshot | Camera view / map recognition | TBD |

---

## 10. Final Test Summary

Fill this section before the final report.

| Item | Final Value / Result |
|---|---|
| Minimum driving PWM | TBD |
| Recommended straight PWM | TBD |
| Recommended left turn PWM | TBD |
| Recommended right turn PWM | TBD |
| Center servo value | TBD |
| Left servo value | TBD |
| Right servo value | TBD |
| Communication method | UART / USB Serial / TBD |
| Camera setup | TBD |
| Final demo result | TBD |

---

## 11. Notion Test Database Columns

Recommended columns for Notion:

| Column Name | Type |
|---|---|
| Date | Date |
| Category | Select |
| Test Item | Text |
| PWM | Number |
| Servo Command | Select |
| Servo Value | Number |
| Test Condition | Select |
| Expected Result | Text |
| Actual Result | Text |
| Fuse Status | Select |
| Issue | Text |
| Action | Text |
| Result | Select |
| Evidence Link | URL |
| Next Step | Text |

Recommended select values:

```text
Category:
- Motor
- Servo
- Integrated
- UART
- Camera
- Power
- Troubleshooting

Test Condition:
- Rear wheels lifted
- On floor
- Camera fixed
- Serial command
- Power check

Fuse Status:
- OK
- Blown
- Not tested

Result:
- Pass
- Fail
- Partial
- TBD
```
