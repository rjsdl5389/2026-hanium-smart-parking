# 2026 Hanium Smart Parking RC Car

> Camera-based smart parking RC car system using **Raspberry Pi**, **ESP32**, **OpenCV/YOLO**, and **embedded motor control**.

## 1. Project Overview

This project implements a smart parking RC car system that recognizes a parking lot environment through a camera and controls an RC car based on the recognized parking information.

The system is divided into two main parts:

- **Raspberry Pi**: camera input, image processing, parking space recognition, and driving command decision
- **ESP32**: low-level embedded control, including DC motor PWM control, motor direction control, and servo steering control

The goal of this project is not only to make the RC car move, but also to verify the full development process from hardware wiring, motor control, camera-based recognition, communication, integration testing, and troubleshooting.

---

## 2. System Architecture

### 2.1 Overall System Flow

```text
+-------------------------------------------------------------+
|                       Parking Lot Map                       |
|        Parking spaces / obstacles / RC car movement area    |
+-----------------------------+-------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                          Camera                             |
|  - Captures parking lot map                                  |
|  - Provides image frames to Raspberry Pi                     |
+-----------------------------+-------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                       Raspberry Pi                          |
|                                                             |
|  [Vision Processing Layer]                                  |
|  - Camera frame acquisition                                  |
|  - Image preprocessing                                       |
|  - Parking space / object recognition                        |
|  - Map state estimation                                      |
|                                                             |
|  [Decision Layer]                                           |
|  - Determines driving command                                |
|  - Generates control command: F / S / L / R / C              |
+-----------------------------+-------------------------------+
                              |
                              | UART / USB Serial
                              v
+-------------------------------------------------------------+
|                           ESP32                             |
|                                                             |
|  [Embedded Control Layer]                                   |
|  - Receives command from Raspberry Pi                        |
|  - Parses driving command                                    |
|  - Controls DC motor PWM                                     |
|  - Controls motor direction                                  |
|  - Controls steering servo                                   |
+-----------------------------+-------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                    Motor Driver + Servo                     |
|                                                             |
|  - Cytron MDD10A motor driver                                |
|  - DC geared motor for rear-wheel driving                    |
|  - Servo motor for front-wheel steering                      |
+-----------------------------+-------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                           RC Car                            |
|  - Moves forward                                             |
|  - Stops                                                     |
|  - Turns left / right                                        |
|  - Performs parking scenario on the test map                 |
+-------------------------------------------------------------+
```

### 2.2 Layered Architecture

```text
Application Layer
└── Smart parking scenario
    ├── Parking space recognition
    ├── RC car position / movement decision
    └── Final parking demonstration

Vision & Decision Layer
└── Raspberry Pi
    ├── Camera input
    ├── OpenCV-based image processing
    ├── YOLO inference test
    ├── Parking area detection
    └── Driving command generation

Communication Layer
└── UART / USB Serial
    ├── Raspberry Pi → ESP32 command transmission
    └── Command format: F / S / L / R / C

Embedded Control Layer
└── ESP32
    ├── Command parsing
    ├── DC motor PWM control
    ├── Motor direction control
    ├── Servo steering control
    └── Integrated driving control

Hardware Layer
└── RC car platform
    ├── Battery
    ├── Fuse
    ├── Power switch
    ├── Power distribution terminal
    ├── DC-DC step-down converter
    ├── Cytron MDD10A motor driver
    ├── DC geared motor
    └── Servo motor
```

---

## 3. Hardware Architecture

### 3.1 Power Flow

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
  │     └── DC Motor
  │
  ├── DC-DC Step-down Converter
  │     ├── ESP32
  │     └── Servo Motor
  │
  └── Raspberry Pi Power Input
```

### 3.2 Control Signal Flow

```text
Raspberry Pi
  ↓ UART / USB Serial
ESP32
  ├── GPIO 25 → Motor Driver PWM
  ├── GPIO 26 → Motor Driver DIR
  └── GPIO 27 → Servo PWM
```

### 3.3 Hardware Components

| Category | Component | Role |
|---|---|---|
| Main Computer | Raspberry Pi | Camera processing and driving decision |
| Embedded Controller | ESP32 | Motor, servo, and low-level control |
| Motor Driver | Cytron MDD10A | DC motor power control |
| Drive Motor | DC geared motor | Rear-wheel driving |
| Steering | Servo motor | Front-wheel steering |
| Power Protection | Fuse | Overcurrent protection |
| Power Control | Switch | Main power on/off |
| Power Conversion | DC-DC step-down converter | Voltage conversion for control modules |
| Vision | Camera module / USB camera | Parking map recognition |

### 3.4 ESP32 Pin Map

| Function | ESP32 GPIO | Description |
|---|---:|---|
| Motor PWM | GPIO 25 | PWM signal for motor driver speed control |
| Motor DIR | GPIO 26 | Direction signal for motor driver |
| Servo PWM | GPIO 27 | PWM signal for steering servo |
| UART RX | TBD | Receive command from Raspberry Pi |
| UART TX | TBD | Send response/debug data to Raspberry Pi |
| GND | GND | Common ground with motor driver and external power modules |

> All control modules must share a common GND when signal communication is used.

---

## 4. Software Architecture

### 4.1 ESP32 Firmware

The ESP32 handles the real-time control part of the RC car.

Main responsibilities:

- Receive command from Raspberry Pi
- Parse driving command
- Generate DC motor PWM signal
- Control motor direction
- Generate servo PWM signal
- Perform integrated drive and steering control
- Support individual hardware tests before final integration

Expected firmware modules:

```text
firmware_esp32/
├── 01_motor_basic_test/
│   └── DC motor forward/stop and PWM control test
│
├── 02_servo_steering_test/
│   └── Left/center/right steering control test
│
├── 03_drive_servo_integrated_test/
│   └── DC motor + servo integrated driving test
│
├── 04_pwm_sweep_test/
│   └── Minimum driving PWM measurement test
│
└── 05_uart_receiver_test/
    └── Raspberry Pi command receiver test
```

### 4.2 Raspberry Pi Software

The Raspberry Pi handles the vision and high-level decision part of the system.

Main responsibilities:

- Capture camera frame
- Check parking lot map visibility
- Process image using OpenCV
- Test YOLO-based object/parking area recognition
- Determine driving command
- Send command to ESP32 through UART / USB Serial

Expected software modules:

```text
raspberry_pi/
├── 01_uart_sender_test/
│   └── Keyboard-based command sender test
│
├── 02_camera_test/
│   └── Camera frame capture test
│
├── 03_opencv_map_test/
│   └── Parking map image processing test
│
└── 04_yolo_inference_test/
    └── YOLO model inference test
```

### 4.3 Final Integration

```text
integrated/
├── esp32_main/
│   └── Final ESP32 motor/servo control firmware
│
└── raspberry_pi_main/
    └── Final Raspberry Pi vision and decision software
```

---

## 5. Communication Protocol

### 5.1 Command Direction

```text
Raspberry Pi  →  ESP32
```

The Raspberry Pi sends a simple command to the ESP32.  
The ESP32 receives the command and controls the motor and servo accordingly.

### 5.2 Command Table

| Command | Meaning | ESP32 Action |
|---|---|---|
| `F` | Forward | Drive DC motor forward |
| `S` | Stop | Stop DC motor |
| `L` | Left | Set servo to left steering angle |
| `R` | Right | Set servo to right steering angle |
| `C` | Center | Set servo to center position |

### 5.3 Example Control Flow

```text
1. Camera captures parking map
2. Raspberry Pi processes image frame
3. Raspberry Pi decides next movement
4. Raspberry Pi sends command to ESP32
5. ESP32 parses command
6. ESP32 controls motor driver and servo
7. RC car moves on the parking map
8. Camera captures updated state
9. Process repeats until parking scenario is completed
```

---

## 6. Test Plan

### 6.1 Hardware Control Tests

| Test Item | Purpose | Status |
|---|---|---|
| DC Motor Basic Test | Check motor driver, PWM, DIR, and motor output | Planned |
| Servo Steering Test | Check left, center, and right steering range | Planned |
| Integrated Drive Test | Check motor driving and steering at the same time | Planned |
| PWM Sweep Test | Measure minimum PWM required for actual driving | Planned |
| Fuse Stability Test | Check power stability during high PWM driving | Planned |

### 6.2 Raspberry Pi Tests

| Test Item | Purpose | Status |
|---|---|---|
| UART Sender Test | Send command from Raspberry Pi to ESP32 | Planned |
| Camera Test | Check camera angle, height, frame, and map visibility | Planned |
| OpenCV Map Test | Detect map lines, parking spaces, or target areas | Planned |
| YOLO Inference Test | Test object recognition model on camera frames | Planned |

### 6.3 Integration Tests

| Test Item | Purpose | Status |
|---|---|---|
| Raspberry Pi–ESP32 Communication Test | Verify command transmission | Planned |
| Vision-Based Command Test | Generate driving commands from camera result | Planned |
| Final Driving Demo | Demonstrate RC car movement on the parking map | Planned |

---

## 7. Test Records

Detailed test records are managed in:

- `docs/test_log_summary.md`
- Notion test log table
- Demo photos and videos

Main test values to record:

- Minimum PWM required for straight driving
- PWM range for stable driving
- Servo center value
- Maximum left steering value
- Maximum right steering value
- Required PWM during left/right turning
- Fuse behavior during high PWM test
- Camera height and angle
- Parking map visibility condition

---

## 8. Troubleshooting

Current troubleshooting topics:

| Date | Issue | Possible Cause | Action | Result |
|---|---|---|---|---|
| 2026-07-02 | Fuse blown during high PWM test | Unstable B+/B- contact or sudden current spike | Reinforce soldering and restart from low PWM | TBD |
| 2026-07-02 | DC-DC converter solder joint disconnected | Weak soldering joint or wiring stress | Resolder and check output voltage | TBD |

Detailed troubleshooting logs are stored in:

```text
docs/troubleshooting.md
```

---

## 9. My Contribution

My main contribution is focused on the hardware control and embedded system part of the RC car.

- Designed and tested the RC car power/control wiring structure
- Connected battery, fuse, switch, power distribution, and motor driver
- Implemented ESP32-based DC motor PWM control
- Implemented servo steering control using ESP32
- Tested motor driver and steering behavior on the actual RC car
- Measured minimum driving PWM and steering-related driving conditions
- Documented hardware issues and troubleshooting process
- Participated in Raspberry Pi–ESP32 communication structure design

---

## 10. Repository Structure

```text
2026-hanium-smart-parking/
├── README.md
├── .gitignore
│
├── docs/
│   ├── development_log.md
│   ├── hardware_wiring.md
│   ├── system_architecture.md
│   ├── test_log_summary.md
│   └── troubleshooting.md
│
├── firmware_esp32/
│   ├── 01_motor_basic_test/
│   ├── 02_servo_steering_test/
│   ├── 03_drive_servo_integrated_test/
│   ├── 04_pwm_sweep_test/
│   └── 05_uart_receiver_test/
│
├── raspberry_pi/
│   ├── 01_uart_sender_test/
│   ├── 02_camera_test/
│   ├── 03_opencv_map_test/
│   └── 04_yolo_inference_test/
│
├── integrated/
│   ├── esp32_main/
│   └── raspberry_pi_main/
│
└── assets/
    ├── diagrams/
    ├── photos/
    └── demo_links/
```

---

## 11. Demo

Demo videos and photos will be organized as external links because large video files should not be directly stored in the GitHub repository.

```text
assets/demo_links/
└── demo_links.md
```

Planned demo materials:

- DC motor PWM test video
- Servo steering test video
- Integrated drive test video
- Camera recognition test video
- Final parking scenario demo video
- Hardware wiring photos
- RC car top-view layout photos

---

## 12. Development Log

Development logs are stored in:

```text
docs/development_log.md
```

Each log should include:

- Today's work
- Issue
- Cause analysis
- Action
- Test result
- Next step

---

## 13. Current Status

| Area | Status |
|---|---|
| RC car platform | In progress |
| Motor driver wiring | In progress |
| ESP32 motor control | In progress |
| Servo steering control | In progress |
| Raspberry Pi camera test | Planned |
| Raspberry Pi–ESP32 communication | Planned |
| Final integration | Planned |

---

## 14. Future Improvements

- Add stable UART protocol between Raspberry Pi and ESP32
- Add feedback message from ESP32 to Raspberry Pi
- Improve PWM tuning for stable turning
- Add camera-based RC car position estimation
- Improve parking space recognition accuracy
- Organize final demo video and presentation materials
