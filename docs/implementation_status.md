# 구현 상태 단일 기준

기준일: **2026-09-08**
production: **AUTO_HOST + REMOTE_DIRECT**

Backend source of truth: [`release/hanium-2026-final @ 15043f3`](https://github.com/hanium-2026-project/backend/tree/15043f3ec583cdab5f9519cdc3ad2e103dcf8d49)

상태 표기는 `완료`, `부분 완료`, `향후 과제`로 구분한다. source가 남아 있다는 이유만으로 production 기능으로 간주하지 않는다.

## 완료

### 단일차량 perception-to-actuator E2E

- YOLO/OpenCV tracking과 Homography 기반 Vehicle Pose
- `FRONT_CUSHION`/trajectory heading provenance
- stable fresh Pose 이후 슬롯 allocation
- GLOBAL, entry staging, parking setup, rear parking route
- `HostController` Pose 기반 폐루프
- TCP/NDJSON `DIRECT_CONTROL`
- ESP32 `REMOTE_DIRECT` Motor/Servo 출력
- camera 재관측 폐루프
- 여러 실차 run의 `PARKED_CONFIRMING 3/3 → PARKED`

### Parking FSM / recovery

- `APPROACH → ALIGN → ENTRY → FINAL`
- handoff/setup/recovery 경계의 STOP + fresh Pose
- bidirectional setup primitives
- path/heading deviation 재계획
- bounded replan/recovery/final-alignment budget
- physical stop 후 final Pose geometry 평가
- fresh Pose 3개 연속 PARKED 확정

### Safety

- stale/invalid Pose zero
- critical boundary의 fresh heading gate
- forward↔reverse zero interlock + 새 frame 요구
- map/slot/vehicle footprint trajectory preflight
- boundary prediction와 hard stop
- communication loss의 Backend zero latch와 ESP32 safeStop
- session/boot identity와 stale ACK 차단
- reconnect 후 RESET/SET_MODE/fresh Pose/replan
- terminal PARKED/fault의 자동 재출발 금지

### 통신과 Firmware

- Wi-Fi TCP client/server, NDJSON framing
- HELLO/HELLO_ACK
- `boot_id`, `session_id`, seq
- reliable RESET/SET_MODE 결과
- latest-value DIRECT_CONTROL
- heartbeat 1,000 ms watchdog
- DIRECT_CONTROL 500 ms watchdog
- CAR_01 encoder STATUS와 movement/stall/stiction 보조

### Backend API / dashboard adapter

- Django REST API
- Django Channels `/ws/dashboard/`
- Redis Channel Layer 선택 구성
- Redis가 없을 때 in-memory layer
- pipeline Pose/event best-effort broadcast
- dashboard failure와 control/safety path 분리

### Vision slot occupancy / static obstacle

- CAR_ID binding 없는 정적 camera track의 slot geometry 기반 `VISION_OCCUPIED` 확정
- `effective_slot_statuses` overlay를 통한 allocator 후보 제외
- 관측 위치 + slot parking heading 기반 `STATIC_PARKED` planning obstacle
- bbox 일시 유실 release grace와 base 예약/PARKED 상태 보존

## 부분 완료

### PPO

- MaskablePPO 환경, 학습/평가와 deterministic inference 경로는 구현됐다.
- policy artifact와 `sb3-contrib`가 모두 있어야 runtime PPO를 사용한다.
- 현재 Backend venv에는 dependency가 없어 deterministic nearest-slot heuristic으로 fallback한다.
- 과거 HIL recorder에는 policy provenance가 없어 각 run의 PPO 사용을 확정할 수 없다.
- PPO는 allocation 전용이며 HostController/parking control을 대체하지 않는다.

### 다중 차량

- 독립 car/session 상태
- 슬롯 선점에 의한 이중 배정 차단
- 한 차량 AUTO_HOST 실행 중 두 번째 차량 zero 대기
- verified PARKED vehicle obstacle persistence
- fresh trusted other-vehicle footprint preflight
- runtime collision hold/resume 단위 테스트
- camera-only `VISION_OCCUPIED` 슬롯 제외와 `STATIC_PARKED` preflight

위 항목은 동시 2대 autonomous parking 실차 완료가 아니다. 현재 production 정책은 한 번에 한 AUTO_HOST 차량만 움직인다.

### Dashboard

Backend API/consumer/broadcast는 구현돼 있다. 최종 프론트엔드 배포, 장시간 Redis 운영과 공모전 현장 통합 검증은 별도다.

## 향후 과제 / 미구현

- `VISION_OCCUPIED` 확정 전 allocation을 막는 allocation gate. 현재는 “정적 차량 배치 → 점유 확정 → 자율주행 차량 활성화” 운용 순서가 필요하다.
- 두 차량 동시 autonomous route coordination 실차 검증
- current run metadata에 PPO/heuristic provenance 저장
- encoder를 이용한 host 속도 폐루프. 현재 주행 위치 폐루프의 source는 camera Pose다.

## Legacy 코드의 위치

`WAYPOINT_AUTO`, `WAYPOINT`, `GO`, `WAIT` parser/FSM은 호환성과 이력 때문에 남아 있다. 그러나 production rear parking은 `--control-mode auto-host --parking-mode rear`를 명시하고 ESP32로 `WAYPOINT/GO`를 보내지 않는다. Firmware의 `ENABLE_WAYPOINT_AUTO_CONTROL=0`도 이 경계를 보조한다.

## 실차 증거

| Run | 결과 |
|---|---|
| `run_20260831_002703` | A2 PARKED 3/3 |
| `run_20260903_230921` | stale-Pose 복구 후 A2 PARKED |
| `run_20260904_000722` | boundary/final recovery 후 B1 PARKED |
| `run_20260904_183055` | entry staging부터 A2 PARKED |
| `run_20260904_183503` | entry staging부터 A2 PARKED |

이 표는 정적 점유 기능 추가 전의 단일차량 E2E 증거다. Backend final release에 `VISION_OCCUPIED`/`STATIC_PARKED`는 구현되었지만, 이 표는 해당 배치 순서를 포함한 실차 시나리오나 두 차량 동시 자율주행을 입증하지 않는다.

## 최종 회귀 기준

2026-09-07 current working tree:

- 제어·주차 독립 suite: **226/226 PASS**
- 전체 Django suite: **1157/1157 PASS, 1 skip**
- REMOTE_DIRECT bridge suite: **51/51 PASS**
- 기존 failure는 과거 firmware version/PWM 값을 기대한 configuration-contract
  test가 현재 working-tree CAR_01 contract보다 뒤처진 문제였으며, test와 mock
  기대값만 정정했다.

Backend의 P0 production control/parking/communication, 전체 Django 회귀와
REMOTE_DIRECT bridge 회귀에는 실패가 없다.
