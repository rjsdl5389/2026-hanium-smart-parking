# remote-direct-bridge v5

노트북에서 ESP32 RC카(`CAR_01`)를 무선 직접 조종하는 독립 실행형 TCP 브리지입니다. Django, DB, Redis, REST, WebSocket을 수정하지 않습니다.

## 권장 실행: GUI + 터미널 로그

```powershell
python bridge_gui.py
```

- 터미널: TCP 연결, HELLO/STATUS, encoderCount, STOP/timeout 로그
- Tkinter 창: KeyPress/KeyRelease 기반 WASD 조작
- Python 표준 라이브러리만 사용

### WASD 조작

| 키 | 동작 |
|---|---|
| W 홀드 | 전진 |
| S 홀드 | 후진 |
| W+A / W+D | 전진 약한 좌/우회전 |
| S+A / S+D | 후진 약한 좌/우회전 |
| Shift+A/D | 강한 조향 |
| 키 해제 | 즉시 throttle 0, steering 0 |
| M | SET_MODE(REMOTE_DIRECT) |
| Space | STOP → EMERGENCY_STOP |
| R | RESET |
| Q | STOP 후 GUI 종료 |

W+S는 안전상 정지, A+D는 중앙 조향으로 처리합니다. 창 포커스가 사라져도 stale 입력을 남기지 않고 정지합니다.

## 기존 터미널/CLI 실행

```powershell
python bridge.py
```

기존 CLI는 세부값 입력과 timeout 시험용으로 유지합니다. Windows 콘솔은 정확한 key-up 및 동시 키 추적이 어려우므로 실제 주행 조작에는 `bridge_gui.py`를 사용하세요.

## mock ESP32 시험

터미널 1:

```powershell
python bridge_gui.py
```

터미널 2:

```powershell
python tools\mock_esp32.py
```

## 테스트

```powershell
python -m unittest discover -s tests -t .
```

현재 v5 기준 46개 테스트를 포함합니다. WASD 조합, 키 충돌 안전처리, 실측 PWM/서보 매핑, reverse 설정, 프로토콜·세션·STOP·재접속을 검증합니다.

## 주요 파일

```text
remote-direct-bridge/
├─ bridge_gui.py       # v5 권장 실행 진입점
├─ wasd_gui.py         # Tkinter KeyPress/KeyRelease 창
├─ wasd_logic.py       # 테스트 가능한 순수 WASD 매핑
├─ bridge.py           # 기존 터미널/CLI 진입점
├─ controller.py       # 세션·HEARTBEAT·DIRECT_CONTROL·신뢰성 명령
├─ server.py           # persistent TCP + NDJSON
├─ tools/mock_esp32.py
└─ tests/
```

## normalized control과 실제 출력

브리지는 raw PWM을 보내지 않습니다.

- W: `throttle=+1.0`
- S: `throttle=-1.0`
- A/D: `steering=-0.5/+0.5`
- Shift+A/D: `steering=-1.0/+1.0`

ESP32가 20kHz, 8bit 실측 프로파일로 변환합니다.

- 직진 최대 운용값: PWM 23, 86°
- 약한 회전: PWM 40, 60°/112°
- 강한 회전: PWM 50, 30°/122°
- 후진 DIR: GPIO26 LOW
