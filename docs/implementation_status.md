# 구현 상태 단일 기준

기준일: 2026-07-31
기준 브랜치: `integrate-v5.3.1`

이 문서는 저장소의 구현 상태를 판정하는 단일 기준이다. 다른 문서와 내용이 충돌하면 이 문서를 우선하고, 충돌 문서를 수정한다.

## 상태 정의

| 상태 | 의미 |
|---|---|
| 완료 | 코드 구현 및 필요한 실차·통합 검증 완료 |
| 부분 구현 | 파싱·상태 저장 등 일부 코드만 존재 |
| 예정 | 설계 또는 인터페이스만 존재 |
| archive | 과거 개발 이력이며 현재 설정 기준이 아님 |

## 현재 완료 기능

- ESP32 Wi-Fi STA 연결
- 노트북 TCP 서버 연결 및 재연결
- NDJSON 스트림 분리
- HELLO / HELLO_ACK
- session_id / boot_id
- HEARTBEAT / COMM_TIMEOUT
- STATUS 주기 전송
- 신뢰성 명령 seq, 재전송, 중복 방지
- SET_MODE(REMOTE_DIRECT)
- DIRECT_CONTROL 최신값 처리
- 전진·후진
- 누적 좌우 조향
- STOP / RESET
- 직접제어 timeout
- 연결 단절 안전정지
- 새 session 자동 재출발 방지
- 엔코더 quadrature raw count
- 브리지 GUI
- 브리지 테스트 51개
- ESP-IDF v6.0.2 빌드 및 실차 시험

## 부분 구현

### WAYPOINT

구현:

- JSON 필드 검증
- route_id / waypoint_id 검증
- target 저장
- WAITING 전환
- 중복 seq 및 stale route 처리

미구현:

- 현재 Pose 입력
- 위치·heading 오차 계산
- 조향 및 속도 제어
- 실제 waypoint 추종
- 도착 판정

### WAIT / GO

구현:

- WAIT 안전정지
- target 유지 또는 교체
- GO 상태·target·route 검증

제한:

- 실제 waypoint 제어 루프가 없으므로 GO는 안전하게 HOLD 처리한다.
- `ENABLE_WAYPOINT_AUTO_CONTROL=0`이 현재 정상 설정이다.

## 미구현

- POSE_UPDATE 메시지
- pose_seq 및 Pose freshness
- POSE_TIMEOUT
- ARRIVED
- EVENT_ACK
- 엔코더 RPM·속도·거리 환산
- 카메라 Pose와 엔코더 비교
- 경로 생성기와 ESP32 종단 간 연동
- 장애물 재경로
- 다중 차량 협력 제어

## 실제 펌웨어 수신 메시지

- HELLO_ACK
- HEARTBEAT
- WAYPOINT
- WAIT
- GO
- STOP
- RESET
- SET_MODE
- DIRECT_CONTROL

`POSE_UPDATE`와 `EVENT_ACK`는 현재 수신 enum에 없다.

## 현재 브리지 송신 메시지

- HELLO_ACK
- HEARTBEAT
- SET_MODE
- DIRECT_CONTROL
- STOP
- RESET

현재 `remote-direct-bridge`에는 WAYPOINT·WAIT·GO builder와 자동주행 orchestration이 없다.

## 실제 FreeRTOS 실행 구조

- CommunicationTask
- HeartbeatWatchdog
- VehicleControlTask
- TransmitTask
- 엔코더 GPIO ISR

아직 없는 구조:

- SensorTask
- DiagnosticTask
- Pose latest-value queue
- ARRIVED event retry task

## 현재 하드웨어 기준

- Motor PWM: GPIO25
- Motor DIR: GPIO26
- Servo PWM: GPIO27
- Encoder A: GPIO34
- Encoder B: GPIO35
- PWM: 20 kHz, 8-bit
- 직진 기본: 27
- 중간 조향: 45
- 최대 조향: 55
- Servo: 50 / 68 / 86 / 104 / 122°
- 전진 HIGH, 후진 LOW
- 전진 encoder positive, 후진 negative

## 공개 설정 안전 기본값

```c
#define ENABLE_ACTUATOR_OUTPUT 0
#define ENABLE_WAYPOINT_AUTO_CONTROL 0
#define DAY3_ALLOW_GO_WITHOUT_POSE 0
```

실제 출력은 사용자가 로컬 `app_config.h`에서 명시적으로 활성화한다.

## 완료라고 기록하면 안 되는 항목

다음 표현은 현재 시점에 사용하지 않는다.

- waypoint 자율주행 완료
- 카메라 Pose 연동 완료
- ARRIVED 이벤트 완료
- 엔코더 거리 제어 완료
- 장애물 재경로 완료
- 다중 차량 제어 완료
- 전체 주차 데모 완료
