# 노트북–ESP32 Production 통신 프로토콜

기준일: **2026-09-07**
production control mode: **ESP32 REMOTE_DIRECT**

## 1. 역할

- 노트북: TCP server, session 발급, reliable mode negotiation, heartbeat, latest `DIRECT_CONTROL`
- ESP32: TCP client, session/message 검증, Motor/Servo 적용, STATUS, independent watchdog/safeStop

노트북의 Camera Pose와 waypoint는 HostController 내부 입력이다. production에서는 `POSE_UPDATE`나 `WAYPOINT`를 ESP32로 보내 제어하지 않는다.

## 2. Transport와 framing

| 항목 | 값 |
|---|---|
| Network | Wi-Fi |
| Transport | TCP persistent connection |
| Application framing | NDJSON: JSON object + `\n` |
| 최대 message | 512 bytes |
| Host port | 기본 5000 |
| Protocol version | 1 |

TCP의 `send()`/ `recv()` 경계는 JSON message 경계가 아니다. 양쪽은 partial frame과 여러 frame이 합쳐진 수신을 buffer에 누적하고 newline 단위로 파싱한다. 512-byte cap을 넘는 partial/message는 session을 폐기한다.

## 3. 식별자

| 필드 | 소유자 | 목적 |
|---|---|---|
| `car_id` | firmware config | `CAR_01` 형식의 물리 차량 ID |
| `boot_id` | ESP32 boot | TCP reconnect와 실제 reboot 구분 |
| `session_id` | Backend handshake | old socket/message 격리 |
| `seq` | reliable sender | RESET/SET_MODE 등 멱등 transaction |
| `control_seq` | Backend stream | DIRECT_CONTROL 최신값 선택 |
| `heartbeat_seq` | Backend stream | link heartbeat 관측 |
| `status_seq` | ESP32 stream | STATUS freshness |

`car_id`, `session_id`, `boot_id`가 현재 identity와 일치하지 않는 STATUS/COMMAND_RESULT는 liveness나 ACK를 갱신하지 않는다.

## 4. 연결과 mode 협상

### 4.1 HELLO

ESP32는 TCP 연결 뒤 actuator를 safeStop하고 `SYNCING`에서 HELLO를 보낸다. HELLO에는 최소한 protocol version, `car_id`, `boot_id`, firmware/state와 이전 session 문맥이 포함된다.

### 4.2 HELLO_ACK

Backend는 HELLO를 검증하고 새 `session_id`와 `command_seq_start`를 발급한다.

```json
{"version":1,"type":"HELLO_ACK","car_id":"CAR_01","boot_id":"...","session_id":"...","result":"READY_ALLOWED","command_seq_start":1}
```

동일 `car_id`의 새 연결이 승인되면 기존 socket/session은 폐기한다.

### 4.3 RESET → SET_MODE

REMOTE_DIRECT 진입은 reliable command로 수렴한다.

```text
current STATUS 확인
→ 필요 시 RESET(seq)
→ 같은 seq의 terminal COMMAND_RESULT
→ SET_MODE(seq, REMOTE_DIRECT)
→ 같은 seq의 ACCEPTED
→ direct stream enable
```

각 논리 transaction에는 outstanding command 하나만 둔다. timeout 재전송은 **같은 seq와 같은 payload**를 사용한다. delayed/duplicate ACK는 멱등하게 처리하며 다른 session의 ACK는 무시한다.

## 5. Production message

### 5.1 HEARTBEAT

Backend가 250 ms 주기로 보낸다.

```json
{"version":1,"type":"HEARTBEAT","car_id":"CAR_01","session_id":"...","heartbeat_seq":1024}
```

ESP32는 유효 heartbeat가 1,000 ms 동안 없으면 `COMM_TIMEOUT`과 `safeStop`을 수행한다.

### 5.2 DIRECT_CONTROL

```json
{"version":1,"type":"DIRECT_CONTROL","car_id":"CAR_01","session_id":"...","control_seq":203,"throttle":0.25,"steering":-0.40}
```

- `throttle`: normalized -1.0..1.0, 양수 전진/음수 후진
- `steering`: normalized -1.0..1.0, wire 기준 음수 LEFT/양수 RIGHT
- latest-value stream이며 개별 ACK를 기다리지 않는다.
- Backend는 기본 100 ms tick으로 계속 보낸다.
- ESP32는 current session의 증가하는 `control_seq`만 적용한다.
- 마지막 valid DIRECT_CONTROL 이후 500 ms가 지나면 motor zero + servo center다.

Host가 zero를 원할 때도 stream을 끄는 대신 `throttle=0, steering=0`을 명시적으로 보낸다.

### 5.3 STATUS / COMMAND_RESULT

STATUS는 state, mode, sequence, applied throttle/steering, PWM/direction, servo angle, encoder count, wait/error와 session identity를 보고한다. REMOTE_DIRECT STATUS는 512-byte cap 안의 compact schema를 사용한다.

RESET/SET_MODE의 성공 여부는 `COMMAND_RESULT` 또는 terminal command-result field로 확인한다. 단순 주기 STATUS나 `command_result=NONE`은 ACK가 아니다.

## 6. 메시지 분류

| 분류 | Production 사용 | 처리 |
|---|---|---|
| HELLO / HELLO_ACK | 사용 | connection/session handshake |
| RESET / SET_MODE | 사용 | reliable, seq/terminal result |
| HEARTBEAT | 사용 | latest stream, link watchdog |
| DIRECT_CONTROL | 사용 | latest stream, actuator command |
| STATUS / COMMAND_RESULT | 사용 | state와 reliable ACK |
| STOP | 안전/운영용 | reliable, 선점 가능 |
| WAYPOINT / WAIT / GO | legacy only | production AUTO_HOST가 송신하지 않음 |
| POSE_UPDATE | disabled | HostController 내부 Pose 사용 |
| ARRIVED / EVENT_ACK | 하위호환 | Host가 도착 판정, 수신 시 ACK만 가능 |

## 7. Zero latch

Backend `VehicleServer.hold_control(car_id)`은 해당 차량 stream을 zero로 latch한다. 다음 상황에서는 단순 latest value 변경만으로 non-zero가 복원되지 않는다.

- socket disconnect / Backend RX timeout
- session replacement
- communication recovery
- route switch/fresh-Pose boundary
- terminal PARKED/fault

상위 coordinator가 mode/session, fresh Pose와 새 route preflight를 완료한 뒤에만 `release_control()`을 호출한다.

## 8. Communication failure recovery

```text
RX gap 또는 socket loss
→ Backend COMM_FAIL edge
→ per-car zero latch
→ host mission/context hold
→ ESP32 heartbeat/direct deadman safeStop
→ old socket/session retire
→ reconnect + HELLO
→ new session identity
→ RESET exactly once per logical transaction
→ terminal ACK
→ SET_MODE REMOTE_DIRECT exactly once
→ terminal ACK
→ fresh Pose/heading
→ slot intent와 terminal state 확인
→ current Pose 기준 trajectory preflight
→ AUTO_PENDING
→ zero latch release
```

재접속 자체는 출발 권한이 아니다. route, controller error history와 마지막 Pose를 그대로 재사용하지 않는다.

## 9. Timeout과 우선순위

| 항목 | 현재 값 |
|---|---:|
| HEARTBEAT interval | 250 ms |
| Backend RX COMM timeout | 1,000 ms |
| Firmware heartbeat timeout | 1,000 ms |
| DIRECT_CONTROL interval | 100 ms |
| Firmware DIRECT_CONTROL timeout | 500 ms |
| STATUS interval | 200 ms |
| Default reliable response timeout | 300 ms |
| Max retransmit | 5 |

ESP32 control task는 STOP/WAIT/fault notification을 latest DIRECT_CONTROL보다 우선 처리한다. socket send가 오래 block돼 heartbeat까지 지연되지 않도록 Backend send timeout과 session retirement가 적용된다.

## 10. Legacy와 문서 표현

`REMOTE_DIRECT`는 개발 중간모드가 아니라 최종 production actuator mode다. `WAYPOINT_AUTO`는 parser/enum과 비교용 코드가 남아 있어도 production이 아니다. “ESP32가 waypoint를 추종한다”, “GO가 차량을 출발시킨다”, “Arduino firmware가 최종 구현이다”라고 쓰지 않는다.

## 11. Dashboard protocol과의 구분

Django Channels/Redis WebSocket은 사용자 화면용 telemetry broadcast다. 차량 TCP 5000 NDJSON과 별도이며, Redis나 dashboard 장애는 `DIRECT_CONTROL` heartbeat/safeStop에 영향을 주지 않는다.
