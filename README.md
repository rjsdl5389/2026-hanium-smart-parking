# 2026 한이음 자율주행 기반 지능형 주차 운영 시스템

> 고정 카메라 기반 전역 인식, 동적 주차면 배정, waypoint 경로 생성, ESP32 차량 제어를 결합한 축소형 스마트 주차 테스트베드

## 1. 프로젝트 개요

본 프로젝트는 대형 마트·상가 지하주차장과 같은 환경에서 발생하는 주차면 탐색 비효율과 차량 간 충돌 문제를 개선하기 위해, **인프라 기반 협력형 자율주행 주차 시스템**을 축소형 테스트베드로 구현하는 것을 목표로 한다.

고정 카메라가 주차장 전체를 관찰하고, 노트북 상위 제어기가 차량 위치·주차면 상태·충돌 위험을 판단한다. 이후 차량별 주차면과 이동 경로를 생성해 ESP32에 전달하며, ESP32는 실제 모터와 조향 서보를 제어한다.

현재는 **노트북–ESP32 Wi-Fi/TCP 연결, REMOTE_DIRECT 수동 무선제어, 비상정지·재연결·통신단절 fail-safe까지 실차 검증 완료** 상태다. 카메라 Pose → 경로 생성 → WAYPOINT → 자동주행의 전체 종단 간 연동은 다음 단계다.

---

## 2. 최종 시연 목표

```text
차량 진입
→ 차량 및 빈 주차면 인식
→ 주차면 배정
→ 경로 생성
→ waypoint 기반 자율주행
→ 장애물 또는 충돌 위험 감지
→ 즉시 정지
→ 현재 위치 기준 경로 재생성
→ 주행 재개
→ 최종 주차 완료 및 슬롯 상태 갱신
```

다중 차량 시나리오에서는 선행 차량과 후속 차량의 슬롯 배정, 공용 구간 충돌 회피, 차량별 WAIT·GO 제어까지 포함한다.

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
    ├─ 주차면 배정
    ├─ route·waypoint 생성
    ├─ 장애물·충돌 위험 판단
    ├─ 경로 재생성
    └─ 관제 대시보드
    ↓ Wi-Fi / TCP / NDJSON
ESP32 하위 제어기
    ├─ 차량 상태머신
    ├─ 모터·서보 제어
    ├─ 엔코더 처리
    ├─ waypoint 추종
    └─ STOP·통신단절 안전정지
    ↓
RC카 주행 및 주차
```

### 역할 분리

| 구분 | 주요 역할 |
|---|---|
| 노트북 상위 제어기 | 카메라 인식, 좌표 변환, 슬롯 관리, 주차면 배정, 전역 경로 생성, 충돌 판단, 경로 재생성 |
| ESP32 하위 제어기 | TCP 연결, 명령 검증, 상태머신, waypoint 추종, 모터·서보 제어, 엔코더 처리, 즉시 정지 |

---

## 4. 현재 구현 상태

### 4.1 실차 검증 완료

- ESP32 Wi-Fi 연결
- 노트북 TCP 서버 ↔ ESP32 TCP 클라이언트 지속 연결
- NDJSON 기반 메시지 송수신
- `HELLO` / `HELLO_ACK` 세션 동기화
- `STATUS` 상태 피드백
- `REMOTE_DIRECT` 모드 진입
- W/S 전진·후진
- A/D 누적 조향
- Shift+A/D 빠른 누적 조향
- 키 해제 시 모터 정지 및 중앙 조향
- `STOP` 비상정지
- `RESET → REMOTE_DIRECT` 복구
- GUI 포커스 이탈 시 안전정지
- 브리지 종료 시 안전정지
- Wi-Fi·핫스팟 단절 시 안전정지
- 재연결 후 자동 재출발 방지
- ESP32 재부팅·EN 리셋 시 안전정지
- 엔코더 방향: 전진 양수 / 후진 음수
- 브리지 자동 테스트 51개 통과
- ESP-IDF v6.0.2 빌드 성공
- 실차 연속 혼합주행 통과

### 4.2 코드 구조는 있으나 종단 간 실차 검증 전

- `POSE_UPDATE`
- `WAYPOINT`
- `WAIT` / `GO`
- waypoint 도착 판정
- 카메라 Pose 기반 자동주행
- route 재생성
- 다중 차량 제어

### 4.3 남은 핵심 과제

- 카메라 Pose 실시간 입력
- Homography 좌표와 실제 맵 좌표 일치 검증
- 주차면 배정 결과와 경로 생성 결과 연결
- waypoint 자동주행 실차 검증
- 엔코더 count/회전 및 cm 환산
- 직진 편차·정지거리·회전반경 측정
- 장애물 발생 시 WAIT·경로 재생성
- RC카 2호기 제작 및 차량별 설정 분리

---

## 5. 통신 구조

- 노트북: TCP 서버
- ESP32: TCP 클라이언트
- 메시지: JSON
- 메시지 경계: 줄바꿈 `\n`
- 전송 형식: NDJSON
- 기본 포트: `5000`

주요 메시지:

| 방향 | 메시지 | 역할 |
|---|---|---|
| ESP32 → 노트북 | `HELLO` | 차량·부팅 상태 보고 |
| 노트북 → ESP32 | `HELLO_ACK` | session 승인 |
| 노트북 → ESP32 | `SET_MODE` | 제어 모드 변경 |
| 노트북 → ESP32 | `DIRECT_CONTROL` | normalized throttle·steering 전달 |
| 노트북 → ESP32 | `POSE_UPDATE` | 현재 차량 Pose 전달 |
| 노트북 → ESP32 | `WAYPOINT` | 목표 좌표·방향·속도 전달 |
| 노트북 → ESP32 | `WAIT` | target 유지 상태로 정지 |
| 노트북 → ESP32 | `GO` | 명시적 주행 재개 |
| 노트북 → ESP32 | `STOP` | 주행 취소 및 비상정지 |
| 노트북 → ESP32 | `RESET` | 비상정지·오류 복구 |
| ESP32 → 노트북 | `STATUS` | 차량 상태와 명령 처리 결과 |
| ESP32 → 노트북 | `ARRIVED` | waypoint 도착 이벤트 |

상세 명세: [`docs/communication_protocol.md`](docs/communication_protocol.md)

---

## 6. 차량 상태와 안전 원칙

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

안전 원칙:

- 부팅 직후 모터 출력 비활성화
- 상태 동기화 전 주행 금지
- STOP 최우선 처리
- `result=NONE`을 명령 승인으로 처리하지 않음
- 해당 `seq`의 명시적인 `ACCEPTED`만 승인
- 오래된 STATUS가 최신 상태를 덮어쓰지 않음
- 재접속·세션 변경·ESP32 재부팅 후 자동 재출발 금지
- RESET 후 자동으로 REMOTE_DIRECT에 진입하지 않음
- 통신 또는 GUI 입력이 끊기면 안전정지

상세 상태 전이: [`docs/control_state_machine.md`](docs/control_state_machine.md)

---

## 7. 하드웨어 구성

| 구분 | 구성 요소 | 역할 |
|---|---|---|
| 차량 제어기 | ESP32 | 통신, 상태머신, 모터·서보 제어 |
| 모터드라이버 | Cytron MD10C | DC모터 PWM·방향 제어 |
| 임시 테스트 드라이버 | BTS7960 | 비교·예비 시험 |
| 구동부 | DC 기어드모터 | 후륜 구동 |
| 조향부 | 서보모터 | 전륜 조향 |
| 피드백 | 모터 엔코더 | 속도·거리 측정 |
| 전원 | 3S 배터리팩, 퓨즈, 스위치, 전원분배 | 차량 전원 공급 및 보호 |
| 전압 변환 | DC-DC 컨버터 | ESP32·서보 전압 공급 |
| 외부 인식 | 고정 카메라 | 차량·주차면·장애물 관측 |

### ESP32 핀

| 기능 | GPIO |
|---|---:|
| 모터 PWM | 25 |
| 모터 DIR | 26 |
| 서보 PWM | 27 |
| 엔코더 A | 34 |
| 엔코더 B | 35 |

### 실차 보정값

| 구분 | 값 |
|---|---:|
| 직진 PWM | 27 |
| 중간 조향 PWM | 45 |
| 최대 조향 PWM | 55 |
| 좌 최대 | 50° |
| 좌 중간 | 68° |
| 중앙 | 86° |
| 우 중간 | 104° |
| 우 최대 | 122° |

- 모터 PWM: 20 kHz, 8-bit
- 전진 DIR: HIGH
- 후진 DIR: LOW
- 엔코더 방향 보정: `-1`
- 22° / 130°는 기계 한계 확인값이며 운용값이 아니다.

---

## 8. 저장소 구조

```text
2026-hanium-smart-parking/
├─ README.md
├─ docs/
│  ├─ sw_team_rc_car_control_guide.md
│  ├─ remote_direct_test_2026-07-31.md
│  ├─ communication_protocol.md
│  ├─ control_state_machine.md
│  ├─ software_interface.md
│  ├─ system_architecture.md
│  ├─ freertos_task_design.md
│  ├─ hardware_wiring.md
│  ├─ test_log_summary.md
│  ├─ development_log.md
│  └─ troubleshooting.md
├─ integrated/
│  └─ esp32_main/
│     ├─ main/
│     │  ├─ app_config.example.h
│     │  ├─ actuator.c
│     │  ├─ encoder.c
│     │  ├─ network_client.c
│     │  ├─ protocol.c
│     │  ├─ tx_manager.c
│     │  └─ vehicle_control.c
│     └─ tools/
├─ remote-direct-bridge/
│  ├─ bridge_gui.py
│  ├─ controller.py
│  ├─ protocol.py
│  ├─ server.py
│  ├─ session.py
│  ├─ wasd_gui.py
│  ├─ wasd_logic.py
│  ├─ tests/
│  └─ tools/mock_esp32.py
├─ firmware_esp32/
└─ assets/
```

---

## 9. 빠른 시작

### 9.1 SW팀 인수인계 문서

처음 RC카를 제어하는 팀원은 다음 문서를 먼저 읽는다.

- [`docs/sw_team_rc_car_control_guide.md`](docs/sw_team_rc_car_control_guide.md)

### 9.2 브리지 테스트

```powershell
cd remote-direct-bridge
python -m unittest discover -v
```

정상 결과:

```text
Ran 51 tests
OK
```

### 9.3 GUI 실행

```powershell
cd remote-direct-bridge
python bridge_gui.py
```

### 9.4 ESP32 설정

```powershell
cd integrated\esp32_main\main
Copy-Item app_config.example.h app_config.h
```

`app_config.h`에서 Wi-Fi SSID, 비밀번호, 노트북 IPv4를 설정하고 실제 출력 시험 시:

```c
#define ENABLE_ACTUATOR_OUTPUT 1
```

실제 `app_config.h`는 Git 추적 대상에서 제외된다.

---

## 10. 주요 문서

| 문서 | 내용 |
|---|---|
| [`docs/sw_team_rc_car_control_guide.md`](docs/sw_team_rc_car_control_guide.md) | SW팀용 설치·실행·제어·연동 인수인계 |
| [`docs/remote_direct_test_2026-07-31.md`](docs/remote_direct_test_2026-07-31.md) | REMOTE_DIRECT 실차 검증 결과 |
| [`docs/system_architecture.md`](docs/system_architecture.md) | 전체 시스템 구조 |
| [`docs/communication_protocol.md`](docs/communication_protocol.md) | TCP·NDJSON 메시지 및 신뢰성 정책 |
| [`docs/control_state_machine.md`](docs/control_state_machine.md) | 차량 상태와 명령 허용 조건 |
| [`docs/freertos_task_design.md`](docs/freertos_task_design.md) | ESP32 Task·Queue 구조 |
| [`docs/software_interface.md`](docs/software_interface.md) | Pose·slot·route·waypoint 인터페이스 |
| [`docs/hardware_wiring.md`](docs/hardware_wiring.md) | 전원·MD10C·서보·엔코더 배선 |
| [`docs/test_log_summary.md`](docs/test_log_summary.md) | 시험 항목과 측정값 |
| [`docs/development_log.md`](docs/development_log.md) | 날짜별 개발 기록 |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | 문제 해결 절차 |

---

## 11. 현재 개발 브랜치

REMOTE_DIRECT 통합본은 다음 브랜치에 있다.

```text
integrate-v5.3.1
```

해당 브랜치 검증이 끝난 뒤 `main`에 병합한다.
