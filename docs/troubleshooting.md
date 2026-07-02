# Troubleshooting

## 1. Purpose

This document records hardware and software issues found during development.

The goal is not only to fix problems, but also to keep evidence of the engineering process:

```text
Problem → Cause Analysis → Action → Result
```

This record will be useful for the final report, presentation, GitHub portfolio, and interview explanation.

---

## 2. Issue Log

| No. | Date | Issue | Status |
|---:|---|---|---|
| 1 | 2026-07-02 | Fuse blown during high PWM motor test | In progress |
| 2 | 2026-07-02 | DC-DC converter solder joint disconnected | In progress |

---

## 3. Issue 1: Fuse blown during high PWM motor test

## 3.1 Date

2026-07-02

## 3.2 Situation

During the motor driving test, the fuse was blown after increasing the PWM value.

The issue appeared after testing relatively high PWM values.

## 3.3 Possible Causes

| Possible Cause | Description |
|---|---|
| Unstable B+ / B- connection | Loose power input to the motor driver may cause unstable current flow |
| Sudden current spike | Motor startup or high PWM operation may create a current spike |
| Weak solder joint | Poor soldering can increase resistance or cause intermittent contact |
| Wiring vibration | Movement of the RC car may loosen temporary wiring |
| Motor load increase | Actual floor driving requires more current than unloaded wheel testing |

## 3.4 Action Plan

- Reinforce soldering joints
- Recheck B+ and B- input connection
- Check fuse holder connection
- Check DC-DC converter soldering
- Restart PWM test from low values
- Increase PWM step by step
- Record motor behavior and fuse status at each PWM value

## 3.5 Test Plan After Fix

| PWM | Test Condition | Expected Check |
|---:|---|---|
| 80 | Rear wheels lifted | Motor response |
| 100 | Rear wheels lifted | Motor response |
| 120 | Rear wheels lifted | Motor response |
| 140 | On floor | Whether RC car moves |
| 160 | On floor | Minimum driving candidate |
| 180 | On floor | Stable driving candidate |
| 200 | On floor | Fuse stability |
| 220 | On floor | High PWM stability check |

## 3.6 Result

TBD

## 3.7 Notes

This issue should be linked with the PWM sweep test record in `docs/test_log_summary.md`.

---

## 4. Issue 2: DC-DC converter solder joint disconnected

## 4.1 Date

2026-07-02

## 4.2 Situation

The soldered part of the DC-DC step-down converter was disconnected.

## 4.3 Possible Causes

| Possible Cause | Description |
|---|---|
| Weak soldering | The solder joint may not have been mechanically strong enough |
| Mechanical stress | Wire movement may have stressed the solder joint |
| Module not fixed | A floating module can move during testing |
| Wire tension | Short or stiff wire may pull the solder joint |

## 4.4 Action Plan

- Resolder the disconnected joint
- Check the output voltage before reconnecting modules
- Physically fix the converter to reduce movement
- Avoid applying tension to the soldered wire
- Recheck wiring after vibration or driving test

## 4.5 Result

TBD

---

## 5. Debugging Principles

- Do not test high PWM immediately after wiring changes.
- Start from the lowest meaningful PWM value.
- Change only one variable at a time.
- Record both success and failure cases.
- Take photos before and after wiring changes.
- Record short videos of important tests.
- Keep hardware tests and software changes linked by date.

---

## 6. Troubleshooting Template

Use this template for future issues.

```md
## Issue Title

### Date
YYYY-MM-DD

### Situation
Describe what happened.

### Possible Causes
- Cause 1
- Cause 2
- Cause 3

### Action
- Action 1
- Action 2
- Action 3

### Result
Describe what changed after the fix.

### Next Step
Describe what should be tested next.
```

---

## 7. Future Issues To Watch

| Area | Risk | What To Record |
|---|---|---|
| Motor control | Motor does not move at low PWM | Minimum working PWM |
| Servo control | Steering angle too large or too small | Left/center/right values |
| Power system | Fuse blown or voltage drop | PWM, battery condition, wiring state |
| Communication | Command not received | Sent command, received command, baud rate |
| Camera | Map not fully visible | Camera height, angle, resolution |
| Integration | RC car does not follow command | Camera result, Pi command, ESP32 action |
