# 2026 Hanium Smart Parking RC Car

## 1. Project Overview

This project aims to implement a smart parking RC car system using camera-based parking space recognition and embedded motor control.

The Raspberry Pi is responsible for camera processing and decision making, while the ESP32 controls the DC motor, motor driver, and steering servo.

## 2. System Architecture

```text
Camera / Parking Lot Map
        ↓
Raspberry Pi
- Camera input
- Image processing
- Parking space recognition
- Driving command decision
        ↓ UART / USB Serial
ESP32
- DC motor PWM control
- Servo steering control
- Motor driver control
        ↓
RC Car

## 3. Hardware Components
Category	Component
Main Controller	Raspberry Pi
Motor Controller	ESP32
Motor Driver	Cytron MDD10A
Drive Motor	DC geared motor
Steering	Servo motor
Power	Battery, fuse, switch, DC-DC step-down converter
Vision	Camera module / USB camera
4. Software Structure
firmware_esp32/
- Motor PWM control
- Servo steering control
- UART command receiver
- Integrated driving firmware

raspberry_pi/
- Camera test
- OpenCV processing
- YOLO inference test
- UART command sender

integrated/
- Final integrated ESP32 firmware
- Final Raspberry Pi control code
5. My Contribution
Designed and tested the RC car power/control wiring structure
Implemented ESP32-based DC motor PWM control
Implemented servo steering control using ESP32
Tested motor driver and steering behavior on the actual RC car
Measured minimum driving PWM and steering-related driving conditions
Participated in Raspberry Pi–ESP32 communication structure design
6. Test Items
Test Item	Description	Status
DC Motor Basic Test	Test forward/stop control using PWM and DIR pins	Planned
Servo Steering Test	Test left, center, right steering angles	Planned
Integrated Drive Test	Drive motor + steering servo combined test	Planned
PWM Sweep Test	Measure minimum PWM required for actual driving	Planned
UART Command Test	Send driving commands from Raspberry Pi to ESP32	Planned
Camera Test	Check camera position, frame, and map visibility	Planned
Final Driving Demo	Demonstrate RC car movement on the parking map	Planned
7. Troubleshooting Summary
Date	Issue	Possible Cause	Action	Result
2026-07-02	Fuse blown during high PWM test	Unstable B+/B- contact or sudden current spike	Reinforce soldering and restart from low PWM	TBD
8. Demo

Demo videos and photos will be organized in assets/demo_links/.

9. Development Log

Detailed development logs are stored in docs/development_log.md.


README는 처음부터 완벽할 필요 없음.  
지금은 “프로젝트가 뭔지, 구조가 뭔지, 네가 뭘 맡았는지”만 보이면 됨.

---

# 5. .gitignore 만들기

프로젝트 폴더에 `.gitignore` 파일 만들고 아래 내용 넣어.

```gitignore
# OS files
.DS_Store
Thumbs.db

# VSCode
.vscode/

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.venv/
venv/

# Arduino / PlatformIO
.pio/
.vscode/.browse.c_cpp.db*
.vscode/c_cpp_properties.json
.vscode/launch.json
.vscode/ipch/

# Build files
build/
dist/

# Large media files
*.mp4
*.mov
*.avi
*.mkv

# Temporary files
*.tmp
*.log