# 안전 및 Fail-safe 계약

기준일: **2026-09-07**
production 경로: **AUTO_HOST → DIRECT_CONTROL → REMOTE_DIRECT**

## 안전 책임 분리

노트북은 관측·경로·제어 수준의 안전을 담당하고 ESP32는 통신·출력 수준의 마지막 정지를 담당한다. Dashboard, Redis와 PPO는 안전정지 경로의 필수 의존성이 아니다.

| 계층 | 차단 조건 | 동작 |
|---|---|---|
| Perception | stale/invalid Pose, critical heading 부재 | zero, fresh observation 대기 또는 fault/replan |
| Planning | map/slot/obstacle/curvature/reachability 위반 | route load 전 reject, zero 유지 |
| Host control | authority 없음, mission 없음, direction change | 명시적 `DIRECT_CONTROL(0,0)` |
| Backend transport | RX timeout, socket/session 교체 | 차량별 zero latch, old session 폐기 |
| ESP32 transport | heartbeat timeout | `COMM_TIMEOUT` + `safeStop` |
| ESP32 actuator | `DIRECT_CONTROL` 500 ms timeout | motor zero + servo center |

## Pose 및 heading

- 일반 AUTO 제어는 timestamp가 있는 fresh Pose만 사용한다.
- initial allocation, handoff, setup 완료, rear plan과 recovery/replan 경계는 `FRONT_CUSHION` 또는 검증된 `TRAJECTORY` heading을 요구한다. `LAST_VALID`만으로 새 route를 만들지 않는다.
- rear reverse 중 heading/Pose가 잠시 사라지면 즉시 zero로 정지하고 bounded reacquisition을 수행한다. 복구되지 않으면 parking setup/replan으로 넘긴다.
- route 교체 시 마지막 Pose를 지우므로 새 camera observation 전에는 움직이지 않는다.

## 방향 전환 interlock

`PoseController`가 forward↔reverse 변화를 감지하면 `DIRECTION_CHANGE_STOP` zero를 한 번 출력한다. `HostController`는 그 관측을 폐기한다. 따라서 다음 scheduler tick만으로 반대 방향 non-zero가 재개되지 않고, 별도의 fresh camera frame이 필요하다.

## Route preflight

`pipeline.runner._trajectory_safe()`가 production route load의 공통 gate다. 다음을 검사한다.

- map boundary와 차량 physical footprint
- target 외 점유 슬롯 침범
- 다른 차량 footprint와 measurement margin
- steering/최소 선회반경
- waypoint 구조, 과도한 jump와 총 길이
- 시작 Pose에서 첫 waypoint의 도달가능성
- 전후진 전환점의 정지거리

검증 실패는 `ROUTE_REJECTED` 또는 `RECOVERY_REJECTED` 이벤트와 이유를 남기고 zero를 유지한다. map geometry 자체는 tolerance 때문에 확장하지 않는다.

## Runtime boundary

- physical vehicle footprint로 판정한다.
- `boundary_hard_margin_mm=20`과 measurement uncertainty 10 mm band를 사용한다.
- 예측 guard가 진행 방향의 boundary 침범을 감지하면 실제 hard excursion 전에 zero/replan한다.
- 실제 hard violation은 즉시 zero와 `BOUNDARY_HARD`/fault다.

## 통신 단절과 재접속

```text
COMM loss
→ Backend per-car zero latch
→ ESP32 safeStop
→ old socket/session 무효화
→ reconnect + HELLO
→ 새 session_id/boot_id 확인
→ RESET terminal ACK
→ SET_MODE(REMOTE_DIRECT) ACK
→ fresh Pose/heading
→ 기존 slot intent 검증
→ 현재 Pose 기준 route 재계획
→ zero latch 해제 후 재개
```

ACK가 지연되거나 이전 session에서 도착해도 현재 협상을 완료시킬 수 없다. `PARKED`나 명시적 terminal fault는 재접속으로 다시 움직이지 않는다.

## Parking completion

`FINAL` waypoint 도착만으로 `PARKED`가 아니다.

1. zero와 physical stop 확인
2. fresh Pose로 slot depth/lateral footprint/heading 평가
3. 필요할 때만 bounded `FINAL_ALIGNMENT`
4. 서로 다른 fresh Pose 3개 연속 acceptance
5. `PARKED` 확정 및 verified obstacle Pose 보존

## 현재 한계

- camera-only 정적 차량은 stationary/slot geometry/연속 관측 후 `VISION_OCCUPIED`로 확정되고 allocator와 `STATIC_PARKED` obstacle에 반영된다.
- 단, 점유 확정 전 allocation을 막는 gate는 없다. `VISION_SLOT_OCCUPIED` 확인 전 자율차를 활성화하면 점유 확정 전의 슬롯이 배정될 수 있으므로 검증된 운용 순서를 지켜야 한다.
- 장애물 geometry는 정상 `PARKED`, 확정된 `STATIC_PARKED`, 또는 fresh trusted heading이 있는 다른 차량에 대해 적용된다. heading이 불확실한 bound 차량은 새 route를 fail-safe로 막는다.
- production은 한 번에 AUTO_HOST 차량 한 대만 움직이는 Level 1/2 정책이다. 동시 다중차량 autonomous collision avoidance 완료를 의미하지 않는다.
- CAR_01 encoder는 movement/stall/stiction 보조 신호이며, camera Pose 폐루프를 대체하지 않는다. encoder가 없는 CAR_02는 별도 firmware feature flag로 해당 의존성을 끈다.
