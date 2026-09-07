# 2026 한이음 자율주행 기반 지능형 주차 운영 시스템

> 고정 카메라 전역 인식과 노트북 기반 폐루프 제어로 RC카를 주차시키는 축소형 스마트 주차 테스트베드

최종 문서 기준일: **2026-09-07**

## 최종 시스템 구조

```text
고정 카메라
→ YOLO / OpenCV
→ Homography
→ Vehicle Pose (x, y, heading)
→ 슬롯 상태 / 슬롯 배정
→ Route / Waypoint
→ HostController
→ throttle / steering
→ Wi-Fi TCP / NDJSON / DIRECT_CONTROL
→ ESP32 REMOTE_DIRECT
→ DC Motor / Servo
→ 차량 이동
→ 카메라 재관측
```

노트북은 전역 인식, 슬롯 배정, 경로 생성, Pose 기반 폐루프 제어와 복구·재계획을 담당한다. ESP32는 세션이 유효한 `DIRECT_CONTROL`만 액추에이터에 적용하고, 통신 또는 명령 스트림이 끊기면 독립적으로 즉시 정지한다.

**Production 자동주행 경로는 `AUTO_HOST → DIRECT_CONTROL → REMOTE_DIRECT`다.** `WAYPOINT_AUTO`와 `WAYPOINT`/`GO`/`WAIT` 처리는 호환성과 실험 이력 때문에 남아 있지만 production wire에는 사용하지 않는다.

## 제어와 안전의 핵심

- `HostController`가 fresh camera Pose와 현재 waypoint로 heading error, arc cross-track error, curvature feed-forward, throttle/steering을 계산한다.
- 실행 가능한 모든 production route는 load 전에 map, 차체 footprint, 점유 슬롯, 다른 차량 footprint, curvature, waypoint jump와 첫 waypoint 도달가능성을 검사한다.
- stale/invalid Pose는 non-zero 출력을 허용하지 않는다. 후진 주차 중 일시적인 heading 손실도 먼저 zero로 정지하고 bounded fresh-heading 복구 또는 재계획으로 전환한다.
- forward↔reverse 전환에는 zero-command interlock을 넣고, 전환을 만든 관측을 폐기해 새 camera observation 전에는 반대 방향으로 출발하지 않는다.
- 통신 장애 시 Backend와 ESP32가 각각 zero/safeStop을 수행한다. 재접속 뒤에는 새 `session_id`와 `boot_id`를 검증하고 `RESET → SET_MODE(REMOTE_DIRECT)` 협상, fresh Pose 확보, 현재 위치 기준 재계획을 거쳐야 한다.
- 최종 `PARKED`는 위치 하나만으로 결정하지 않는다. 물리적 정지 확인, 슬롯 footprint/depth/heading 검사와 서로 다른 fresh Pose 3개 연속 확인을 사용한다.

자세한 내용은 [시스템 아키텍처](docs/system_architecture.md), [제어 상태머신](docs/control_state_machine.md), [통신 프로토콜](docs/communication_protocol.md), [안전 계약](docs/safety_and_failsafe.md)을 참고한다.

## 현재 구현 상태

| 영역 | 상태 | 범위 |
|---|---|---|
| Camera→Pose→Route→HostController→ESP32 | 완료·실차 검증 | 단일 AUTO_HOST 차량의 후면주차 |
| Parking setup/recovery/replanning | 완료·실차 검증 | bounded 시도, 불가능하면 zero/WAIT/FAULT |
| TCP/NDJSON session recovery | 완료·HIL 검증 | zero latch, RESET/SET_MODE, stale ACK 차단 |
| Route preflight safety | 완료·자동 회귀 | unsafe route는 load 전에 reject |
| Dashboard REST/WebSocket adapter | 구현 완료 | Redis는 배포 시 선택, 제어 안전 경로와 분리 |
| PPO 환경·정책 | 구현·시뮬레이션 검증 | model/dependency가 없으면 deterministic heuristic |
| 정적 수동 배치 차량의 슬롯 자동 점유 | **미완료** | `VISION_OCCUPIED` production 분류/allocator 동기화 없음 |
| 다중 차량 자율주행 | 부분 완료 | 두 번째 차량 zero 대기와 장애물 검사는 있으나 동시 자율주행 검증 아님 |

현재 코드가 보장하는 정적 장애물은 **정상 `PARKED` 판정으로 저장된 차량 Pose** 또는 fresh trusted heading을 가진 다른 bound 차량이다. 카메라에 보이는 임의의 수동 배치 차량을 자동으로 `VISION_OCCUPIED`로 선언하는 기능과 동일하지 않다.

## 실차 E2E 증거와 표현 범위

단일차량 실차에서 다음 경로가 확인됐다.

```text
GLOBAL / entry staging
→ parking setup
→ APPROACH → ALIGN → ENTRY → FINAL
→ physical stop + fresh Pose evaluation
→ PARKED_CONFIRMING 3/3
→ PARKED
```

대표 기록:

- `run_20260831_002703`: A2 `PARKED`, fresh 확인 3/3
- `run_20260903_230921`: A2 `PARKED`, stale-Pose 복구 후 완료
- `run_20260904_000722`: B1 `PARKED`, boundary/final-alignment 복구 후 완료
- `run_20260904_183055`, `run_20260904_183503`: entry staging부터 A2 후면주차까지 `PARKED`

이 증거는 **두 차량 동시 자율주행 성공**을 뜻하지 않는다. 또한 정적 차량을 카메라만으로 `VISION_OCCUPIED` 처리해 allocator에서 제외한 실차 성공은 현재 코드/로그로 입증되지 않았으므로 최종 보고서의 완료 항목으로 쓰지 않는다.

## PPO와 HIL runtime

`rl/`에는 MaskablePPO 환경, 학습·평가 코드와 deterministic inference가 있다. production allocator는 정책 파일과 `sb3-contrib`를 모두 사용할 수 있을 때 PPO를 호출하고, 어느 하나라도 없으면 nearest-slot deterministic heuristic으로 안전하게 fallback한다. 어느 경우에도 action mask와 route preflight safety 검사는 유지된다.

현재 Backend venv에는 `sb3-contrib`/`stable-baselines3`가 없어 이번 최종 회귀에서는 heuristic fallback이 사용됐다. 과거 HIL run은 policy provenance를 기록하지 않아 PPO 사용을 사후 확정할 수 없다. 따라서 보고서에는 “PPO 환경·정책 구현 및 시뮬레이션 검증”과 “HIL의 deterministic fallback”을 구분한다.

## Dashboard / Redis / Django Channels

- Django REST API와 `/ws/dashboard/` consumer가 구현돼 있다.
- `REDIS_URL`이 있으면 Redis Channel Layer, 없으면 in-memory layer를 사용한다.
- pipeline의 `DashboardBridge`는 Pose와 이벤트를 best-effort로 broadcast한다.
- Dashboard/Redis 실패는 차량 제어 및 safe-stop 경로를 막지 않는다.
- 프론트엔드 UI의 최종 배포·사용성 검증은 이 저장소의 실차 제어 완료와 별도다.

## Production 실행

실차 production은 Backend 저장소에서 mode를 명시한다.

```powershell
python manage.py run_pipeline `
  --control-mode auto-host `
  --parking-mode rear `
  --calibration <validated-calibration.json> `
  --weights <best.pt> `
  --record runs `
  --record-video `
  --show
```

가중치, calibration, 영상과 run 산출물은 로컬 증빙이며 Git에 포함하지 않는다. 실제 production Backend source는 [`hanium-2026-project/backend`](https://github.com/hanium-2026-project/backend)에서 관리한다. 이 저장소의 `integrated/host`는 통합 이력/스냅샷이며 최신 Backend의 단일 source of truth가 아니다.

## 저장소 구조

```text
.
├─ README.md
├─ docs/                         # 최종 설계·구현·시험 문서
├─ integrated/
│  ├─ host/                      # 과거 통합 스냅샷
│  └─ esp32_main/                # CAR_01 ESP-IDF firmware
└─ remote-direct-bridge/         # 독립 수동/HIL 검증 도구
```

CAR_02의 encoder-disabled firmware는 별도 로컬 workspace로 분리돼 있으며 이 저장소의 CAR_01 firmware와 혼합하지 않는다.

## 주요 문서

- [시스템 아키텍처](docs/system_architecture.md)
- [제어 상태머신](docs/control_state_machine.md)
- [통신 프로토콜](docs/communication_protocol.md)
- [구현 상태](docs/implementation_status.md)
- [안전 및 fail-safe](docs/safety_and_failsafe.md)
- [테스트 로그 요약](docs/test_log_summary.md)
- [개발 로그](docs/development_log.md)
- [트러블슈팅](docs/troubleshooting.md)

## 저장소 보안/용량 원칙

실제 `app_config.h`, `.env`, Wi-Fi 자격증명, 로컬 주소, venv, ESP-IDF `build/`, YOLO weights, 영상, DB와 runtime run은 commit하지 않는다.
