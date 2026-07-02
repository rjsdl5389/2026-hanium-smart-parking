# System Architecture

## 1. Overview

This document describes the overall system architecture of the 2026 Hanium Smart Parking RC Car project.

The system is divided into two major parts:

- Raspberry Pi: camera processing, parking space recognition, and driving command generation
- ESP32: low-level motor control, servo steering control, and command execution

This separation allows the Raspberry Pi to focus on relatively heavy vision processing, while the ESP32 handles real-time embedded control.

---

## 2. Overall System Flow

```text
[ Parking Lot Map / Camera View ]
              ↓
[ Raspberry Pi ]
  - Camera frame acquisition
  - Image processing
  - Parking space recognition
  - Driving command decision
              ↓
[ UART / USB Serial Communication ]
              ↓
[ ESP32 ]
  - Command parsing
  - DC motor PWM control
  - Motor direction control
  - Servo steering control
              ↓
[ Motor Driver + Servo Motor ]
              ↓
[ RC Car Movement ]
```

---

## 3. Layered Architecture

```text
Application Layer
└── Parking decision logic
    └── Select driving command based on camera/map result

Vision Processing Layer
└── Raspberry Pi
    ├── Camera input
    ├── OpenCV processing
    ├── Parking space detection
    └── Object / vehicle recognition test

Communication Layer
└── UART or USB Serial
    ├── Raspberry Pi sends driving command
    └── ESP32 receives and parses command

Embedded Control Layer
└── ESP32
    ├── DC motor PWM control
    ├── Motor direction control
    ├── Servo steering control
    └── Safety stop handling

Hardware Actuation Layer
└── RC Car
    ├── Motor driver
    ├── DC drive motor
    ├── Steering servo
    └── Power system
```

---

## 4. Role Separation

## 4.1 Raspberry Pi

The Raspberry Pi is responsible for high-level processing and decision making.

| Function | Description |
|---|---|
| Camera input | Receives image frames from the camera |
| Image processing | Processes parking lot map and vehicle position |
| Parking space recognition | Detects available or occupied parking spaces |
| Driving command generation | Determines movement command such as forward, stop, left, or right |
| Serial communication | Sends control commands to the ESP32 |

The Raspberry Pi does not directly control the motor or servo. Instead, it sends simple movement commands to the ESP32.

---

## 4.2 ESP32

The ESP32 is responsible for low-level embedded control.

| Function | Description |
|---|---|
| Command receiver | Receives commands from Raspberry Pi |
| Command parser | Interprets commands such as F, S, L, R, and C |
| DC motor control | Controls motor speed using PWM |
| Direction control | Controls motor driver direction input |
| Servo control | Controls steering angle using PWM signal |
| Safety handling | Stops the motor when needed during testing |

The ESP32 directly controls the motor driver and steering servo.

---

## 5. Communication Structure

The Raspberry Pi and ESP32 communicate using UART or USB Serial.

```text
Raspberry Pi
  TX  ─────────────→  ESP32 RX
  RX  ←─────────────  ESP32 TX
  GND ──────────────  ESP32 GND
```

For stable communication, both boards must share a common ground.

---

## 6. Command Protocol

The initial command protocol is intentionally simple for debugging.

| Command | Meaning | ESP32 Action |
|---|---|---|
| F | Forward | Drive the DC motor forward |
| S | Stop | Stop the DC motor |
| L | Left | Move steering servo to left angle |
| R | Right | Move steering servo to right angle |
| C | Center | Move steering servo to center angle |

Example command flow:

```text
Camera detects target direction
        ↓
Raspberry Pi decides "turn left"
        ↓
Raspberry Pi sends 'L'
        ↓
ESP32 receives 'L'
        ↓
ESP32 moves servo to left steering angle
```

---

## 7. ESP32 Control Structure

```text
[ Serial Command Input ]
          ↓
[ Command Parser ]
          ↓
+-----------------------------+
| Control Decision            |
| - Forward / Stop            |
| - Left / Right / Center     |
+-----------------------------+
          ↓
+-----------------------------+
| Output Control              |
| - Motor PWM                 |
| - Motor DIR                 |
| - Servo PWM                 |
+-----------------------------+
          ↓
[ Motor Driver / Servo Motor ]
```

---

## 8. Hardware Control Signal Flow

```text
ESP32 GPIO 25 ─────→ Motor Driver PWM Input
ESP32 GPIO 26 ─────→ Motor Driver DIR Input
ESP32 GPIO 27 ─────→ Servo Signal Input
ESP32 GND    ─────→ Common Ground
```

---

## 9. Power Structure

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
  │     └── Servo / Controller Power
  └── Other Modules
```

The motor power line and logic control line are separated conceptually, but all signal-related modules must share common ground.

---

## 10. Development Stages

| Stage | Description | Main Output |
|---|---|---|
| 1 | DC motor basic test | Motor forward/stop control |
| 2 | Servo steering test | Left/right/center steering |
| 3 | Integrated drive test | Motor and servo combined movement |
| 4 | PWM sweep test | Minimum driving PWM measurement |
| 5 | UART command test | Raspberry Pi to ESP32 command transmission |
| 6 | Camera test | Camera frame and map visibility check |
| 7 | Vision-based driving | Camera result converted to driving command |
| 8 | Final demo | RC car movement on parking map |

---

## 11. Design Rationale

The system uses a distributed control structure for the following reasons:

- Raspberry Pi is better suited for camera processing and AI inference.
- ESP32 is better suited for real-time PWM-based motor and servo control.
- Separating high-level decision making and low-level control makes debugging easier.
- Each module can be tested independently before final integration.
- The final system can be expanded by improving either the vision module or the control module without rewriting the entire system.

---

## 12. Future Improvements

- Add checksum or command validation to serial communication
- Add emergency stop command
- Add feedback from ESP32 to Raspberry Pi
- Add motor encoder feedback if needed
- Add structured driving states such as IDLE, FORWARD, TURNING, and STOP
- Improve camera-based position estimation
- Integrate autonomous parking path planning
