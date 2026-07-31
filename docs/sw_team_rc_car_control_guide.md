# SW팀용 RC카 제어 및 연동 인수인계 가이드

> 대상: RC카 하드웨어·ESP32 펌웨어·노트북 브리지 구조를 처음 접하는 SW팀원  
> 기준 브랜치: `integrate-v5.3.1`  
> 기준 펌웨어: `0.5.3-logic-hardening`  
> 최종 실차 검증일: 2026-07-31

---

## 1. 문서 목적

이 문서는 SW팀원이 다음 작업을 혼자 수행할 수 있도록 정리한 인수인계 문서다.

1. GitHub 저장소를 내려받는다.
2. 노트북과 ESP32를 같은 Wi-Fi에 연결한다.
3. ESP32 펌웨어를 빌드하고 업로드한다.
4. 노트북 브리지 GUI를 실행한다.
5. RC카를 WASD로 직접 제어한다.
6. 비상정지와 복구 절차를 수행한다.
7. 이후 카메라·경로 생성 SW와 ESP32 제어부를 연동한다.

현재 단계에서는 **수동 무선제어와 안전정지까지 실차 검증이 완료**되었다.  
카메라 Pose, 주차면 배정, 경로 생성, waypoint 자동주행의 전체 종단 간 연동은 아직 검증 전이다.

---

## 2. 시스템 구조

```text
노트북
├─ 카메라 인식
├─ 차량 위치 및 방향 계산
├─ 주차면 배정
├─ 경로 및 waypoint 생성
└─ TCP 서버
      ↓ Wi-Fi / TCP / NDJSON
ESP32
├─ TCP 클라이언트
├─ 차량 상태머신
├─ 모터 PWM·DIR 제어
├─ 서보 조향 제어
└─ 엔코더 상태 피드백
      ↓
RC카
```

현재 수동 실차 시험에는 `remote-direct-bridge`를 사용한다.

```text
키보드·GUI
    ↓
remote-direct-bridge
    ↓ Wi-Fi / TCP / NDJSON
ESP32
    ↓
MD10C + DC모터 / 서보모터 / 엔코더
```

최종 자율주행 단계에서는 키보드 입력 대신 카메라·경로 생성 SW가 `WAYPOINT`, `WAIT`, `GO`, `STOP` 명령을 생성한다.

---

## 3. 현재 구현 상태

### 3.1 실차 검증 완료

- ESP32 Wi-Fi 연결
- 노트북 TCP 서버 ↔ ESP32 TCP 클라이언트 지속 연결
- NDJSON 기반 메시지 송수신
- `HELLO` / `HELLO_ACK` 세션 동기화
- `STATUS` 상태 피드백
- `REMOTE_DIRECT` 모드 진입
- W/S 전진·후진
- A/D 누적 조향
- Shift+A/D 빠른 누적 조향
- 키 해제 시 모터 정지 및 조향 중앙 복귀
- 비상정지 `STOP`
- `RESET → REMOTE_DIRECT` 복구
- GUI 포커스 이탈 시 안전정지
- 브리지 종료 시 안전정지
- Wi-Fi·핫스팟 단절 시 안전정지
- 재연결 후 자동 재출발 방지
- ESP32 재부팅·EN 리셋 시 안전정지
- 엔코더 방향: 전진 양수 / 후진 음수
- 브리지 단위·통합 테스트 51개 통과
- ESP-IDF v6.0.2 빌드 성공
- 실차 연속 혼합주행 통과

### 3.2 코드 구조는 있으나 종단 간 실차 검증 전

- `WAYPOINT`
- `POSE_UPDATE`
- `WAIT` / `GO`
- waypoint 도착 판정
- 차량 상태머신
- 통신 timeout 및 오류 처리

ESP32 내부 구조는 존재하지만, **카메라·경로 생성 SW가 실제 값을 보내 RC카가 지정 waypoint까지 이동하는 종단 간 시험은 아직 완료하지 않았다.**

### 3.3 남은 작업

- 카메라 기반 차량 Pose 실시간 입력
- Homography 좌표와 실제 RC카 좌표계 일치 검증
- 주차면 배정 결과와 경로 생성 결과 연결
- waypoint 자동주행 실차 검증
- 엔코더 1회전당 count 및 cm 환산
- 직진 편차와 회전반경 측정
- 장애물 발생 시 WAIT·경로 재생성
- 다중 차량 순차·협력 제어
- RC카 2호기 제작 및 차량별 설정 분리

---

## 4. 주요 폴더

```text
2026-hanium-smart-parking/
├─ integrated/esp32_main/       # ESP-IDF 기반 실제 ESP32 펌웨어
│  ├─ main/
│  │  ├─ app_config.example.h   # 공개용 설정 예시
│  │  ├─ actuator.c             # 모터·서보 실제 출력
│  │  ├─ encoder.c              # 엔코더 count
│  │  ├─ network_client.c       # 노트북 TCP 서버 연결
│  │  ├─ protocol.c             # NDJSON 파싱·생성
│  │  ├─ tx_manager.c           # STATUS 전송 큐
│  │  └─ vehicle_control.c      # 상태머신·명령 처리
│  └─ tools/day3_tcp_server.py  # 초기 TCP 시험 도구
│
├─ remote-direct-bridge/        # 실차 수동제어용 노트북 TCP 서버
│  ├─ bridge_gui.py             # 권장 실행 진입점
│  ├─ controller.py             # 세션·모드·STOP·RESET·제어 송신
│  ├─ server.py                 # TCP 서버
│  ├─ protocol.py               # 메시지 생성·검증
│  ├─ wasd_gui.py               # Tkinter 키 입력
│  ├─ wasd_logic.py             # WASD → normalized control 변환
│  ├─ tools/mock_esp32.py       # ESP32 없이 통신 시험
│  └─ tests/                    # 51개 자동 테스트
│
└─ docs/
   ├─ remote_direct_test_2026-07-31.md
   ├─ communication_protocol.md
   ├─ control_state_machine.md
   └─ software_interface.md
```

---

## 5. 하드웨어 기준값

### 5.1 ESP32 핀

| 기능 | GPIO |
|---|---:|
| 모터 PWM | 25 |
| 모터 DIR | 26 |
| 서보 PWM | 27 |
| 엔코더 A | 34 |
| 엔코더 B | 35 |

### 5.2 모터·조향 보정값

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
- 전진 DIR: GPIO26 HIGH
- 후진 DIR: GPIO26 LOW
- 엔코더 방향 보정: `-1`
- 약 22° / 130°는 기계 한계 확인용이며 실제 운용값이 아니다.

---

## 6. 처음 설치하는 방법

### 6.1 저장소 내려받기

```powershell
git clone https://github.com/rjsdl5389/2026-hanium-smart-parking.git
cd 2026-hanium-smart-parking
git switch integrate-v5.3.1
```

`integrate-v5.3.1`이 `main`에 병합된 이후에는 `main`을 사용하면 된다.

### 6.2 ESP32 로컬 설정 파일 만들기

저장소에는 실제 Wi-Fi 비밀번호와 노트북 IP가 포함되지 않는다.

```powershell
cd integrated\esp32_main\main
Copy-Item app_config.example.h app_config.h
```

`app_config.h`에서 다음 항목을 수정한다.

```c
#define WIFI_SSID "실제 Wi-Fi 또는 핫스팟 이름"
#define WIFI_PASSWORD "실제 비밀번호"
#define SERVER_IPV4 "노트북의 같은 네트워크 IPv4 주소"
#define SERVER_PORT 5000
```

실차 출력은 반드시 바퀴를 띄운 상태에서 처음 활성화한다.

```c
#define ENABLE_ACTUATOR_OUTPUT 1
```

- `0`: GPIO 출력 없이 계산값만 로그로 확인
- `1`: 실제 모터와 서보 출력

`app_config.h`는 `.gitignore` 대상이므로 실제 비밀번호가 GitHub에 올라가지 않는다.

### 6.3 노트북 IP 확인

```powershell
ipconfig
```

ESP32와 노트북이 연결된 Wi-Fi 어댑터의 IPv4 주소를 `SERVER_IPV4`에 입력한다.

### 6.4 ESP32 펌웨어 빌드

ESP-IDF v6.0.2 PowerShell에서 실행한다.

```powershell
cd C:\경로\2026-hanium-smart-parking\integrated\esp32_main
idf.py build
```

정상 결과:

```text
Project build complete
```

### 6.5 ESP32 업로드 및 모니터

```powershell
idf.py -p COM6 flash monitor
```

COM 포트는 장치관리자에서 확인한다.

정상 부팅 로그:

```text
Firmware version: 0.5.3-logic-hardening
ENABLE_ACTUATOR_OUTPUT=1
Quadrature encoder initialized
```

Watchdog 또는 반복 재부팅 로그가 없어야 한다.

모니터 종료:

```text
Ctrl + ]
```

---

## 7. 브리지 GUI로 RC카 제어하기

### 7.1 실행

일반 PowerShell에서:

```powershell
cd C:\경로\2026-hanium-smart-parking\remote-direct-bridge
python bridge_gui.py
```

Python 표준 라이브러리만 사용한다.  
Windows 방화벽에서 Python의 사설 네트워크 통신을 허용한다. 기본 포트는 `5000`이다.

### 7.2 정상 연결 순서

1. 노트북과 ESP32를 같은 Wi-Fi에 연결한다.
2. 브리지 GUI를 실행한다.
3. ESP32 전원을 켜거나 EN 버튼을 누른다.
4. 브리지 로그에서 `HELLO`와 `HELLO_ACK`를 확인한다.
5. GUI의 `REMOTE_DIRECT` 버튼 또는 M 키를 한 번 누른다.
6. 다음 승인 로그를 확인한다.

```text
REMOTE_DIRECT acknowledged; DIRECT_CONTROL streaming enabled.
```

7. 승인 후에만 WASD 주행을 시작한다.

### 7.3 조작법

| 키 | 동작 |
|---|---|
| W 홀드 | 전진 |
| S 홀드 | 후진 |
| A 홀드 | 조향값을 좌측으로 단계 증가 |
| D 홀드 | 조향값을 우측으로 단계 증가 |
| Shift+A/D | 조향 변화속도 증가 |
| A/D 해제 | 즉시 중앙 복귀 |
| 모든 주행키 해제 | 모터 정지 + 중앙 조향 |
| M | REMOTE_DIRECT 요청 |
| Space | 비상정지 STOP |
| R | RESET 요청 |
| Q | 안전정지 후 GUI 종료 |

- W+S 동시 입력: 정지
- A+D 동시 입력: 중앙 조향
- GUI가 포커스를 잃으면 정지

### 7.4 비상정지 후 복구

```text
STOP
→ EMERGENCY_STOP 확인
→ R 또는 RESET 버튼
→ READY / WAYPOINT_AUTO 확인
→ M 또는 REMOTE_DIRECT 버튼
→ 승인 로그 확인
→ W/S 재입력
```

중요:

```text
RESET 후 바로 W를 눌러도 움직이지 않는 것이 정상이다.
반드시 RESET → REMOTE_DIRECT 재승인 → 주행 순서를 지킨다.
```

---

## 8. 브리지 자동 테스트

```powershell
cd remote-direct-bridge
python -m unittest discover -v
```

정상 결과:

```text
Ran 51 tests
OK
```

시험 범위:

- 프로토콜 파싱·생성
- 세션과 명령 sequence
- `result=NONE` 오승인 방지
- 오래된 STATUS 처리
- STOP·RESET·모드 복구
- 연결 해제·재접속
- WASD 충돌 입력
- 조향 누적 및 중앙 복귀
- 실측 PWM·서보 매핑

---

## 9. SW팀이 먼저 해야 할 시험

### 단계 A: 실제 RC카 수동제어 확인

```text
브리지 GUI + 실제 ESP32 + 실제 RC카
```

확인 항목:

- 전진·후진
- 좌우 조향
- STOP·RESET
- 통신 단절 안전정지

이 단계가 실패하면 카메라·경로 코드와 합치지 않는다.

### 단계 B: mock ESP32 확인

터미널 1:

```powershell
python bridge_gui.py
```

터미널 2:

```powershell
python tools\mock_esp32.py
```

실제 차량 없이 세션·모드·STOP·재접속을 확인할 수 있다.

### 단계 C: 기존 브리지 모듈 재사용

최종 SW는 다음 모듈을 재사용하거나 동일한 계약을 지켜야 한다.

- `protocol.py`: 메시지 형식과 검증
- `session.py`: session·sequence·상태 snapshot
- `controller.py`: 신뢰성 명령, 모드, STOP·RESET
- `server.py`: TCP 연결과 NDJSON 수신

처음부터 새 통신 코드를 따로 만들면 현재 검증된 안전정책이 빠질 가능성이 크다. 우선 기존 브리지를 독립 모듈로 실행한 뒤, 카메라·경로 결과를 브리지 명령 입력으로 연결하는 방식이 안전하다.

---

## 10. SW 연동 시 지켜야 할 제어 계약

### 10.1 좌표와 명령

- 차량 전역 위치: Homography 변환 이후 cm 단위
- heading: 차량 중심에서 차량 전방 기준점으로 향하는 각도
- 전체 경로: 노트북이 보관
- ESP32 전송: 초기에는 waypoint 하나씩
- 실제 모터 PWM을 SW에서 직접 보내지 않는다.
- SW는 normalized control 또는 waypoint 목표를 전달한다.

### 10.2 상태 처리

- `STOP`은 모든 일반 명령보다 우선한다.
- `result=NONE`은 명령 승인 결과가 아니다.
- 해당 `seq`의 명시적인 `ACCEPTED`를 받아야 명령 완료다.
- 늦게 도착한 과거 STATUS가 최신 상태를 덮어쓰면 안 된다.
- 연결 해제, 새 session, ESP32 재부팅 후 자동 재출발시키면 안 된다.
- RESET은 비상정지·오류 복구용이며 READY 상태에서 반복 전송하지 않는다.

### 10.3 최종 자동주행 권장 흐름

```text
카메라 Pose 수신
→ 주차면 배정
→ route 및 waypoint 생성
→ ESP32 연결·세션 확인
→ WAYPOINT 전송
→ STATUS / ARRIVED 확인
→ 다음 WAYPOINT 전송
```

위험 상황:

```text
위험 감지
→ WAIT 또는 STOP
→ 실제 정지 STATUS 확인
→ 최신 Pose 기준 경로 재생성
→ 새 route_id 적용
→ 명시적 재개 명령
```

---

## 11. 자주 발생하는 문제

### ESP32가 Wi-Fi에 연결되지 않음

- SSID와 비밀번호 재확인
- 아이폰은 `다른 사람의 연결 허용`과 `호환성 최대화` 활성화
- 노트북도 같은 핫스팟에 연결
- 핫스팟 설정 화면을 연 상태에서 ESP32 EN 버튼 입력

### Wi-Fi는 연결됐지만 TCP 연결 실패

- `SERVER_IPV4`가 노트북의 현재 IPv4인지 확인
- 브리지 GUI가 실행 중인지 확인
- 포트 `5000` 확인
- Windows 방화벽의 Python 사설 네트워크 허용 확인

### REMOTE_DIRECT인데 W/S가 동작하지 않음

다음 승인 로그 확인:

```text
REMOTE_DIRECT acknowledged; DIRECT_CONTROL streaming enabled.
```

승인 전 비제로 주행명령은 의도적으로 차단된다.

실행 중인 Python 파일 확인:

```powershell
python -c "import controller; print(controller.__file__)"
```

경로가 현재 저장소의 `remote-direct-bridge`여야 한다.

### STOP 후 다시 움직이지 않음

정상 안전정책일 수 있다.

```text
R → READY 확인 → M → 승인 확인 → W/S
```

### 모터·서보가 전혀 움직이지 않음

`app_config.h` 확인:

```c
#define ENABLE_ACTUATOR_OUTPUT 1
```

그다음 전원, 공통 GND, 모터드라이버 입력전압, PWM·DIR 배선을 확인한다.

### ESP32에서 Watchdog 발생

펌웨어 버전과 `tx_manager.c`가 v5.3.1 기준인지 확인한다.

```text
Firmware version: 0.5.3-logic-hardening
```

---

## 12. 개발 경과 요약

### 2026-07-02

- MDD10A 고장 가능성 판단
- MD10C 1채널 모터드라이버로 변경
- BTS7960을 임시·비교 시험용으로 확보

### 2026-07-03

- Raspberry Pi를 시스템에서 제외
- 노트북 상위제어기 + ESP32 하위제어기 구조 확정
- Wi-Fi 통신 구조로 전환

### 2026-07-09

- 서보 중앙 86° 확인
- 기계 한계 약 22° / 130° 확인
- 실제 운용각은 기계 한계보다 좁게 사용하기로 결정

### 2026-07-27~29

- 공중에서는 정상이나 바닥에서 부하가 걸리면 정지하는 현상 분석
- 조향각·PWM 조합을 조정
- 직진·중간조향·최대조향 PWM 보정
- 좌우 대칭 조향각 확정

### 2026-07-31

- 노트북 브리지와 ESP32 실차 통합
- STATUS 순서 역전과 `result=NONE` 오판 문제 수정
- 중복 SET_MODE와 잘못된 RESET 요청 차단
- TransmitTask Watchdog 회귀 오류 수정
- 51개 테스트 전체 통과
- STOP·RESET·재연결·포커스 이탈·브리지 종료·핫스팟 단절 안전시험 통과

---

## 13. AI에게 저장소를 넘길 때 사용할 프롬프트

```text
이 저장소는 2026 한이음 지능형 주차 프로젝트다.

우선 다음 파일을 읽고 현재 구조를 파악해라.
1. README.md
2. docs/sw_team_rc_car_control_guide.md
3. docs/communication_protocol.md
4. docs/control_state_machine.md
5. docs/software_interface.md
6. remote-direct-bridge/controller.py
7. remote-direct-bridge/protocol.py
8. integrated/esp32_main/main/vehicle_control.c
9. integrated/esp32_main/main/app_config.example.h

현재 실차 검증 완료 범위는 REMOTE_DIRECT 수동 무선제어와 fail-safe다.
카메라 Pose → 경로 생성 → WAYPOINT → 실차 자동주행은 아직 종단 간 검증 전이다.

다음 원칙을 깨지 마라.
- STOP 최우선
- result=NONE을 명령 승인으로 처리하지 않음
- 해당 seq의 명시적 ACCEPTED만 승인
- 오래된 STATUS가 최신 상태를 덮어쓰지 않음
- 재접속·재부팅 후 자동 재출발 금지
- 실제 비밀번호와 IP가 든 app_config.h는 커밋 금지
- 실제 PWM은 ESP32에서 변환하고 상위 SW가 raw PWM을 직접 보내지 않음

변경 전에 현재 구현과 테스트를 요약하고, 수정 파일과 영향 범위를 먼저 제시해라.
```

---

## 14. 관련 문서

- [`remote_direct_test_2026-07-31.md`](remote_direct_test_2026-07-31.md)
- [`communication_protocol.md`](communication_protocol.md)
- [`control_state_machine.md`](control_state_machine.md)
- [`software_interface.md`](software_interface.md)
- [`../remote-direct-bridge/README.md`](../remote-direct-bridge/README.md)
- [`../integrated/esp32_main/main/app_config.example.h`](../integrated/esp32_main/main/app_config.example.h)
