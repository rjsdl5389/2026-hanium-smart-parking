# Production 제어 상태머신

기준일: **2026-09-07**
주 경로: **AUTO_HOST → DIRECT_CONTROL → ESP32 REMOTE_DIRECT**

이 문서는 서로 다른 네 상태를 구분한다. Host authority, host waypoint mission, parking coordinator와 ESP32 vehicle state를 하나의 FSM처럼 섞어 해석하지 않는다.

## 1. Host authority

`host_control.authority.ControlAuthority`가 non-zero 명령의 단일 소유자를 강제한다.

| 상태 | 허용 producer | 출력 |
|---|---|---|
| `DISARMED` | 없음 | zero |
| `MANUAL` | ManualControlProducer | 사람 입력 또는 zero |
| `AUTO_HOST` | AutoControlProducer | fresh Pose 기반 제어 또는 zero |
| `FAULTED` | 없음 | latched zero |

```text
DISARMED → arm_manual → MANUAL
DISARMED → arm_auto   → AUTO_HOST
MANUAL/AUTO_HOST → disarm → DISARMED
ANY → fault/stop → FAULTED
FAULTED → clear_fault → DISARMED → explicit arm
```

manual과 auto를 동시에 활성화할 수 없다. mode handshake의 terminal `ACCEPTED` 전에는 AUTO_HOST를 arm하지 않는다.

## 2. Host waypoint mission

`HostWaypointMission`은 waypoint를 노트북 메모리에만 유지한다. ESP32에는 `WAYPOINT`나 `GO`를 보내지 않는다.

| 상태 | 의미 |
|---|---|
| `EMPTY` | route 없음 |
| `RUNNING` | 현재 target을 camera Pose로 추종 |
| `REPLAN_REQUIRED` | 현재 target/geometry를 직접 계속 추종할 수 없음 |
| `RECOVERY_FAILED` | bounded recovery 예산 소진 |
| `DONE` | 마지막 waypoint 도착, PARKED 후보 |
| `PARKED` | 상위 fresh-Pose 검증까지 완료 |

일반 waypoint 도착은 다음 target으로 진행한다. 마지막 waypoint 도착은 `DONE`일 뿐이며 곧바로 `PARKED`가 아니다.

## 3. Parking coordinator

### 3.1 정상 흐름

```text
INITIAL
→ fresh trusted heading
→ stable fresh Pose 3회
→ SLOT_SELECTED/reserved
→ GLOBAL 또는 ENTRY_STAGING
→ HANDOFF_CAPTURED
→ STOP + fresh Pose
→ PARKING setup/direct plan
→ APPROACH
→ ALIGN
→ ENTRY
→ FINAL
→ zero + physical stop
→ FINAL_POSE_EVAL
→ PARKED_CONFIRMING 1/3 → 2/3 → 3/3
→ PARKED
```

### 3.2 setup과 recovery

direct rear route가 현재 Pose에서 불가능하거나 큰 heading/path deviation이 발생하면:

```text
STOP
→ current route/control invalidation
→ fresh Pose + trusted heading
→ bounded bidirectional setup planner
→ trajectory preflight
→ setup execution
→ STOP + fresh Pose
→ rear planner 재호출
```

setup motion primitive는 forward/reverse straight와 left/right arc이며 최대 1~3 segment다. route/recovery/final-alignment 재시도 상한은 기본 3이며 상한을 늘려 실패를 숨기지 않는다.

### 3.3 작은 final residual

```text
FINAL_POSE_EVAL
├─ geometry accepted → PARKED_CONFIRMING
├─ 작은 보정 가능 → FINAL_ALIGNMENT (bounded)
└─ unsafe/infeasible → safe recovery 또는 WAIT/FAULT
```

`FINAL_ALIGNMENT`는 기본 parking planner가 아니라 작은 residual 전용 fallback이다.

### 3.4 safe terminal wait

경로가 없거나 안전 validator가 거절하면 차는 zero를 유지한다. 대표 stage:

- `WAIT_SAFE_ROUTE`
- `WAIT_SAFE_RECOVERY`
- `WAIT_RECOVERY_EXHAUSTED`
- `WAIT_REPEATED_REPLAN`
- `WAIT_FRESH_HEADING_FAULT`
- `WAIT_COMM_RECOVERY_FAULT`

route_id만 증가시키며 같은 실패 경로를 반복하지 않는다.

## 4. Pose와 heading 상태전이

### 4.1 Initial allocation

`LAST_VALID` heading만으로 새 mission을 시작하지 않는다. body heading source가 `FRONT_CUSHION` 또는 검증된 `TRAJECTORY`이고, 서로 다른 관측 3개가 설정된 position/heading stability 범위에 들어와야 한다.

### 4.2 일반 stale Pose

AUTO_HOST에서 Pose가 stale/invalid이면 HostController는 zero를 보내고 fault를 latch한다. 재출발은 명시적 re-arm과 fresh Pose가 필요하다.

### 4.3 Rear reverse observation loss

ENTRY/FINAL/PARKING 후진 중 unsafe heading source나 stale Pose는 즉시 zero다. 짧은 bounded 시간 동안 fresh body heading을 재획득하고, 실패하면 `REVERSE_HEADING_TIMEOUT` 재계획으로 전환한다.

### 4.4 Route switch

새 route/recovery를 load하기 전에:

```text
DIRECT_CONTROL zero
→ controller state reset
→ previous Pose clear
→ route load
→ new camera observation
→ non-zero 허용
```

같은 scheduler tick에서 stale/computed Pose로 다시 출발하지 않는다.

## 5. Direction change

PoseController가 forward↔reverse 변화를 감지하면 `DIRECTION_CHANGE_STOP`을 반환한다. HostController는 zero를 전송하고 Pose source를 clear한다. 다음 non-zero는 별도 fresh camera frame 뒤에만 가능하다.

이 interlock은 Motor DIR을 non-zero PWM 상태에서 즉시 뒤집는 것을 막는다.

## 6. Deviation과 completion 순서

- terminal capture/completion 조건을 일반 intermediate deviation보다 먼저 평가한다.
- handoff 근처 overshoot는 capture tolerance 안이면 과거 waypoint를 재획득하지 않고 STOP→fresh Pose→parking으로 전환한다.
- 중간 waypoint의 실제 path deviation은 기존 replan 동작을 유지한다.
- same target, same reason, 거의 같은 Pose와 실질적으로 동일한 route가 반복되면 direct parking/setup으로 전환하거나 safe WAIT/FAULT한다.

## 7. Boundary

runtime boundary는 bbox가 아니라 physical vehicle footprint를 사용한다.

- measurement-aware initial hard tolerance: 20 mm
- 추가 uncertainty band: 10 mm
- predictive guard: 진행 방향에서 hard boundary 도달 전 zero/replan
- 의미 있는 hard excursion: 즉시 zero + terminal fault

tolerance는 safety 판정에만 적용하고 map/planner geometry를 늘리지 않는다.

## 8. Communication recovery

```text
RUNNING
→ COMM loss
→ Backend hold_control(zero latch)
→ ESP32 COMM_TIMEOUT/safeStop
→ socket/session 폐기
→ HELLO + new session identity
→ RESET terminal ACK
→ SET_MODE REMOTE_DIRECT terminal ACK
→ WAIT_FRESH_POSE
→ existing slot/context 검증
→ current Pose route preflight
→ AUTO_PENDING
→ fresh observation
→ zero latch release + AUTO_HOST
```

지연된 old-session ACK는 새 협상을 완료할 수 없다. 중복 recovery callback은 같은 in-flight transaction에 합류한다. `PARKED`와 명시적 terminal fault는 reconnect로 부활하지 않는다.

## 9. ESP32 state

Firmware의 vehicle state는 actuator/통신 상태다.

- `BOOT`
- `WIFI_CONNECTING`
- `SYNCING`
- `READY`
- `MOVING`
- `WAITING`
- `EMERGENCY_STOP`
- `COMM_TIMEOUT`
- `ERROR`

부팅, TCP 연결/동기화, RESET, timeout과 STOP은 모두 `actuator_safe_stop()`을 통과한다. `SET_MODE(REMOTE_DIRECT)`가 ACCEPTED되고 유효한 current-session `DIRECT_CONTROL`이 오기 전에는 motor non-zero를 허용하지 않는다.

## 10. Legacy 경계

`WAYPOINT_AUTO`, `WAYPOINT`, `WAIT`, `GO`, ARRIVED/EVENT_ACK 관련 parser와 상태는 하위호환/실험 이력이다. production rear parking은 Host mission이 도착을 판단하고 ESP32에는 `DIRECT_CONTROL`만 스트리밍한다. Firmware의 `ENABLE_WAYPOINT_AUTO_CONTROL=0`을 유지한다.
