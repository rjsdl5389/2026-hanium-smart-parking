# remote-direct-bridge v5.3.1

노트북에서 ESP32 RC카(`CAR_01`)를 무선 직접 조종하는 독립 실행형 TCP 브리지다.

- Django·Redis·DB·REST·WebSocket 수정 없이 단독 실행
- 노트북 TCP 서버
- ESP32 TCP 클라이언트
- persistent TCP + NDJSON
- REMOTE_DIRECT 수동제어
- STOP·RESET·재연결 fail-safe
- 브리지 자동 테스트 51개 통과

---

## 1. 권장 실행

```powershell
python bridge_gui.py
```

- 터미널: TCP 연결, HELLO, STATUS, encoder, STOP, timeout 로그
- GUI: Tkinter KeyPress/KeyRelease 기반 WASD 조작
- Python 표준 라이브러리만 사용

---

## 2. 연결 순서

1. 노트북과 ESP32를 같은 Wi-Fi에 연결한다.
2. ESP32의 `app_config.h`에 노트북 IPv4를 입력한다.
3. 브리지 GUI를 실행한다.
4. ESP32 전원을 켜거나 EN 버튼을 누른다.
5. `HELLO` / `HELLO_ACK`를 확인한다.
6. M 키 또는 REMOTE_DIRECT 버튼을 한 번 누른다.
7. 다음 로그를 확인한다.

```text
REMOTE_DIRECT acknowledged; DIRECT_CONTROL streaming enabled.
```

8. 승인 후 WASD로 조작한다.

---

## 3. WASD 조작

| 키 | 동작 |
|---|---|
| W 홀드 | 전진 |
| S 홀드 | 후진 |
| A 홀드 | 좌측 조향값 누적 |
| D 홀드 | 우측 조향값 누적 |
| Shift+A/D | 조향 변화속도 증가 |
| A/D 해제 | 즉시 중앙 조향 |
| 모든 주행키 해제 | 모터 정지 + 중앙 조향 |
| M | `SET_MODE(REMOTE_DIRECT)` |
| Space | `STOP → EMERGENCY_STOP` |
| R | `RESET` |
| Q | STOP 후 GUI 종료 |

안전 입력 처리:

- W+S: 정지
- A+D: 중앙 조향
- GUI 포커스 이탈: 정지
- REMOTE_DIRECT 승인 전 비제로 주행명령 차단

---

## 4. 비상정지 복구

```text
Space 또는 STOP 버튼
→ EMERGENCY_STOP
→ R 또는 RESET 버튼
→ READY / WAYPOINT_AUTO 확인
→ M 또는 REMOTE_DIRECT 버튼
→ 명시적 ACCEPTED 확인
→ W/S 재입력
```

RESET 후 바로 W를 눌러도 움직이지 않는 것이 정상이다. 재출발에는 REMOTE_DIRECT 재승인이 필요하다.

---

## 5. normalized control과 실제 출력

브리지는 raw PWM을 보내지 않는다.

```text
W → throttle=+1.0
S → throttle=-1.0
A/D → steering 누적 변화
키 해제 → throttle=0.0, steering=0.0
```

ESP32가 normalized 값과 조향 크기를 실측 프로파일로 변환한다.

### 현재 실차 보정값

| 상태 | 모터 PWM | 서보 |
|---|---:|---:|
| 직진 | 27 | 86° |
| 좌 중간 | 45 | 68° |
| 우 중간 | 45 | 104° |
| 좌 최대 | 55 | 50° |
| 우 최대 | 55 | 122° |

- 모터 PWM: 20 kHz, 8-bit
- 전진 DIR: GPIO26 HIGH
- 후진 DIR: GPIO26 LOW
- 서보 PWM: GPIO27, 50 Hz
- 기계 한계 22° / 130°는 실제 운용에 사용하지 않는다.

---

## 6. 테스트

```powershell
python -m unittest discover -v
```

정상 결과:

```text
Ran 51 tests
OK
```

검증 범위:

- 프로토콜 파싱·생성
- 세션과 sequence
- `result=NONE` 오승인 방지
- 해당 seq의 명시적 `ACCEPTED` 처리
- 오래된 STATUS가 최신 snapshot을 덮어쓰지 않도록 처리
- STOP·RESET·REMOTE_DIRECT 복구
- 중복 모드 요청 차단
- 연결 해제·재접속
- WASD 충돌 입력
- 조향 누적과 중앙 복귀
- 실측 PWM·서보 매핑

---

## 7. mock ESP32 시험

터미널 1:

```powershell
python bridge_gui.py
```

터미널 2:

```powershell
python tools\mock_esp32.py
```

실제 차량 없이 세션, 모드 전환, STOP, RESET, 재접속을 확인할 수 있다.

---

## 8. 주요 파일

```text
remote-direct-bridge/
├─ bridge_gui.py       # 권장 실행 진입점
├─ wasd_gui.py         # Tkinter KeyPress/KeyRelease
├─ wasd_logic.py       # WASD → normalized control
├─ bridge.py           # CLI 진입점
├─ controller.py       # 세션·HEARTBEAT·STOP·RESET·DIRECT_CONTROL
├─ server.py           # persistent TCP + NDJSON
├─ protocol.py         # 메시지 생성·검증
├─ session.py          # session·sequence·snapshot
├─ tools/mock_esp32.py
└─ tests/
```

---

## 9. 핵심 안전정책

- STOP 최우선
- `result=NONE`은 명령 승인 아님
- 해당 명령 seq의 명시적 `ACCEPTED`만 승인
- 오래된 STATUS가 최신 상태를 덮어쓰지 않음
- 연결 해제 시 입력값 초기화
- 재접속 후 자동 재출발 금지
- REMOTE_DIRECT 승인 전 주행 차단
- READY 상태에서 불필요한 RESET 차단

---

## 10. 관련 문서

- [`../docs/sw_team_rc_car_control_guide.md`](../docs/sw_team_rc_car_control_guide.md)
- [`../docs/remote_direct_test_2026-07-31.md`](../docs/remote_direct_test_2026-07-31.md)
- [`../docs/communication_protocol.md`](../docs/communication_protocol.md)
- [`../integrated/esp32_main/main/app_config.example.h`](../integrated/esp32_main/main/app_config.example.h)
