# ESP32 차량 제어 상태머신 설계

## 1. 문서 목적

본 문서는 자율주행 기반 지능형 주차 운영 시스템에서 ESP32가 관리하는 차량 상태와 상태 전이 규칙을 정의한다.

상태머신의 목적은 다음과 같다.

- 차량의 모터·서보 출력을 하나의 일관된 기준으로 제어한다.
- WAYPOINT, WAIT, GO, STOP, RESET 명령의 허용 조건을 명확히 한다.
- 통신 단절, Pose 유실, 하드웨어 오류 발생 시 차량을 안전하게 정지한다.
- 명령 재전송 및 중복 수신 상황에서도 동일 명령을 반복 실행하지 않는다.
- 재접속 또는 ESP32 재부팅 이후 기존 주행을 자동 재개하지 않는다.
- 차량의 물리 상태와 주차 경로의 진행 단계를 분리해 관리한다.

상태머신의 최종 소유자는 `VehicleControlTask`이다.

다른 Task는 차량 상태나 모터 출력을 직접 변경하지 않고, 이벤트·명령·센서 정보를 `VehicleControlTask`에 전달한다.

---

## 2. 상태와 경로 단계 분리

차량의 물리 동작 상태와 주차 경로의 진행 단계는 서로 다른 값으로 관리한다.

### 2.1 차량 상태

- `BOOT`
- `WIFI_CONNECTING`
- `SYNCING`
- `READY`
- `MOVING`
- `WAITING`
- `EMERGENCY_STOP`
- `COMM_TIMEOUT`
- `ERROR`

### 2.2 경로 단계

- `NONE`
- `CRUISE`
- `APPROACH`
- `ALIGN`
- `ENTRY`
- `FINAL`
- `PARKED`

예시:

```text
state = WAITING
phase = ALIGN
```

위 상태는 차량이 정렬 단계의 waypoint를 수행하던 중 일시정지한 상황을 의미한다.

WAIT 이후 GO를 받아도 `phase`는 `ALIGN`으로 유지한다.

---

## 3. 상태별 정의

## 3.1 BOOT

ESP32가 부팅된 직후의 상태이다.

필수 동작:

- 모터 출력 비활성화
- 서보 출력 안전값 적용
- `boot_id` 생성
- 상태·Queue·타이머 초기화
- 현재 target 및 waypoint buffer 비우기
- 자동 주행 금지

전이:

```text
BOOT
→ 초기화 성공
→ WIFI_CONNECTING
```

초기화 실패 시:

```text
BOOT
→ 초기화 실패
→ ERROR
```

---

## 3.2 WIFI_CONNECTING

ESP32가 설정된 Wi-Fi 네트워크 및 노트북 TCP 서버에 연결을 시도하는 상태이다.

필수 동작:

- 모터 정지 유지
- 주행 명령 실행 금지
- Wi-Fi 및 TCP 재연결 시도
- 연결 성공 전 target 로드 금지

전이:

```text
WIFI_CONNECTING
→ TCP 연결 성공
→ SYNCING
```

연결 실패가 계속되더라도 차량은 정지 상태를 유지한다.

---

## 3.3 SYNCING

TCP 연결 이후 노트북과 차량 상태를 동기화하는 상태이다.

필수 동작:

- `HELLO` 전송
- `HELLO_ACK` 대기
- 차량 ID, 프로토콜 버전, `boot_id`, 오류 상태 확인
- pending ARRIVED 및 최근 완료 waypoint 정보 보고
- 기존 target과 buffer를 이용한 자동 주행 금지

전이:

```text
SYNCING
→ HELLO_ACK result = READY_ALLOWED
→ target 및 buffer 정리
→ READY
```

```text
SYNCING
→ HELLO_ACK result = HOLD
→ SYNCING 유지
```

```text
SYNCING
→ HELLO_ACK result = REJECTED
→ 연결 종료 또는 ERROR
```

동기화 도중 통신이 끊기면:

```text
SYNCING
→ TCP 연결 종료
→ WIFI_CONNECTING
```

---

## 3.4 READY

차량이 정상적으로 연결되고 정지해 있으며 새로운 명령을 받을 수 있는 상태이다.

조건:

- 통신 정상
- 동기화 완료
- 모터 정지
- 잠금 오류 없음
- 이전 주행 자동 재개 없음

허용 동작:

- `SET_MODE`
- `WAYPOINT`
- `POSE_UPDATE`
- `HEARTBEAT`
- `STOP`
- 필요한 경우 `WAIT`

기본 전이:

```text
READY + 유효 WAYPOINT
→ target 저장
→ MOVING
```

READY에서 WAIT를 받으면 이미 정지한 상태이므로 모터 정지를 다시 보장하고 READY를 유지한다.

```text
READY + WAIT
→ safeStop()
→ READY 유지
→ ack 전송
```

---

## 3.5 MOVING

현재 waypoint를 향해 차량을 제어하는 상태이다.

필수 동작:

- 최신 카메라 Pose 확인
- 엔코더 속도·거리 확인
- 위치 및 heading 오차 계산
- 모터 PWM 계산
- 서보 조향값 계산
- waypoint 도착 조건 확인
- 통신 timeout 및 Pose timeout 확인

정상 완료:

```text
MOVING
→ waypoint 도착 조건 만족
→ safeStop(ARRIVED)
→ last_completed 갱신
→ ARRIVED 이벤트 생성
→ READY
```

일시정지:

```text
MOVING + WAIT
→ target·route·waypoint·phase 유지
→ safeStop(WAIT)
→ WAITING
```

비상정지:

```text
MOVING + STOP
→ target 및 buffer 폐기
→ safeStop(STOP)
→ EMERGENCY_STOP
```

Pose 유실:

```text
MOVING + POSE_TIMEOUT
→ target·route·waypoint·phase 유지
→ safeStop(POSE_TIMEOUT)
→ WAITING
```

통신 단절:

```text
MOVING + COMM_TIMEOUT
→ target 및 buffer 폐기
→ safeStop(COMM_TIMEOUT)
→ COMM_TIMEOUT
```

하드웨어 오류:

```text
MOVING + 제어 불가능한 오류
→ target 및 buffer 폐기
→ safeStop(ERROR)
→ ERROR
```

1차 구현에서는 MOVING 중 새로운 WAYPOINT를 수신하면 거절한다.

```text
MOVING + 새로운 WAYPOINT
→ COMMAND_RESULT: REJECTED
→ reason = INVALID_STATE
→ MOVING 유지
```

동일 `seq`와 동일 payload의 WAYPOINT 재전송은 중복 실행하지 않고 이전 처리 결과만 다시 응답한다.

---

## 3.6 WAITING

현재 주행 맥락을 유지한 채 일시정지한 상태이다.

WAITING에서 유지되는 정보:

- `target_loaded`
- `route_id`
- `waypoint_id`
- `phase`
- 현재 waypoint 내용
- `wait_reason`

대표 진입 원인:

- `REMOTE_WAIT`
- `COLLISION_RISK`
- `OBSTACLE`
- `REROUTING`
- `POSE_TIMEOUT`
- `POSE_INVALID`
- `CONTROL_UNCERTAIN`

새로운 경로를 적용하는 경우:

```text
WAITING + 새 WAYPOINT
→ 새 target 저장
→ 새 route_id 및 waypoint_id 저장
→ WAITING 유지
→ GO 대기
```

GO 실행 조건:

- 현재 상태가 WAITING
- target이 로드됨
- `session_id` 일치
- `route_id` 일치
- `waypoint_id` 일치
- 최신 Pose 유효
- Pose timeout 아님
- 로컬 안전 오류 없음
- EMERGENCY_STOP 아님
- ERROR 아님
- COMM_TIMEOUT 아님

조건을 모두 만족하면:

```text
WAITING + GO
→ MOVING
```

조건이 부족하면:

```text
WAITING + GO
→ COMMAND_RESULT: REJECTED
→ WAITING 유지
```

Pose가 다시 정상화되어도 자동 출발하지 않는다.

```text
POSE_TIMEOUT 해소
→ WAITING 유지
→ 노트북의 GO 대기
```

STOP 수신 시:

```text
WAITING + STOP
→ target 및 buffer 폐기
→ safeStop(STOP)
→ EMERGENCY_STOP
```

---

## 3.7 EMERGENCY_STOP

STOP 명령 또는 이에 준하는 비상조건으로 인해 잠금된 정지 상태이다.

필수 동작:

- 가장 강한 검증된 안전정지 적용
- target 폐기
- waypoint buffer 폐기
- 자동 출발 금지
- GO 거절
- 새로운 WAYPOINT 거절
- 상태를 주기 STATUS에 반복 보고

허용 명령:

- `HEARTBEAT`
- `POSE_UPDATE`
- `STOP`
- 조건을 만족한 `RESET`
- 연결 동기화 메시지

복구:

```text
EMERGENCY_STOP
→ 비상 원인 제거 확인
→ RESET
→ READY
```

RESET 이후에도 기존 주행을 재개하지 않는다.

```text
READY
→ 현재 Pose 재확인
→ 새 route 생성
→ 새 WAYPOINT
```

---

## 3.8 COMM_TIMEOUT

노트북과의 유효 통신이 설정 시간 이상 끊긴 상태이다.

진입 조건 예시:

- 유효 HEARTBEAT 미수신
- TCP 연결 종료
- 유효한 현재 session 메시지 미수신

진입 처리:

```text
통신 timeout 감지
→ target 및 buffer 폐기
→ safeStop(COMM_TIMEOUT)
→ COMM_TIMEOUT
```

COMM_TIMEOUT에서는 GO를 허용하지 않는다.

복구:

```text
COMM_TIMEOUT
→ TCP 재연결
→ SYNCING
→ HELLO/HELLO_ACK
→ READY
→ 새 route 및 WAYPOINT
```

재연결은 통신 복구일 뿐 기존 주행 복구가 아니다.

---

## 3.9 ERROR

차량을 안전하게 제어할 수 없는 하드웨어 또는 소프트웨어 오류 상태이다.

예시:

- 엔코더 입력 비정상
- 모터 출력 명령 대비 무응답
- 서보 제어 이상
- 내부 상태 불일치
- Queue 또는 메모리 오류
- VehicleControlTask 이상
- 유효하지 않은 제어 파라미터

진입 처리:

```text
오류 감지
→ target 및 buffer 폐기
→ safeStop(ERROR)
→ ERROR
```

ERROR에서는 GO와 WAYPOINT를 거절한다.

복구:

```text
오류 원인 제거
→ RESET 조건 확인
→ RESET
→ READY
```

복구할 수 없는 오류는 재부팅 또는 운영자 점검을 요구한다.

---

## 4. 상태 우선순위

여러 이벤트가 동시에 발생할 경우 다음 우선순위를 적용한다.

```text
ERROR 또는 하드웨어 안전 오류
> STOP
> COMM_TIMEOUT
> WAIT 또는 POSE_TIMEOUT
> 일반 제어 명령
> 진단 및 로그 요청
```

단, 이미 `EMERGENCY_STOP` 또는 `ERROR`에 진입한 상태에서 통신이 끊기더라도 기존 잠금 상태를 해제하지 않는다.

예시:

```text
state = EMERGENCY_STOP
통신 단절 발생
→ 모터 정지 유지
→ EMERGENCY_STOP 유지
→ link 상태만 DOWN으로 기록
```

```text
state = ERROR
통신 단절 발생
→ ERROR 유지
→ link 상태만 DOWN으로 기록
```

안전 잠금 상태가 통신 상태 변화로 덮어써져서는 안 된다.

---

## 5. 명령별 허용 상태표

| 명령 | 허용 상태 | 처리 결과 |
|---|---|---|
| `HELLO_ACK` | SYNCING | READY 또는 SYNCING 유지 |
| `SET_MODE` | READY | 제어 모드 변경 |
| `DIRECT_CONTROL` | READY 또는 MOVING, REMOTE_DIRECT 모드 | 최신 직접 제어값 적용 |
| `POSE_UPDATE` | 연결된 모든 상태 | 최신 Pose 갱신 |
| `WAYPOINT` | READY | target 저장 후 MOVING |
| `WAYPOINT` | WAITING | target 교체 후 WAITING 유지 |
| `WAYPOINT` | MOVING | 신규 명령 거절, 동일 seq 재전송은 결과 재응답 |
| `WAIT` | MOVING | WAITING 전환 |
| `WAIT` | WAITING | WAITING 유지 |
| `WAIT` | READY | 정지 보장 후 READY 유지 |
| `WAIT` | 잠금 상태 | 현재 안전 상태 유지 |
| `GO` | WAITING + 복구조건 충족 | MOVING 전환 |
| `GO` | 그 외 상태 | 거절 |
| `STOP` | 모든 상태 | EMERGENCY_STOP 전환 |
| `RESET` | EMERGENCY_STOP 또는 복구 가능한 ERROR | READY 전환 |
| `HEARTBEAT` | 연결된 모든 상태 | 링크 수신시각 갱신 |
| `EVENT_ACK` | 연결된 모든 상태 | pending event 제거 |

---

## 6. 주요 상태 전이표

| 현재 상태 | 이벤트 또는 명령 | 조건 | 다음 상태 | target 처리 |
|---|---|---|---|---|
| BOOT | 초기화 성공 | 필수 장치 초기화 완료 | WIFI_CONNECTING | 폐기 |
| BOOT | 초기화 실패 | 제어 불가 | ERROR | 폐기 |
| WIFI_CONNECTING | TCP 연결 성공 | 노트북 서버 연결 | SYNCING | 폐기 |
| SYNCING | READY_ALLOWED | 동기화 성공 | READY | 폐기 |
| SYNCING | HOLD | 추가 확인 필요 | SYNCING | 폐기 |
| READY | WAYPOINT | 유효 명령 | MOVING | 저장 |
| READY | WAIT | 항상 허용 | READY | 없음 |
| READY | STOP | 항상 허용 | EMERGENCY_STOP | 폐기 |
| MOVING | ARRIVED 조건 충족 | 위치·heading 허용오차 만족 | READY | 완료 후 폐기 |
| MOVING | WAIT | 안전 일시정지 | WAITING | 유지 |
| MOVING | POSE_TIMEOUT | 유효 Pose 없음 | WAITING | 유지 |
| MOVING | STOP | 비상정지 | EMERGENCY_STOP | 폐기 |
| MOVING | COMM_TIMEOUT | 링크 단절 | COMM_TIMEOUT | 폐기 |
| MOVING | 하드웨어 오류 | 제어 불가 | ERROR | 폐기 |
| WAITING | 새 WAYPOINT | 유효한 새 route | WAITING | 교체 |
| WAITING | GO | 모든 복구조건 충족 | MOVING | 유지 |
| WAITING | STOP | 항상 허용 | EMERGENCY_STOP | 폐기 |
| EMERGENCY_STOP | RESET | 원인 제거 및 조건 충족 | READY | 폐기 |
| ERROR | RESET | 복구 가능한 오류 해제 | READY | 폐기 |
| COMM_TIMEOUT | TCP 재연결 | 연결 성공 | SYNCING | 폐기 |

---

## 7. WAIT 원인별 복구 규칙

### 7.1 REMOTE_WAIT

```text
노트북이 일시정지를 요청
→ WAITING
→ 노트북이 재개 가능 확인
→ GO
→ MOVING
```

### 7.2 COLLISION_RISK 또는 OBSTACLE

```text
노트북 Safety Shield가 위험 감지
→ WAIT
→ WAITING
→ 위험 해소 또는 새 route 생성
→ 새 WAYPOINT 저장
→ GO
→ MOVING
```

### 7.3 REROUTING

```text
기존 route 폐기 결정
→ WAITING
→ 새로운 route_id 생성
→ 새 WAYPOINT 저장
→ GO
→ MOVING
```

### 7.4 POSE_TIMEOUT 또는 POSE_INVALID

```text
유효 Pose 유실
→ WAITING
→ 유효 Pose 재확보
→ Pose age 및 confidence 확인
→ 노트북 GO
→ MOVING
```

Pose 복구만으로 자동 출발하지 않는다.

### 7.5 CONTROL_UNCERTAIN

```text
조향·속도·엔코더 정보 불일치
→ WAITING
→ 센서 및 제어상태 확인
→ 안전조건 충족
→ GO 또는 RESET
```

오류가 잠금 수준으로 판단되면 ERROR로 전환한다.

---

## 8. ARRIVED 처리 규칙

ARRIVED는 상태가 아니라 중요 이벤트이다.

도착 조건을 만족하면 다음 순서로 처리한다.

```text
1. safeStop(ARRIVED)
2. last_completed_route_id 갱신
3. last_completed_waypoint_id 갱신
4. event_id 생성
5. pendingArrival = true
6. ARRIVED 전송
7. 내부 상태 READY
```

`EVENT_ACK`를 받기 전까지 같은 `event_id`의 ARRIVED를 재전송한다.

노트북은 동일 이벤트를 한 번만 처리한다.

최종 waypoint ARRIVED가 발생해도 즉시 슬롯을 `OCCUPIED`로 변경하지 않는다.

노트북이 카메라로 다음을 확인한 후 최종 `PARKED`를 판정한다.

- 차량 중심이 슬롯 내부에 있는가
- 차량 중심과 슬롯 중심의 오차가 허용 범위인가
- 차량 heading이 슬롯 목표 heading과 일치하는가
- 차량이 실제로 정지했는가

---

## 9. safeStop 처리 기준

모든 정지 동작은 `VehicleControlTask` 내부의 공통 함수에서 처리한다.

```text
safeStop(reason)
```

다른 Task가 직접 모터 PWM이나 방향 핀을 변경하지 않는다.

### 9.1 일시정지형 safeStop

대상:

- WAIT
- POSE_TIMEOUT
- POSE_INVALID
- ARRIVED

특징:

- 제어된 정지
- WAIT 계열은 target과 phase 유지
- ARRIVED는 완료 target 폐기
- 이후 명시적인 명령에 따라 재개 또는 다음 waypoint 수행

### 9.2 잠금형 safeStop

대상:

- STOP
- COMM_TIMEOUT
- ERROR
- Watchdog 또는 제어 Task 이상

특징:

- 가장 강한 검증된 안전정지
- target 폐기
- waypoint buffer 폐기
- 자동 재출발 금지
- RESET 또는 재동기화 필요

실제 MD10C에서 PWM 0이 관성정지인지 능동제동인지 테스트한 후 최종 정지 출력을 확정한다.

---

## 10. 명령 선점 규칙

일반 신뢰성 명령은 차량 한 대당 하나만 응답 대기 상태로 둔다.

```text
일반 outstanding command = 1
```

우선순위:

```text
STOP > WAIT > 일반 신뢰성 명령
```

### WAIT 선점

```text
WAYPOINT 응답 대기 중
→ WAIT 수신
→ WAYPOINT 재전송 일시 중단
→ 차량 정지
→ WAITING STATUS 확인
→ last_processed_cmd_seq와 target 상태로 기존 명령 처리 여부 판단
```

### STOP 선점

```text
일반 명령 응답 대기 중
→ STOP 수신
→ 기존 명령 재전송 취소
→ target 및 buffer 폐기
→ EMERGENCY_STOP
```

STOP 이전 명령의 늦은 응답은 차량 상태 복구에 사용하지 않는다.

---

## 11. 통신 재접속 및 재부팅

### 11.1 동일 boot_id 재접속

TCP 연결만 끊긴 상황으로 본다.

```text
통신 단절
→ safeStop(COMM_TIMEOUT)
→ 재접속
→ SYNCING
→ pending ARRIVED 및 최근 완료정보 동기화
→ 기존 target 폐기
→ READY
→ 현재 Pose 기준 새 route
```

### 11.2 새로운 boot_id

ESP32가 실제 재부팅된 상황으로 본다.

```text
새 boot_id 확인
→ 이전 session 폐기
→ 이전 target 및 buffer 신뢰 금지
→ RAM 기반 pending event 신뢰 금지
→ 카메라로 실제 차량 상태 확인
→ 새 session 생성
→ READY
→ 새 route
```

재접속 또는 재부팅 이후 기존 주행을 자동으로 재개하지 않는다.

---

## 12. 상태 보고 필드

STATUS에는 상태머신 동기화에 필요한 다음 정보를 포함한다.

- `state`
- `mode`
- `status_seq`
- `ack_seq` 또는 `last_processed_cmd_seq`
- `route_id`
- `waypoint_id`
- `phase`
- `target_loaded`
- `wait_reason`
- `error_code`
- `latest_pose_seq`
- `pose_age_ms`
- `encoder_speed_cm_s`
- `encoder_distance_cm`
- `last_completed_route_id`
- `last_completed_waypoint_id`
- `pending_event_id`

명령 처리 직후에는 `ack_seq`를 포함한 STATUS 또는 `COMMAND_RESULT`를 즉시 전송한다.

---

## 13. 상태머신 구현 원칙

1. 차량 상태와 모터·서보 출력의 최종 소유자는 `VehicleControlTask`이다.
2. 다른 Task는 상태를 직접 변경하지 않고 이벤트만 전달한다.
3. STOP은 모든 상태에서 적용한다.
4. WAIT는 현재 주행 맥락을 유지한다.
5. GO는 복구 가능한 WAITING 상태에서만 적용한다.
6. COMM_TIMEOUT, ERROR, EMERGENCY_STOP은 GO로 해제하지 않는다.
7. RESET은 READY까지만 복구하며 자동 주행을 시작하지 않는다.
8. POSE_UPDATE 수신 재개만으로 차량을 자동 출발시키지 않는다.
9. 통신 재연결만으로 차량을 자동 출발시키지 않는다.
10. 신규 route는 새로운 `route_id`를 사용한다.
11. MOVING 중 신규 WAYPOINT 교체는 1차 구현에서 금지한다.
12. ARRIVED는 중요 이벤트이며 `EVENT_ACK`까지 유지한다.
13. 최종 PARKED 판정은 노트북이 카메라로 검증한다.
14. 안전 잠금 상태는 통신 상태 변화보다 우선한다.
15. 잘못된 명령이나 상태 불일치는 차량 이동으로 이어져서는 안 된다.

---

## 14. 구현 예정 항목

본 문서를 기준으로 다음 항목을 코드에 반영한다.

- `enum class VehicleState`
- `enum class ControlMode`
- `enum class ParkingPhase`
- `enum class WaitReason`
- `enum class ErrorCode`
- 상태별 명령 허용 함수
- 상태 전이 함수
- `safeStop(reason)`
- target 및 waypoint buffer 초기화 함수
- GO 실행조건 검증 함수
- timeout 감시 로직
- STATUS 생성 함수
- ARRIVED pending 및 EVENT_ACK 처리
- 상태 전이 단위 테스트