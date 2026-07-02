# System Architecture

## 1. Overall Structure

```text
Camera
  ↓
Raspberry Pi
  ↓
UART / USB Serial
ESP32
  ↓
Motor Driver + Servo Motor
  ↓
RC Car Movement

2. Role Separation
Raspberry Pi
Camera input
Image processing
Parking map recognition
Parking space decision
Driving command generation
ESP32
Receive driving commands
Control DC motor PWM
Control motor direction
Control steering servo
Handle low-level driving behavior
3. Command Example
Command	Meaning
F	Forward
S	Stop
L	Left steering
R	Right steering
C	Center steering
4. Reason for Architecture

The Raspberry Pi handles relatively heavy vision processing, while the ESP32 handles real-time motor and servo control. This separation makes debugging easier and improves modularity.


---

# 11. Git 초기화하기

이제 프로젝트 폴더에서 Git을 시작함.  
GitHub 공식 문서에서도 로컬 코드가 아직 Git으로 관리되지 않는다면 프로젝트 루트에서 `git init`으로 초기화한다고 설명함. :contentReference[oaicite:2]{index=2}

프로젝트 폴더 안에서:

```bash
git init