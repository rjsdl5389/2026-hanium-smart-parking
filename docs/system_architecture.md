# 시스템 아키텍처

기준일: **2026-09-07**

## 전체 폐루프

```text
고정 카메라
→ YOLO(rc_car, FRONT_CUSHION) / OpenCV tracking
→ Homography
→ Vehicle Pose (x_mm, y_mm, body heading)
→ 슬롯 상태 / allocator
→ GLOBAL·setup·rear Route / Waypoint
→ trajectory preflight
→ HostController
→ normalized throttle / wire steering
→ VehicleServer
→ TCP / NDJSON / DIRECT_CONTROL
→ ESP32 REMOTE_DIRECT
→ Motor PWM/DIR / Servo
→ 차량 이동
→ 카메라 재관측
```

노트북이 high-level 제어와 위치 폐루프를 소유한다. ESP32는 waypoint의 전역 의미를 해석하지 않고, 현재 session의 최신 `DIRECT_CONTROL`을 출력으로 바꾸며 독립 watchdog과 `safeStop`을 제공한다.

## 실제 source of truth

| 영역 | 저장소/모듈 | 책임 |
|---|---|---|
| Production Backend | `hanium-2026-project/backend` | perception, allocation, planning, control, TCP server |
| Perception | `cv/` | camera capture, YOLO, tracking, association, heading |
| Allocation | `rl/bridge.py`, `rl/inference.py` | action mask, PPO 또는 heuristic 슬롯 선택 |
| Planning | `parking/waypoints.py` | GLOBAL, entry/setup, rear, recovery waypoint |
| Preflight | `parking/trajectory_safety.py` | trajectory 전체 geometry 검증 |
| Control | `controller/`, `host_control/`, `control/` | Pose controller, authority, mission, scheduler |
| Transport | `comm/`, `integration/remote_direct_session.py` | NDJSON, reliable negotiation, streaming |
| Firmware | `integrated/esp32_main` | REMOTE_DIRECT, actuator, encoder, watchdog |
| Dashboard | Django/Channels + `pipeline/dashboard.py` | best-effort 관측·이벤트 표시 |

이 저장소의 `integrated/host`는 과거 통합 스냅샷이다. 최신 production Backend 판단에는 별도 Backend 저장소의 현재 working tree를 사용한다.

## Perception과 binding

1. YOLO가 `rc_car`와 `FRONT_CUSHION`을 검출한다.
2. association이 차량과 전방 표식을 짝지어 body heading을 만든다.
3. bbox 중심 pixel을 Homography로 mm 좌표에 투영하고 보정 offset을 적용한다.
4. ESP32의 HELLO/READY 순서와 entrance의 미바인딩 track을 FIFO로 연결한다.
5. binding 시 이전 track의 heading/sample을 지우고 새 planning epoch를 시작한다.

짧은 heading loss에는 `LAST_VALID`이 일반 관측 연속성을 제공할 수 있으나, initial allocation·handoff·setup 완료·rear/recovery 계획 경계에서는 fresh `FRONT_CUSHION` 또는 검증된 `TRAJECTORY` heading만 허용한다.

## 슬롯 상태와 장애물

allocator의 action mask는 이미 예약/점유된 슬롯을 제외하고, allocation 순간 슬롯을 선점해 이중 배정을 막는다. 정상 `PARKED` 확정 시 fresh Pose를 `_parked_obstacles`에 보존하고 이후 route preflight에서 다른 차량 footprint로 사용한다.

현재 production에는 임의의 수동 배치 차량을 vision만으로 슬롯에 투영해 `VISION_OCCUPIED`로 만드는 경로가 없다. 따라서 “정적 차량 검출 → 슬롯 자동 점유 → allocator 제외”는 구현 완료로 표현하지 않는다. 다른 bound 차량이 fresh trusted Pose를 가지면 obstacle이며, heading이 불확실하면 새 경로를 안전하게 거절한다.

## Allocation: PPO와 fallback

`select_action()`은 model 파일과 MaskablePPO dependency가 모두 있으면 `deterministic=True` PPO inference를 사용한다. 모델 또는 dependency가 없으면 nearest-slot heuristic으로 fallback한다.

두 경로 모두:

- 동일 action mask를 사용한다.
- 빈 슬롯이 없으면 WAIT한다.
- 선택 후 route geometry preflight를 통과해야 한다.

PPO는 슬롯 선택 정책이지 차량 steering controller가 아니다. 실제 HIL 조향은 항상 deterministic `HostController`다.

## Route와 Parking

```text
fresh heading + stable initial Pose
→ slot reservation
→ GLOBAL 또는 ENTRY_STAGING
→ handoff capture
→ STOP + fresh Pose
→ direct rear route 가능성 평가
   ├─ 가능: APPROACH → ALIGN → ENTRY → FINAL
   └─ 불가: bounded bidirectional setup → STOP + fresh Pose → rear replan
→ physical stop
→ FINAL_POSE_EVAL
   ├─ accepted: PARKED_CONFIRMING 3/3 → PARKED
   ├─ small residual: bounded FINAL_ALIGNMENT
   └─ unsafe/infeasible: recovery 또는 safe terminal WAIT/FAULT
```

setup planner는 forward/reverse straight와 left/right arc를 최대 1~3 segment로 탐색한다. deviation/replan budget은 무한 재시도를 막으며 기본 상한은 3이다.

## HostController

HostController는 단일 authority를 선택한다.

- `DISARMED` / `FAULTED`: 항상 zero
- `MANUAL`: WASD producer만 반영
- `AUTO_HOST`: camera Pose와 현재 mission waypoint만 반영

PoseController는 waypoint bearing/body heading, arc tangent와 radial cross-track error, waypoint curvature feed-forward, PD feedback과 phase별 throttle cap을 계산한다. 출력 steering은 ESP32 wire sign으로 변환된 normalized 값이다.

route switch, recovery, direction change와 communication recovery에는 zero와 fresh-observation gate가 있다.

## ESP32

- Wi-Fi TCP client와 NDJSON framing
- HELLO/HELLO_ACK, `boot_id`·`session_id`
- RESET/SET_MODE reliable command 결과
- REMOTE_DIRECT 최신값 slot
- Motor PWM/DIR, Servo mapping
- CAR_01 encoder count 및 stall/stiction 보조
- 500 ms DIRECT_CONTROL deadman
- 1,000 ms heartbeat timeout
- 모든 fault 경로의 motor zero + servo center

`WAYPOINT_AUTO` 관련 enum/parser/legacy FSM은 남아 있지만 `ENABLE_WAYPOINT_AUTO_CONTROL=0`이며 production AUTO_HOST wire에서 사용하지 않는다.

## Dashboard

Django REST, Channels WebSocket과 Redis channel layer는 운영 상태 표시 계층이다. `REDIS_URL`이 없으면 in-memory layer를 사용한다. pipeline broadcast는 best-effort이며 실패해도 camera/control/safe-stop은 계속 동작한다.

## 다중 차량의 정확한 범위

현재 production 정책은 한 번에 AUTO_HOST 차량 한 대만 움직인다. 두 번째 bound 차량은 `WAIT_OTHER_VEHICLE`에서 zero를 유지한다. 슬롯 이중 배정 차단, 다른 차량 footprint preflight와 collision hold/resume 단위 테스트는 존재하지만, 두 차량 동시 자율주행 실차 완료를 주장하지 않는다.
