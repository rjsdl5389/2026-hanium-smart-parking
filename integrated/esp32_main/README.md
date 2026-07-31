# ESP32 펌웨어

## 현재 범위

완료:

- Wi-Fi / TCP client
- NDJSON parser
- HELLO / STATUS
- HEARTBEAT timeout
- REMOTE_DIRECT
- 모터·서보 출력
- 엔코더 raw count
- STOP·RESET·재접속 fail-safe

부분 구현:

- WAYPOINT parser
- target 저장
- WAIT / GO 상태 검증

미구현:

- POSE_UPDATE
- waypoint 제어 루프
- 도착 판정
- ARRIVED
- 속도·거리 환산

## 설정

```powershell
cd main
Copy-Item app_config.example.h app_config.h
```

공개 기본값:

```c
ENABLE_ACTUATOR_OUTPUT 0
ENABLE_WAYPOINT_AUTO_CONTROL 0
DAY3_ALLOW_GO_WITHOUT_POSE 0
```

실차 수동제어 시험에서만 로컬 `ENABLE_ACTUATOR_OUTPUT`을 1로 변경한다.

## 빌드

```powershell
idf.py build
```

## 플래시

```powershell
idf.py -p COM6 flash monitor
```

## 핀

- PWM 25
- DIR 26
- Servo 27
- Encoder A 34
- Encoder B 35

## 보정

- PWM 27 / 45 / 55
- Servo 50 / 68 / 86 / 104 / 122°
- 20 kHz, 8-bit
- HIGH forward, LOW reverse

## 안전

WAYPOINT 제어 루프가 구현되기 전:

```c
ENABLE_WAYPOINT_AUTO_CONTROL 0
```

GO는 HOLD하고 WAITING을 유지한다.
