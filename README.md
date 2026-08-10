# 2026 한이음 자율주행 기반 지능형 주차 운영 시스템

> 고정 카메라 기반 전역 인식 · 주차면 배정 · 경로/waypoint 생성 · 노트북 상위 제어 · ESP32 차량 구동을 통합하는 축소형 스마트 주차 테스트베드

## 현재 기준 상태 — 2026-08-10

현재 차량 제어의 **주 통합 경로는 AUTO_HOST**다.

```text
고정 카메라
→ YOLO / OpenCV / Homography
→ Vehicle Pose (x, y, heading)
→ 주차면 배정 / Route / Waypoint
→ 노트북 HostController
→ throttle / steering 계산
→ Wi-Fi TCP / NDJSON / DIRECT_CONTROL
→ ESP32 REMOTE_DIRECT
→ DC모터 / 서보 / 엔코더
```

ESP32가 전역 waypoint 판단을 수행하는 구조가 아니라, **노트북이 카메라 Pose와 waypoint를 이용해 제어값을 계산하고 ESP32는 저수준 구동·즉시 안전정지를 담당**하는 구조를 현재 통합 기준으로 사용한다.

기존 `WAYPOINT`, `WAIT`, `GO` 프로토콜/펌웨어 코드는 호환성 및 대안 비교를 위해 유지한다. SW팀의 waypoint 구현 방식과 최종 통합 시 비교 후 단일 구조로 확정한다.

## 실차 검증 완료

- 노트북 ↔ ESP32 Wi-Fi/TCP 연결
- `HELLO` / `HELLO_ACK` / `STATUS` / `HEARTBEAT`
- `SET_MODE → REMOTE_DIRECT`
- `DIRECT_CONTROL` 스트리밍
- 통신단절/재접속 안전정지
- ESP32 재부팅 후 세션 재동기화
- MANUAL_WASD 실차 전진/후진/좌우 조향
- STOP/HOLD 및 키 해제 시 0/중앙 복귀
- MANUAL_WASD ↔ AUTO_HOST 전환 구조
- AUTO 전환 시 fresh camera pose 전까지 `AUTO_PENDING`
- 수동 제어 전용 `max_throttle=1.0`, reverse 허용
- AUTO_HOST 기본 `max_throttle=0.40`, reverse 비허용 유지
- 최종 회귀 테스트 **164/164 PASS**

테스트 구성:

```text
controller      32
host_control    59
integration     24
comm            31
pipeline        18
------------------
total          164
```

## 현재 다음 단계

SW팀에서 별도로 구현한 **마우스 클릭 waypoint 주행**을 최신 차량 제어/카메라 코드와 다시 연결해 종단 간 동작을 확인한다.

```text
카메라 Pose
→ 마우스 클릭 waypoint
→ 최신 통합 Host/통신 계층
→ 실제 ESP32
→ 실제 RC카 주행
```

이 단계에서 실제 회전반경이 여전히 크면 서보 운용각만 재조정한다. 제어 코드 구조는 먼저 유지한다.

## 수동/자동 제어 모드

### MANUAL_WASD

ESP32가 READY가 되면 카메라나 mission이 없어도 수동제어를 사용할 수 있다.

- `W`: 전진
- `S`: 후진
- `A/D`: 좌/우 조향
- `Space`: STOP/HOLD
- `F1`: MANUAL
- `F2`: AUTO

수동모드는 카메라 학습용 위치 조정, 초기 배치, 실차 점검 및 개발 중 비상 수동제어에 사용한다.

### AUTO_HOST

노트북이 현재 Pose와 waypoint를 바탕으로 제어값을 계산한다.

MANUAL → AUTO 전환은:

```text
zero
→ manual loop 종료
→ AUTO_PENDING
→ fresh camera pose 수신
→ AUTO scheduler 시작
→ AUTO_HOST
```

순서로 동작해 오래된 Pose에 의한 즉시 fault를 방지한다.

## 하드웨어 기준

| 기능 | 값 |
|---|---:|
| Motor PWM GPIO | 25 |
| Motor DIR GPIO | 26 |
| Servo PWM GPIO | 27 |
| Encoder A/B | 34 / 35 |
| PWM | 20 kHz, 8-bit |
| 직진 기본 duty | 27 |
| 약회전 기본 duty | 45 |
| 강회전 기본 duty | 55 |
| Servo center | 86° |
| Left weak / strong | 68° / 50° |
| Right weak / strong | 104° / 122° |
| 기계 한계 확인값 | 약 22° / 130° |

기계 한계값은 정상 운용값으로 사용하지 않는다.

## 저장소 구조

```text
.
├─ README.md
├─ docs/
├─ integrated/
│  ├─ host/                 # 최신 노트북 통합 코드
│  │  ├─ controller/
│  │  ├─ host_control/
│  │  ├─ control/
│  │  ├─ integration/
│  │  ├─ comm/
│  │  ├─ pipeline/
│  │  ├─ parking/
│  │  └─ cv/
│  └─ esp32_main/           # ESP-IDF 차량 펌웨어
└─ remote-direct-bridge/    # 이전/독립 개발용 REMOTE_DIRECT 브리지
```

`remote-direct-bridge`는 실차 수동제어 검증 이력을 보존하는 개발 도구이며, 현재 통합 개발의 기준 코드는 `integrated/host`다.

## 보안/용량 원칙

다음 파일은 Git에 올리지 않는다.

- 실제 `app_config.h`
- `.env`
- Wi-Fi 비밀번호/로컬 서버 주소
- `.conda_backend`, venv
- ESP-IDF `build/`, `managed_components/`
- YOLO weight (`*.pt`) 및 영상/런타임 산출물
- DB, cache, backup

모델 weight는 별도 전달/배포하고 저장소에는 경로와 사용법만 기록한다.

## 주요 문서

- [`docs/implementation_status.md`](docs/implementation_status.md): 현재 구현 상태의 단일 기준
- [`docs/integration_status_2026-08-10.md`](docs/integration_status_2026-08-10.md): 이번 통합/HIL 마일스톤
- [`docs/system_architecture.md`](docs/system_architecture.md): 현재 시스템 구조
- [`docs/development_log.md`](docs/development_log.md): 일자별 개발 이력
- [`docs/test_log_summary.md`](docs/test_log_summary.md): 검증 결과
- [`docs/troubleshooting.md`](docs/troubleshooting.md): 재현 가능한 문제/해결