# 2026 한이음 자율주행 기반 지능형 주차 운영 시스템

> 고정 카메라 기반 전역 인식, 동적 주차면 배정, waypoint 경로 생성, ESP32 차량 제어를 결합한 축소형 스마트 주차 테스트베드

## 1. 프로젝트 개요

본 프로젝트는 대형 마트·상가 지하주차장과 같은 환경에서 발생하는 주차면 탐색 비효율과 차량 간 충돌 문제를 개선하기 위해, **인프라 기반 협력형 자율주행 주차 시스템**을 축소형 테스트베드로 구현하는 것을 목표로 한다.

고정 카메라가 주차장 전체를 관찰하고, 노트북 상위 제어기가 차량 위치·주차면 상태·충돌 위험을 판단한다. 이후 차량별 주차면과 이동 경로를 생성해 ESP32에 전달하며, ESP32는 waypoint를 추종하면서 실제 모터와 조향 서보를 제어한다.

핵심 시연 시나리오는 다음과 같다.

- RC카가 주차장에 진입한다.
- 카메라가 차량 위치와 주차면 상태를 인식한다.
- 상위 제어기가 적절한 주차면을 배정한다.
- 차량까지의 waypoint 경로를 생성한다.
- ESP32가 waypoint를 추종해 주차를 수행한다.
- 주행 중 장애물 또는 차량 간 충돌 위험이 발생하면 즉시 정지한다.
- 현재 위치를 기준으로 경로를 다시 생성한 뒤 주행을 재개한다.
- 다중 차량 진입 시 슬롯 상태와 공용 구간을 고려해 차량별 WAIT·GO를 제어한다.

---

## 2. 핵심 목표

- 고정 카메라 기반 차량 위치 및 방향 추정
- Homography 기반 픽셀 좌표의 실제 맵 좌표 변환
- 주차면 상태관리와 동적 주차면 배정
- waypoint 기반 전역 경로 생성
- ESP32 기반 하위 주행 제어
- 엔코더 기반 속도·거리 피드백
- 장애물 및 다중 차량 충돌 위험 대응
- 통신 단절·위치 유실·오류 상황의 fail-safe 구현
- React·Django·Redis 기반 관제 대시보드 연동

---

## 3. 전체 시스템 구조

```text
고정 카메라
    ↓
YOLO 차량·전방부 검출
    ↓
Homography 좌표 변환
    ↓
차량 Pose(x, y, heading) 및 주차면 상태
    ↓
노트북 상위 제어기
    ├─ PPO 기반 주차면 배정
    ├─ waypoint 경로 생성
    ├─ Safety Shield 및 충돌 판단
    ├─ 동적 경로 재생성
    └─ Django·Redis·React 관제 시스템
    ↓ Wi-Fi TCP / NDJSON
ESP32 하위 제어기
    ├─ 차량 상태머신
    ├─ waypoint 추종
    ├─ 엔코더 속도·거리 피드백
    ├─ DC모터 PWM·방향 제어
    ├─ 조향 서보 제어
    └─ WAIT·STOP·통신 단절 안전정지
    ↓
RC카 주행 및 주차
```

### 상위 제어기와 하위 제어기의 역할

| 구분 | 주요 역할 |
|---|---|
| 노트북 상위 제어기 | 카메라 인식, 맵 좌표 변환, 주차면 배정, 전역 경로 생성, 충돌 판단, 경로 재생성, 대시보드 |
| ESP32 하위 제어기 | waypoint 추종, 모터·서보 제어, 엔코더 처리, 도착 판정, 즉시 정지, 상태 피드백 |

노트북은 전체 주차장을 기준으로 판단하고, ESP32는 차량 한 대의 실제 움직임과 즉각적인 안전동작을 담당한다.

---

## 4. 차량 위치 및 제어 구조

### 4.1 외부 관측 위치

고정 카메라와 노트북은 차량의 실제 전역 위치를 측정한다.

- YOLO 차량 bounding box 중심: 차량 위치 기준점
- 차량 전방 쿠션 또는 전방 특징: heading 계산 기준점
- Homography 변환 결과: 실제 cm 단위 맵 좌표

### 4.2 내부 주행 상태

ESP32는 엔코더를 이용해 차량의 내부 주행 상태를 추정한다.

- 바퀴 속도
- 이동거리
- 목표 속도와 실제 속도의 차이
- 카메라 갱신 사이의 짧은 구간 이동량

### 4.3 피드백 결합

```text
카메라 Pose = 차량이 실제로 어디 있는가
엔코더 정보 = 차량이 얼마나 움직였다고 판단하는가
```

초기에는 카메라 Pose를 위치와 heading의 주 기준으로 사용하고, 엔코더는 속도와 이동거리 보정에 사용한다. 이후 엔코더와 조향각 기반 지역 odometry를 적용하고, 새 카메라 Pose로 누적 오차를 보정한다.

---

## 5. Waypoint 운용 방식

### 5.1 1차 구현

노트북이 전체 경로를 보관하고 현재 이동할 waypoint를 하나씩 전송한다.

```text
WAYPOINT 전송
→ ESP32 주행
→ ARRIVED 수신
→ 다음 WAYPOINT 전송
```

### 5.2 고도화

다음 waypoint 1~2개를 미리 버퍼링해 연속 주행을 구현한다.

다음 상황에서는 기존 waypoint와 버퍼를 폐기한다.

- STOP
- COMM_TIMEOUT
- ERROR
- 재접속 또는 ESP32 재부팅
- 장애물·충돌 위험에 따른 경로 재생성
- 새로운 route_id 수신

### 5.3 주행 단계

| Phase | 역할 |
|---|---|
| `CRUISE` | 일반 통로 주행 |
| `APPROACH` | 주차면 근처 접근 및 감속 |
| `ALIGN` | 차량과 슬롯 방향 정렬 |
| `ENTRY` | 슬롯 입구 진입 |
| `FINAL` | 슬롯 중심과 최종 heading 정렬 |

차량 상태와 주행 phase는 별도로 관리한다. 예를 들어 차량이 정렬 중 일시정지한 경우 `state=WAITING`, `phase=ALIGN`로 표현한다.

---

## 6. 통신 구조

- 노트북: TCP 서버
- ESP32: TCP 클라이언트
- 네트워크: Wi-Fi
- 메시지 형식: JSON
- 메시지 경계: 줄바꿈 문자 `\n`
- 전송 구조: NDJSON 기반 지속 연결

주요 메시지:

| 방향 | 메시지 | 역할 |
|---|---|---|
| 노트북 → ESP32 | `HELLO_ACK` | 연결 승인 및 session 발급 |
| 노트북 → ESP32 | `POSE_UPDATE` | 카메라 기반 현재 위치·방향 전달 |
| 노트북 → ESP32 | `WAYPOINT` | 목표 위치·방향·속도 전달 |
| 노트북 → ESP32 | `WAIT` | 현재 target을 유지한 채 일시정지 |
| 노트북 → ESP32 | `GO` | 안전조건 확인 후 기존 target 추종 재개 |
| 노트북 → ESP32 | `STOP` | 주행 취소 및 비상정지 |
| 노트북 → ESP32 | `RESET` | 오류·비상정지 해제 후 READY 복귀 |
| ESP32 → 노트북 | `HELLO` | 차량·부팅·최근 상태 동기화 |
| ESP32 → 노트북 | `STATUS` | 차량 상태 및 명령 처리 결과 보고 |
| ESP32 → 노트북 | `ARRIVED` | 현재 waypoint 도착 이벤트 |

상세 명세는 [`docs/communication_protocol.md`](docs/communication_protocol.md)를 참고한다.

---

## 7. 차량 상태머신

주요 상태:

```text
BOOT
WIFI_CONNECTING
SYNCING
READY
MOVING
WAITING
EMERGENCY_STOP
COMM_TIMEOUT
ERROR
```

핵심 안전 원칙:

- 부팅 직후부터 모터 출력 비활성화
- 상태 동기화 전 주행 금지
- STOP은 모든 상태에서 최우선 처리
- WAIT는 target과 phase를 유지
- STOP은 target과 waypoint buffer를 폐기
- COMM_TIMEOUT·ERROR·EMERGENCY_STOP은 GO로 해제 불가
- 통신 또는 Pose가 복구돼도 자동 재출발 금지
- 재접속 후 기존 경로 자동 재개 금지

상세 상태 전이는 [`docs/control_state_machine.md`](docs/control_state_machine.md)를 참고한다.

---

## 8. 동적 경로 재생성

주행 중 장애물 또는 차량 간 충돌 위험이 감지되면 다음 순서로 처리한다.

```text
위험 감지
→ WAIT 전송
→ ESP32 안전정지 및 WAITING 응답
→ 정지된 차량의 최신 Pose 확인
→ 기존 route 폐기
→ 새로운 route_id 발급
→ 새 waypoint 생성 및 전송
→ GO 전송
→ MOVING 재개
```

기존 route의 늦은 waypoint와 ARRIVED는 현재 상태에 반영하지 않는다.

---

## 9. 다중 차량 제어

노트북은 주차장 전체를 관찰하며 차량별 상태와 경로를 관리한다.

- 차량별 `car_id`, `session_id`, `route_id` 관리
- 주차면 `EMPTY / RESERVED / OCCUPIED` 상태관리
- 공용 통로 충돌 위험 판단
- 차량별 WAIT·GO 제어
- 선행 차량 주차 완료 후 후속 차량 경로 재계산

PPO는 차량의 모터 출력을 직접 제어하지 않고, 현재 환경에서 적절한 주차면을 선택하는 상위 정책으로 사용한다.

---

## 10. 주요 기술

| 분야 | 기술 |
|---|---|
| 비전 | OpenCV, YOLO, Homography |
| 주차면 배정 | PPO, Action Mask, 슬롯 상태머신 |
| 경로 생성 | waypoint 기반 경로, A* 기반 확장 |
| 안전 제어 | Safety Shield, WAIT·GO·STOP, fail-safe |
| 임베디드 | ESP32, FreeRTOS, PWM, 엔코더, 상태머신 |
| 통신 | Wi-Fi, TCP, NDJSON |
| 백엔드 | Python, Django, Redis, Django Channels |
| 프론트엔드 | React |
| 개발 언어 | Python, C/C++ |

---

## 11. 하드웨어 구성

| 구분 | 구성 요소 | 역할 |
|---|---|---|
| 차량 제어기 | ESP32 | 통신, 상태머신, 모터·서보 제어 |
| 모터드라이버 | Cytron MD10C | DC모터 PWM·방향 제어 |
| 임시 테스트 드라이버 | BTS7960 | MD10C 적용 전·예비 구동 테스트 |
| 구동부 | DC 기어드모터 | 후륜 구동 |
| 조향부 | 서보모터 | 전륜 조향 |
| 피드백 | 모터 엔코더 | 속도·거리 측정 |
| 전원 | 3S 배터리팩, 퓨즈, 스위치, 전원분배 | 차량 전원 공급 및 보호 |
| 전압 변환 | DC-DC 컨버터 | ESP32·서보 전압 공급 |
| 외부 인식 | 고정 카메라 | 차량·슬롯·장애물 관측 |

현재 ESP32 제어 핀 기준:

| 기능 | GPIO |
|---|---:|
| 모터 PWM | GPIO 25 |
| 모터 DIR | GPIO 26 |
| 서보 PWM | GPIO 27 |
| 엔코더 입력 | 추후 배선 확정 |

---

## 12. 개발 진행 상태

### 설계 및 문서화

| 항목 | 상태 |
|---|---|
| 전체 시스템 아키텍처 | 완료 |
| 노트북–ESP32 TCP 통신 프로토콜 | 완료 |
| ESP32 차량 상태머신 | 완료 |
| FreeRTOS Task·Queue 구조 | 완료 |
| 상위 SW–ESP32 인터페이스 | 완료 |
| 하드웨어 전원·배선 기준 | 완료 |
| 통합 테스트 계획 | 완료 |
| 문제 해결 기준 | 완료 |

### 구현 및 시험

| 단계 | 내용 | 상태 |
|---:|---|---|
| 1 | 시리얼 기반 모터·서보 단독 제어 | 부분 확인 / MD10C 기준 재시험 예정 |
| 2 | Wi-Fi 기반 GO·WAIT·STOP·RESET | 설계 완료 / 구현 예정 |
| 3 | speed·steering 직접 제어 | 구현 예정 |
| 4 | 카메라 Pose 기반 단일 waypoint 이동 | 구현 예정 |
| 5 | 엔코더 기반 속도·거리 보정 | 구현 예정 |
| 6 | 카메라 Pose와 엔코더 비교·보정 | 구현 예정 |
| 7 | 장애물 발생 시 동적 경로 재생성 | 구현 예정 |
| 8 | 다중 차량 협력 제어 | 구현 예정 |
| 9 | waypoint 1~2개 버퍼링 | 고도화 예정 |

현재 단계는 **큰 틀의 설계를 완료하고 MD10C 기반 하드웨어 재시험과 ESP32 통신·상태머신 구현을 시작하는 단계**이다.

상태값은 실제 테스트 결과에 따라 지속적으로 갱신한다.

---

## 13. 상세 문서

| 문서 | 내용 |
|---|---|
| [`docs/system_architecture.md`](docs/system_architecture.md) | 전체 시스템 구조와 상위·하위 제어기 역할 |
| [`docs/communication_protocol.md`](docs/communication_protocol.md) | TCP·NDJSON 메시지, 재전송, 멱등성 및 재접속 명세 |
| [`docs/control_state_machine.md`](docs/control_state_machine.md) | 차량 상태, 명령 허용 조건 및 안전 전이 |
| [`docs/freertos_task_design.md`](docs/freertos_task_design.md) | ESP32 Task·Queue·Notification과 출력 소유권 |
| [`docs/software_interface.md`](docs/software_interface.md) | Pose·Homography·슬롯·route·waypoint 연동 규격 |
| [`docs/hardware_wiring.md`](docs/hardware_wiring.md) | 배터리·MD10C·서보·ESP32·엔코더 배선 기준 |
| [`docs/test_log_summary.md`](docs/test_log_summary.md) | 전체 시험 계획, 측정값 및 통과 기준 |
| [`docs/development_log.md`](docs/development_log.md) | 날짜별 개발 과정과 설계 결정 |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | 하드웨어·통신·인식·제어 문제 해결 절차 |

각 문서는 실제 구현과 시험 결과에 따라 지속적으로 갱신한다.

---

## 14. 저장소 구조

```text
2026-hanium-smart-parking/
├─ README.md
├─ docs/
│  ├─ system_architecture.md
│  ├─ communication_protocol.md
│  ├─ control_state_machine.md
│  ├─ freertos_task_design.md
│  ├─ software_interface.md
│  ├─ hardware_wiring.md
│  ├─ test_log_summary.md
│  ├─ development_log.md
│  └─ troubleshooting.md
├─ firmware_esp32/
│  ├─ 01_motor_basic_test/
│  ├─ 02_servo_steering_test/
│  ├─ 03_drive_servo_integrated_test/
│  ├─ 04_pwm_sweep_test/
│  └─ 최종 ESP32 펌웨어
├─ laptop_controller/
│  └─ 인식·경로·안전·통신 상위 제어 코드
├─ integrated/
│  └─ 전체 시스템 통합 실행 코드
└─ assets/
   ├─ diagrams/
   ├─ photos/
   └─ demo_links/
```

`laptop_controller/`와 세부 하위 폴더는 실제 코드가 추가되는 시점에 생성한다.  
더 이상 사용하지 않는 Raspberry Pi 및 UART 수신 전용 구조는 제거한다.


---

## 15. 담당 역할

**임베디드 시스템 아키텍처 및 시스템 통합 설계**

- 노트북 상위 제어기와 ESP32 하위 제어기 역할 분리
- TCP 기반 차량 제어 통신 프로토콜 설계
- 차량 상태머신 및 fail-safe 구조 설계
- 명령 재전송·중복 방지·멱등성 처리 설계
- FreeRTOS Task·Queue 구조 설계
- 카메라 Pose·waypoint와 실제 RC카 제어 인터페이스 통합
- ESP32 펌웨어 구현 및 하드웨어 통합 테스트
- 전원·모터드라이버·서보·엔코더 배선과 문제 해결 기록

---

## 16. 시연 목표

최종 시연에서는 다음 흐름을 검증한다.

```text
차량 진입
→ 차량 및 빈 주차면 인식
→ 주차면 배정
→ 경로 생성
→ waypoint 기반 자율주행
→ 주행 중 장애물 또는 충돌 위험 발생
→ 즉시 정지
→ 경로 재생성
→ 주행 재개
→ 최종 주차 완료 및 슬롯 상태 갱신
```

다중 차량 시나리오에서는 선행 차량과 후속 차량의 슬롯 배정, 공용 구간 충돌 회피, 차량별 WAIT·GO 제어까지 포함한다.