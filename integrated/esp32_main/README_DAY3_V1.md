# Hanium DAY3 v1

이 패키지는 동결한 경량 아키텍처 문서를 기준으로 만든 첫 통합 DAY3 마일스톤이다.

## 구현 방식

통신, 상태머신, STOP/WAIT 안전 슬롯, 송신 Task는 인터페이스가 서로 연결되어 있으므로 하나의 통합 패키지로 제공한다. 대신 검증은 다음 순서로 끊어서 진행한다.

1. 복사 후 빌드
2. HELLO/HELLO_ACK 동기화
3. 상태 전이 시험
4. seq 중복·충돌 시험
5. heartbeat timeout 시험
6. 로컬 빌드 로그를 포함한 Claude 1회 코드 리뷰

## 이번 범위

- Wi-Fi STA
- Persistent TCP Client
- NDJSON 수신 버퍼
- cJSON 필드·범위 검증
- HELLO / HELLO_ACK
- WAYPOINT 저장
- WAYPOINT만으로는 출발하지 않음
- GO만 정상 MOVING 진입 허용
- WAIT / STOP / RESET
- STOP/WAIT 전용 안전명령 슬롯
- Task Notification은 wake-up 용도로만 사용
- STOP > WAIT
- VehicleControlTask가 상태와 액추에이터 결정 소유
- TransmitTask가 실제 socket send 소유
- heartbeat timeout
- 논리 payload 기준 seq 중복·충돌 처리
- STATUS의 last_processed_cmd_seq
- REMOTE_DIRECT + mock/실제 액추에이터 compile-time 전환 (`ENABLE_ACTUATOR_OUTPUT`)
- GPIO34/GPIO35 quadrature encoder raw count and STATUS reporting
- 2026-07-29 실측 8-bit PWM/조향 보정값 적용
- 노트북 독립 `remote-direct-bridge`와 연동 가능

## 이번에 제외

- 실제 POSE_UPDATE
- waypoint 추종 알고리즘
- ARRIVED/PARKED
- 동적 재경로
- 다중 차량
- PASS waypoint 버퍼링

`DAY3_ALLOW_GO_WITHOUT_POSE=1`은 아직 구현되지 않은 WAYPOINT_AUTO의 Pose gate 임시 예외다. REMOTE_DIRECT는 이 플래그를 사용하지 않는다. WAYPOINT_AUTO 실제 주행 전에는 반드시 제거해야 한다.

## 적용

프로젝트 경로:

```text
C:\Projects\2026-hanium-smart-parking\integrated\esp32_main
```

1. 모니터가 실행 중이면 `Ctrl + ]`로 종료
2. 기존 `main` 폴더 백업
3. 기존 `main/esp32_main.c` 삭제
4. ZIP의 `main` 파일 전체를 프로젝트 `main`에 복사
5. ZIP의 `tools`를 프로젝트 루트에 복사
6. `main/app_config.h`의 SSID, 비밀번호, 노트북 IPv4 수정

노트북 IPv4 확인:

```powershell
ipconfig
```

## 빌드

```powershell
cd C:\Projects\2026-hanium-smart-parking\integrated\esp32_main
idf.py fullclean
idf.py build
```

빌드가 성공하기 전에는 flash하지 않는다.

## REMOTE_DIRECT 브리지 실행

별도 `remote-direct-bridge` 폴더에서:

```powershell
python bridge.py
```

`tools/day3_tcp_server.py`는 기존 DAY3 WAYPOINT 통신 참고용이며 REMOTE_DIRECT 실차 제어에는 사용하지 않는다.
Windows 방화벽 창이 나오면 개인 네트워크를 허용한다.

## Flash

IDF PowerShell:

```powershell
idf.py -p COM6 flash monitor
```

정상 시작:

```text
BOOT → WIFI_CONNECTING → SYNCING → HELLO → HELLO_ACK → READY
```

## 상태 시험

```text
wp
```

예상:

```text
READY → WAITING
wait_reason=AWAITING_START
resume_allowed=true
```

```text
go
```

예상:

```text
WAITING → MOVING
```

일반 WAIT 재개:

```text
wait
go
```

중간 waypoint 완료 차단:

```text
reached
go
```

`resume_allowed=false`이므로 GO가 거절돼야 한다.

```text
next
go
```

새 waypoint를 받은 뒤 다시 MOVING으로 전환돼야 한다.

최종 waypoint 차단:

```text
final
go
wp
```

기존 target GO와 동일 route WAYPOINT가 모두 거절돼야 한다.

```text
newroute
go
```

새 route만 시작 가능해야 한다.

비상정지:

```text
stop
go
reset
```

- STOP → EMERGENCY_STOP
- GO 거절
- RESET → READY

## 신뢰성 시험

승인된 신뢰성 명령 직후:

```text
dup
```

- 명령 재실행 금지
- `duplicate=true`
- 이전 처리 결과 재전송

```text
conflict
```

- `SEQ_CONFLICT`
- 상태 변경 금지

## timeout 시험

```text
hb_off
```

약 1초 후:

```text
safeStop(COMM_TIMEOUT) → COMM_TIMEOUT → TCP 재접속
```

기존 경로는 자동 재개하지 않는다.

```text
hb_on
```

## 검증 상태

- Python 테스트 서버 문법 검사는 패키지 생성 시 수행함
- 이 환경에는 사용자의 Windows ESP-IDF v6.0.2 toolchain이 없으므로 C 코드는 아직 실제 `idf.py build`를 통과한 상태가 아님
- 다음 기준 증거는 사용자 PC의 `idf.py build` 전체 로그
- 실제 모터·서보 연결 없이 ESP32 USB 단독으로 먼저 시험


## Final PWM confirmation (2026-07-29)
- Motor PWM frequency: 20,000 Hz (20 kHz)
- Resolution: 8 bit
- Duty range: 0..255
- Calibrated values 15/23/40/50 are all based on this exact configuration.
