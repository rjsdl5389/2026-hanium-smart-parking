# 시스템 아키텍처

기준일: **2026-08-10**

## 핵심 원칙

- 고정 카메라와 노트북이 전역 인식과 판단을 담당한다.
- ESP32는 차량의 저수준 actuator 출력과 즉시 안전동작을 담당한다.
- Raspberry Pi는 사용하지 않는다.
- 현재 자동주행 통합 기준은 **AUTO_HOST**다.

## 전체 흐름

```text
고정 카메라
    ↓
YOLO / OpenCV
    ↓
Homography
    ↓
Vehicle Pose (x_cm, y_cm, heading)
    ↓
주차면 상태 / 배정
    ↓
Route / Waypoint
    ↓
노트북 HostController
    ├─ AutoControlProducer
    ├─ ManualControlProducer
    ├─ Authority
    └─ Safety / freshness
    ↓
RemoteDirectSession
    ↓
VehicleServer
    ↓ Wi-Fi TCP / NDJSON
ESP32 REMOTE_DIRECT
    ├─ 명령 검증
    ├─ timeout / safeStop
    ├─ Motor PWM/DIR
    ├─ Servo PWM
    └─ Encoder
    ↓
RC카
    ↓
고정 카메라 재관측
```

## 제어 권한

### MANUAL_WASD

개발/점검용이다. ESP32 READY 이후 mission이나 camera pose가 없어도 사용 가능하다.

수동모드에서만 별도의 immutable config 복사본을 사용한다.

```text
max_throttle = 1.0
allow_reverse = True
```

원본 AUTO 설정은 수정하지 않는다.

### AUTO_HOST

노트북이 waypoint와 최신 pose를 이용해 throttle/steering을 계산한다.

```text
max_throttle = 0.40
allow_reverse = False
```

MANUAL → AUTO 전환 직후에는 scheduler를 바로 시작하지 않고 `AUTO_PENDING` 상태에서 fresh pose를 기다린다.

## 안전 전환

```text
AUTO → MANUAL
zero
→ auto scheduler stop
→ disarm
→ arm_manual
→ manual loop

MANUAL → AUTO
manual neutral
→ manual loop stop
→ zero
→ disarm
→ arm_auto
→ AUTO_PENDING
→ fresh camera pose
→ scheduler start
→ AUTO_HOST
```

## ESP32 역할

현재 주 통합 경로에서는 ESP32가 waypoint 기반 전역 위치제어를 수행하지 않는다.

ESP32의 핵심 책임:

- Wi-Fi/TCP 연결
- HELLO/STATUS/HEARTBEAT
- REMOTE_DIRECT 세션
- DIRECT_CONTROL 최신값 적용
- command timeout
- motor/servo mapping
- encoder raw count
- safeStop
- 재접속/재부팅 안전상태

기존 WAYPOINT/WAIT/GO 관련 프로토콜 코드는 대안 설계와 SW팀 구현 비교를 위해 유지한다.

## 조향/모터 보정

```text
PWM straight default     27
PWM weak-turn default    45
PWM strong-turn default  55

servo left strong        50°
servo left weak          68°
servo center             86°
servo right weak         104°
servo right strong       122°
```

waypoint 실차 주행에서 회전반경이 큰 경우 구조를 먼저 바꾸지 않고 서보 운용각을 단계적으로 조정한다.