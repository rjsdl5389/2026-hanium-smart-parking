# hanium_day3_v1 — REMOTE_DIRECT 추가 변경 내역

기존 `hanium_day3_v1`에 **REMOTE_DIRECT**(노트북 직접 조종) 기능을 추가했습니다.
기존 WAYPOINT_AUTO / HELLO / HELLO_ACK / HEARTBEAT / WAYPOINT / GO / WAIT / STOP /
RESET / seq 멱등·SEQ_CONFLICT / 안전 슬롯 / Task 구조는 삭제하지 않고 그대로 유지합니다.

> ⚠️ 이 환경에서는 ESP-IDF 툴체인이 없어 **실제 빌드/플래시를 수행하지 못했습니다.**
> 아래 코드는 정적 구현이며 `gcc -fsyntax-only -Wall -Wextra -Wformat=2`(ESP-IDF
> 헤더 스텁 기반) 문법·포맷 검사만 통과했습니다. 반드시 `idf.py build`로 직접
> 빌드·검증하세요.

## 변경/추가 파일

| 파일 | 변경 | 이유 |
|------|------|------|
| `CMakeLists.txt` (최상위) | **신규** | 원본에 최상위 프로젝트 CMake가 없어 `idf.py build` 단독 실행 불가 → 추가 |
| `sdkconfig.defaults` | **신규** | 프로젝트 보드의 16MB SPI flash 기본값 유지 |
| `main/app_config.h` | 수정 | REMOTE_DIRECT 타임아웃(500ms), 모터/서보 매핑 상수, 핀, 512B TX 상한 |
| `main/app_types.h` | 수정 | `SET_MODE`·`DIRECT_CONTROL` 메시지 타입, 메시지 구조체에 mode/control_seq/throttle/steering, STATUS 스냅샷에 REMOTE_DIRECT 필드 |
| `main/app_types.c` | 수정 | 타입 문자열에 `SET_MODE`·`DIRECT_CONTROL` |
| `main/protocol.c` | 수정 | `SET_MODE`(신뢰성)·`DIRECT_CONTROL` 파싱, mode 파서, fingerprint, NaN/Inf 거절 |
| `main/vehicle_control.c` | 수정 | DIRECT_CONTROL 최신값 슬롯, control_seq 최신성, 500ms 타임아웃, SET_MODE 핸들러, STATUS 확장, 각 safeStop 경로에서 direct 무효화 |
| `main/actuator.c` | **신규**(구 `actuator_mock.c` 대체) | throttle/steering→PWM/서보 매핑 + mock/실제 출력. `ENABLE_ACTUATOR_OUTPUT=1`에서 LEDC 실제 출력 |
| `main/actuator.h` | **신규**(구 `actuator_mock.h` 대체) | `actuator_apply_direct()`/`actuator_output_enabled()` 등 API |
| `main/actuator_mock.c/.h` | **삭제** | `actuator.c/.h`로 대체(이름 명확화). 기존 `#error` 가드 제거 |
| `main/tx_manager.c` | 수정 | STATUS 확장으로 TX 라인 버퍼를 `MAX_TX_LINE_LENGTH`로 확대 |
| `main/CMakeLists.txt` | 수정 | `actuator_mock.c`→`actuator.c`, `esp_driver_ledc esp_driver_gpio` 의존성 추가 |
| `main/app_main.c` | 수정 | actuator 초기화 후 encoder 초기화 |
| `main/encoder.c/.h` | **신규** | GPIO34/35 any-edge quadrature count, critical-section protected read/reset |

기존 `README_DAY3_V1.md`, `CLAUDE_CODE_REVIEW_PROMPT.md`, `tools/day3_tcp_server.py`는
변경하지 않았습니다. (노트북 측 REMOTE_DIRECT 제어는 별도 `remote-direct-bridge/`가 담당하며,
`tools/day3_tcp_server.py`는 원본 DAY3 참고용 서버로 이 기능에 사용하지 않습니다.)

## 반드시 수정해야 하는 설정값 (`main/app_config.h`)

```c
#define WIFI_SSID    "CHANGE_ME"     // ← 실제 Wi-Fi SSID
#define WIFI_PASSWORD "CHANGE_ME"    // ← 실제 Wi-Fi 비밀번호
#define SERVER_IPV4  "192.168.0.10"  // ← 브리지를 실행하는 노트북 IP
```

## 안전 관련 컴파일 설정 (`main/app_config.h`)

```c
#define ENABLE_ACTUATOR_OUTPUT 0
#define MOTOR_PWM_RES_BITS 8
#define MOTOR_ALLOW_REVERSE 0
#define MOTOR_FORWARD_DIR_LEVEL 1
#define DIRECT_CONTROL_TIMEOUT_MS 500

#define PWM_FORWARD_MIN 15
#define PWM_FORWARD_DEFAULT 23
#define PWM_TURN_MIN 35
#define PWM_TURN_DEFAULT 40
#define PWM_STRONG_TURN_DEFAULT 50

#define SERVO_LEFT_STRONG_DEG 30.0
#define SERVO_LEFT_WEAK_DEG 60.0
#define SERVO_CENTER_DEG 86.0
#define SERVO_RIGHT_WEAK_DEG 112.0
#define SERVO_RIGHT_STRONG_DEG 122.0
```

핀: 모터 PWM `GPIO25`, 모터 DIR `GPIO26`, 서보 PWM `GPIO27`, 엔코더 A/B `GPIO34/35`.
세부 실측값과 초기화 순서는 `HW_CALIBRATION_2026-07-29.md`를 참조하세요.

## 빌드 / 플래시 / 모니터 (ESP-IDF v6.0.2)

```bash
idf.py set-target esp32       # 최초 1회
idf.py fullclean
idf.py build
idf.py -p COM6 flash monitor  # 포트는 환경에 맞게
```

## REMOTE_DIRECT 동작 요약

- 부팅 시 모터 0, 서보 중앙, 주행 금지.
- HELLO/HELLO_ACK 완료 후 기본 mode는 기존과 동일하게 `WAYPOINT_AUTO`.
  REMOTE_DIRECT 제어 전에는 반드시 `SET_MODE(REMOTE_DIRECT)`가 필요.
- `SET_MODE`는 READY(정지)에서만 허용, MOVING/EMERGENCY_STOP/ERROR/COMM_TIMEOUT에서 거절.
- 유효한 `DIRECT_CONTROL`(mode=REMOTE_DIRECT, control_seq 최신, 세션 일치)만 적용.
  - throttle≠0 → MOVING(실제/mock 출력). GO/target 불필요.
  - throttle=0 → 모터 0, 조향 적용, 정지(READY 유지).
- `control_seq`는 DIRECT_CONTROL 전용 최신값 순번. 작거나 같으면 폐기.
  새 세션/`SET_MODE(REMOTE_DIRECT)` 시 0으로 초기화. `last_processed_cmd_seq`와 무관.
- 마지막 유효 DIRECT_CONTROL 이후 **500ms** 무입력 → `safeStop(DIRECT_CONTROL_TIMEOUT)`
  → WAITING, `wait_reason=DIRECT_CONTROL_TIMEOUT`, 최신값 무효화. 이후 더 큰 control_seq의
  새 DIRECT_CONTROL이 오면 다시 MOVING 가능(GO 불필요).
- `STOP` → EMERGENCY_STOP, direct 최신값 폐기. 복구는 RESET → SET_MODE → 새 DIRECT_CONTROL.
- HEARTBEAT/TCP 단절 → COMM_TIMEOUT, direct 폐기, 자동 재개 없음.
- 우선순위: STOP > WAIT > 일반 신뢰성 명령 > DIRECT_CONTROL (VehicleControlTask 루프 순서로 보장).
- `CommunicationTask`는 direct 최신값을 슬롯에 저장 후 Notify만; 출력·상태 최종 결정은
  `VehicleControlTask`가 단독 소유. 실제 TCP send는 `TransmitTask`.

## STATUS 확장 필드

REMOTE_DIRECT 무선 STATUS에는 기존 공통 필드 + `latest_control_seq`, `applied_throttle`, `applied_steering`을 포함합니다.
`motor_pwm`, `motor_direction`, `servo_angle_deg`, `direct_control_age_ms`, `actuator_output_enabled`은 512B 상한 유지를 위해 무선 STATUS에서 제외하고 ESP32 시리얼 로그로 확인합니다.

REMOTE_DIRECT STATUS는 아키텍처의 현재 512B 메시지 상한을 유지하도록 축약했습니다.
무선 STATUS에는 latest_control_seq/applied_throttle/applied_steering을 포함하고, 실제 PWM·서보각은 ESP32 시리얼 로그에서 확인합니다. 송수신 NDJSON 상한은 512B입니다.


## 검토 보완 사항

- 새 TCP 연결, READY_ALLOWED 재동기화, RESET 후 mode를 `WAYPOINT_AUTO`로 되돌려 반드시 다시 `SET_MODE(REMOTE_DIRECT)`를 요구합니다.
- 모터 PWM/DIR에는 펌웨어 초기화 후 내부 pull-down을 켭니다. 다만 리셋/부팅 초기 구간은 소프트웨어로 보장할 수 없으므로 모터드라이버 입력에는 **외부 pull-down 저항**을 사용하는 것이 설계 원칙입니다.
- `MOTOR_FORWARD_DIR_LEVEL` / `MOTOR_REVERSE_DIR_LEVEL`을 설정으로 분리했습니다. 공중 벤치 테스트에서 전진 방향이 반대면 두 값을 뒤집으세요.


16MB 플래시 설정은 `sdkconfig.defaults`에 넣었습니다. 기존 프로젝트의 `sdkconfig`가 이미 16MB로 설정되어 있다면 그대로 유지하면 됩니다. ESP-IDF v6.0.2에서는 `CONFIG_ESPTOOLPY_FLASHSIZE_16MB`가 공식 16MB 선택지입니다.


## v3: 2026-07-29 HW 인수인계 반영

- 8-bit PWM(0..255), 전진 DIR=HIGH 반영
- 실측 직진/약한 회전/강한 회전 PWM 프로파일 반영
- 30/60/86/112/122° 구간별 조향 매핑 반영
- servo 50 Hz, 500–2400 us, servo-first 초기화 + 500 ms 중앙 대기
- 조향 변경 시 모터 20 ms 정지 후 재적용
- GPIO34/GPIO35 quadrature encoder 모듈 추가
- REMOTE_DIRECT STATUS에 `encoder_count` 추가
- PPR/감속비 미확정이므로 RPM/속도/거리 계산은 보류


## Final PWM confirmation (2026-07-29)
- Motor PWM frequency: 20,000 Hz (20 kHz)
- Resolution: 8 bit
- Duty range: 0..255
- Calibrated values 15/23/40/50 are all based on this exact configuration.
