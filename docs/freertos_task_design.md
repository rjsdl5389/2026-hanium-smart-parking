# ESP32 FreeRTOS Task 및 Queue 설계

## 1. 문서 목적

본 문서는 자율주행 기반 지능형 주차 운영 시스템에서 ESP32 펌웨어의 FreeRTOS 기반 실행 구조를 정의한다.

주요 목적은 다음과 같다.

- 통신 처리와 차량 제어의 역할 분리
- STOP·WAIT 명령의 즉시 처리
- 차량 상태머신과 모터·서보 출력의 단일 소유권 보장
- POSE_UPDATE·STATUS와 같은 최신값 데이터의 적절한 처리
- 엔코더 센서 처리와 차량 제어 주기 분리
- 송신 메시지의 우선순위 관리
- 일반 명령과 진단 명령의 Queue 기아 방지
- 통신 단절·Pose 유실·Task 정지 상황의 fail-safe 확보

본 설계의 핵심 원칙은 다음과 같다.

> 모든 차량 상태 전이와 모터·서보 출력은 VehicleControlTask 한 곳에서만 최종 결정한다.

---

## 2. 전체 Task 구성

ESP32 애플리케이션은 다음 Task를 기준으로 구성한다.

1. `CommunicationTask`
2. `VehicleControlTask`
3. `SensorTask`
4. `TransmitTask`
5. `DiagnosticTask`

필요 시 Wi-Fi 연결 관리 기능은 `CommunicationTask` 내부 상태로 관리하거나 별도 `ConnectionManagerTask`로 분리할 수 있다. 1차 구현에서는 구조를 단순화하기 위해 `CommunicationTask` 내부에 포함한다.

---

## 3. Task 역할 요약

| Task | 주요 역할 | 상대 우선순위 |
|---|---|---|
| `VehicleControlTask` | 상태머신, waypoint 추종, 모터·서보 출력, 안전정지 | 가장 높음 |
| `CommunicationTask` | TCP 연결, NDJSON 수신, JSON 파싱·검증, 메시지 분류 | 높음 |
| `SensorTask` | 엔코더 수집, 속도·거리 계산, 센서 오류 감지 | 중간 |
| `TransmitTask` | STATUS·ARRIVED·오류 메시지 우선순위 송신 | 중간 |
| `DiagnosticTask` | 설정 조회, 진단, 일반 로그 | 낮음 |

정확한 FreeRTOS priority 숫자는 다른 라이브러리 Task와 ESP32 내부 Wi-Fi Task를 고려해 구현 시 확정한다.

중요한 것은 절대 숫자가 아니라 다음 상대 관계이다.

```text
VehicleControlTask
> CommunicationTask
> SensorTask / TransmitTask
> DiagnosticTask
```

단, 높은 우선순위 Task가 CPU를 계속 점유해서는 안 된다. 모든 Task는 평상시 Queue·Notification·주기를 기다리며 BLOCKED 상태를 유지해야 한다.

---

## 4. VehicleControlTask

### 4.1 책임

`VehicleControlTask`는 차량 동작의 최종 권한을 가진다.

담당 기능:

- 차량 상태머신 관리
- 현재 제어 모드 관리
- 최신 Pose와 waypoint 참조
- 위치 오차 계산
- heading 오차 계산
- 조향 명령 계산
- 목표 속도 결정
- 모터 PWM 출력
- 서보 출력
- WAIT·STOP 처리
- 통신 timeout 처리
- Pose timeout 처리
- waypoint 도착 판정
- `safeStop(reason)` 실행
- ARRIVED 이벤트 생성 요청

### 4.2 단일 소유권 원칙

다른 Task가 모터 PWM이나 서보 출력 함수를 직접 호출하면 안 된다.

금지 예시:

```text
CommunicationTask가 STOP 수신
→ CommunicationTask가 직접 PWM 0 출력
```

권장 구조:

```text
CommunicationTask가 STOP 수신
→ VehicleControlTask에 긴급 Notification 전달
→ VehicleControlTask가 safeStop() 실행
```

이 원칙을 적용하는 이유:

- 상태와 실제 출력 불일치 방지
- 동시에 여러 Task가 PWM을 수정하는 race condition 방지
- STOP 직후 다른 Task가 기존 PWM을 다시 출력하는 문제 방지
- 디버깅 시 출력 변경 주체를 한 곳으로 제한

### 4.3 실행 방식

`VehicleControlTask`는 평상시 busy loop로 계속 실행하지 않는다.

다음 입력을 기다린다.

- STOP·WAIT 긴급 Notification
- 일반 Command Queue
- 새로운 Pose 도착 신호
- SensorTask의 새 엔코더 데이터
- 주기 제어 Tick

권장 개념 구조:

```text
Notification 또는 제어주기 대기
→ 긴급 이벤트 확인
→ 현재 상태 확인
→ timeout 확인
→ 최신 Pose·엔코더 확인
→ 상태머신 처리
→ 제어값 계산
→ 모터·서보 출력
→ 도착 여부 판정
→ 상태 변경 시 송신 요청
```

### 4.4 처리 우선순위

한 번 깨어났을 때 다음 순서로 처리한다.

```text
1. STOP
2. 하드웨어 오류
3. COMM_TIMEOUT
4. WAIT
5. POSE_TIMEOUT
6. RESET·GO·WAYPOINT 등 일반 명령
7. waypoint 추종 제어
8. 상태보고 갱신
```

STOP과 WAIT가 동시에 들어온 경우 STOP을 적용한다.

---

## 5. CommunicationTask

### 5.1 책임

담당 기능:

- Wi-Fi 연결 상태 관리
- TCP 서버 연결
- TCP 재접속
- HELLO 전송 및 HELLO_ACK 수신
- receive buffer 관리
- `\n` 기준 NDJSON 메시지 분리
- JSON 파싱
- 프로토콜 version 검증
- 필수 필드 검증
- 값 범위 검증
- `car_id`, `session_id`, `seq`, `route_id` 검증
- 메시지 종류별 분류
- heartbeat 수신 시간 갱신
- 적절한 Queue·Notification으로 전달

### 5.2 처리하지 않는 기능

`CommunicationTask`는 다음을 직접 수행하지 않는다.

- 차량 상태 최종 변경
- 모터 PWM 출력
- 서보 출력
- waypoint 도착 판정
- 안전정지 출력

통신 Task는 메시지를 해석하고 전달하지만, 차량 행동을 최종 결정하지 않는다.

### 5.3 수신 버퍼 처리

TCP는 메시지 경계를 보장하지 않으므로 영구 receive buffer를 사용한다.

```text
TCP bytes 수신
→ receiveBuffer에 추가
→ 개행 문자 검색
→ 완전한 JSON 한 개 추출
→ 파싱·검증
→ 처리한 문자열 제거
→ 다음 개행이 있으면 반복
```

처리 규칙:

- 최대 JSON 길이 초과 시 해당 메시지 폐기
- 버퍼가 비정상적으로 증가하면 버퍼 초기화 및 오류 보고
- JSON 파싱 실패 시 차량 동작 금지
- 필수 필드 누락 시 명령 거절
- 현재 session과 다른 이동 명령은 실행 경로로 전달하지 않음

### 5.4 메시지 분류

수신 메시지는 다음 경로로 분류한다.

```text
STOP / WAIT
→ Urgent Task Notification

HEARTBEAT
→ CommunicationTask에서 즉시 처리

POSE_UPDATE / DIRECT_CONTROL
→ 최신값 덮어쓰기 구조

SET_MODE / WAYPOINT / GO / RESET
→ General Command Queue

HELLO_ACK / EVENT_ACK
→ 연결·이벤트 관리 경로

진단·설정 명령
→ Low Queue
```

---

## 6. STOP·WAIT 긴급 처리

### 6.1 Task Notification 사용 이유

STOP과 WAIT는 일반 Command Queue 뒤에서 기다리면 안 된다.

예:

```text
Queue 앞에 여러 진단 명령 존재
→ STOP이 Queue 마지막에 삽입
→ 처리 지연
```

따라서 STOP·WAIT은 `VehicleControlTask`에 직접 Task Notification을 전달한다.

장점:

- Queue 순서와 무관하게 즉시 Task 깨움
- 메모리 사용이 작음
- 높은 우선순위 Task로 빠르게 전환 가능
- 긴급 이벤트 비트 표현 가능

### 6.2 Notification 비트 예시

```text
BIT 0: STOP_REQUEST
BIT 1: WAIT_REQUEST
BIT 2: COMM_TIMEOUT_REQUEST
BIT 3: SENSOR_FAULT_REQUEST
BIT 4: NEW_POSE_AVAILABLE
```

처리 시 STOP 비트가 있으면 다른 이동 관련 비트보다 우선한다.

### 6.3 STOP 처리

```text
STOP Notification 수신
→ safeStop(STOP)
→ target 폐기
→ waypoint buffer 폐기
→ EMERGENCY_STOP
→ 즉시 High Priority STATUS 생성
```

### 6.4 WAIT 처리

```text
WAIT Notification 수신
→ safeStop(WAIT)
→ target 유지
→ route·waypoint 유지
→ phase 유지
→ WAITING
→ wait_reason 저장
→ 즉시 Medium Priority STATUS 생성
```

---

## 7. General Command Queue

### 7.1 대상 메시지

- `SET_MODE`
- `WAYPOINT`
- `GO`
- `RESET`

필요에 따라 연결 동기화 완료 명령도 포함할 수 있다.

### 7.2 Queue 데이터 구조 예시

```text
CommandMessage
- type
- seq
- session_id
- route_id
- waypoint_id
- payload
- payload_hash
- received_time_ms
```

구현에서는 문자열 전체를 Queue에 복사하기보다 JSON 파싱 후 검증된 구조체만 전달하는 것을 권장한다.

### 7.3 Queue 길이

1차 구현에서는 길이를 작게 유지한다.

권장 초기 후보:

```text
General Command Queue length = 8
```

노트북은 일반 outstanding command를 하나만 허용하므로 정상 상황에서 Queue가 길게 쌓일 이유가 없다.

Queue가 가득 찼다면 다음 중 하나일 가능성이 높다.

- 통신 Task가 중복 명령을 계속 삽입함
- VehicleControlTask가 정지함
- 명령 생성 속도가 설계보다 빠름
- 오래된 명령이 정리되지 않음

Queue full은 단순히 새 명령을 버리고 끝내지 말고 오류 로그와 상태보고 대상이 되어야 한다.

---

## 8. POSE_UPDATE 최신값 처리

### 8.1 Queue 누적 금지

Pose는 시간 순서대로 모두 처리하는 데이터가 아니라 최신 측정값이 중요한 데이터이다.

잘못된 구조:

```text
Pose 100
Pose 101
Pose 102
Pose 103
→ VehicleControlTask가 오래된 값부터 순서대로 처리
```

올바른 구조:

```text
Pose 100 대기 중
→ Pose 101 도착
→ Pose 100을 Pose 101로 교체
```

### 8.2 구현 선택지

#### 방법 A: 길이 1 Queue + overwrite

```text
xQueueOverwrite(latestPoseQueue, &pose)
```

장점:

- FreeRTOS API로 구조가 명확함
- 새 Pose 도착 시 Task를 깨우기 쉬움

#### 방법 B: 공유 latestPose + mutex

```text
latestPose = newPose
```

장점:

- 불필요한 Queue 복사 감소
- Pose 구조체가 커질 때 유리

1차 구현에서는 길이 1 Queue와 overwrite 방식을 권장한다.

### 8.3 Pose 처리 규칙

- 현재 `session_id`와 일치해야 함
- `pose_seq`가 최신이어야 함
- `valid=true`여야 함
- `measurement_age_ms`가 허용 범위 이내여야 함
- 좌표가 맵 범위 안에 있어야 함
- confidence가 최소 기준 이상이어야 함

유효하지 않은 Pose는 제어에 사용하지 않지만, Pose 유실 판단을 위해 마지막 수신 시각과 마지막 유효 Pose 시각은 구분해서 저장한다.

```text
last_pose_message_rx_ms
last_valid_pose_ms
```

`POSE_TIMEOUT`은 마지막 유효 Pose 기준으로 판단한다.

---

## 9. DIRECT_CONTROL 최신값 처리

`REMOTE_DIRECT` 개발 모드에서 사용한다.

처리 방식:

- 길이 1 Queue 또는 최신 구조체
- 최신 `control_seq`만 적용
- 과거 명령 재생 금지
- `valid_for_ms` 초과 시 안전정지

```text
DIRECT_CONTROL 도착
→ latestDirectControl 갱신
→ VehicleControlTask 깨움

유효시간 만료
→ safeStop(DIRECT_CONTROL_TIMEOUT)
```

DIRECT_CONTROL은 최종 자율주행 모드에서 사용하지 않는다.

---

## 10. SensorTask

### 10.1 책임

담당 기능:

- 엔코더 펄스 읽기
- 일정 주기마다 펄스 변화량 계산
- 바퀴 회전수 계산
- 속도 계산
- 이동거리 누적
- 정지 여부 판단 보조
- 엔코더 이상 감지
- 최신 SensorFeedback 제공

### 10.2 ISR과 Task 역할 분리

엔코더 GPIO 인터럽트에서는 최소 작업만 수행한다.

ISR 담당:

```text
펄스 카운트 증가
필요 시 방향 비트 기록
```

ISR에서 하지 않는 작업:

- JSON 생성
- Serial 대량 출력
- 상태머신 전이
- 모터 제어
- 복잡한 속도 계산

속도와 거리 계산은 `SensorTask`에서 수행한다.

### 10.3 SensorFeedback 예시

```text
SensorFeedback
- encoder_count
- delta_count
- speed_cm_s
- delta_distance_cm
- accumulated_distance_cm
- stationary
- sensor_valid
- updated_time_ms
```

### 10.4 실행 주기

초기 후보:

```text
SensorTask: 10~20 ms 주기
엔코더 속도 제어: 50~100 Hz
```

실제 주기는 엔코더 PPR, 차량 속도, 노이즈 및 CPU 사용률 측정 후 확정한다.

---

## 11. TransmitTask

### 11.1 책임

담당 기능:

- ESP32에서 노트북으로 전송할 메시지 관리
- 메시지 우선순위 적용
- JSON 직렬화
- 개행 문자 추가
- TCP 송신
- 송신 실패 감지
- ARRIVED 재전송 관리
- 최신 STATUS coalescing

### 11.2 송신 우선순위

#### High Priority

- `ARRIVED`
- `ERROR`
- `EMERGENCY_STOP`
- `COMM_TIMEOUT`
- `HELLO`
- 동기화 관련 메시지

#### Medium Priority

- 명령 처리 결과 STATUS
- `READY`
- `MOVING`
- `WAITING`
- `COMMAND_RESULT`

#### Low Priority

- 주기 STATUS
- 엔코더 정보
- 배터리 정보
- 일반 진단 로그

### 11.3 STATUS coalescing

주기 STATUS는 Queue에 모두 쌓지 않는다.

```text
STATUS 100 생성
→ 아직 송신 전
→ STATUS 101 생성
→ STATUS 100 폐기, STATUS 101 유지
```

길이 1 Low STATUS Queue 또는 `latestStatus` 구조체를 사용한다.

명령 응답용 STATUS는 주기 STATUS보다 우선하며, `ack_seq`를 포함해 반드시 송신 시도한다.

### 11.4 ARRIVED 처리

ARRIVED는 일반 주기 STATUS와 다르게 ACK가 필요한 중요 이벤트이다.

```text
ARRIVED 생성
→ pendingEvent 저장
→ High Priority 송신
→ EVENT_ACK 대기
→ timeout 시 같은 event_id로 재전송
```

재전송 중 새 JSON을 임의로 변경하지 않는다. 같은 이벤트 식별자와 같은 완료 정보를 유지한다.

---

## 12. DiagnosticTask

### 12.1 책임

- 설정값 조회
- 시스템 통계 출력
- Queue 사용량 확인
- Task stack 여유 확인
- timeout 발생 횟수 기록
- 메시지 거절 횟수 기록
- 일반 디버그 로그 처리

### 12.2 낮은 우선순위 원칙

DiagnosticTask는 차량 제어보다 우선해서는 안 된다.

안전 상태에서는 진단 처리가 지연될 수 있다.

```text
STOP 처리 중
EMERGENCY_STOP
ERROR
COMM_TIMEOUT
SYNCING
```

위 상황에서는 Low Queue가 일시적으로 굶더라도 안전 처리가 우선이다.

---

## 13. Low Queue 기아 방지

정상 운용 중 일반 명령이 지속해서 들어오더라도 진단 명령이 영원히 처리되지 않도록 처리 비율을 둔다.

초기 정책:

```text
일반 메시지 N개 처리
→ Low 메시지 1개 처리
```

초기 후보:

```text
N = 3 또는 5
```

예:

```text
General 3개 처리
→ Low 1개 확인
→ General 3개 처리
→ Low 1개 확인
```

예외:

다음 상황에서는 Low 처리 비율을 보장하지 않는다.

- STOP 대기 또는 처리 중
- WAIT 긴급 처리 중
- EMERGENCY_STOP
- ERROR
- COMM_TIMEOUT
- SYNCING

추가 보호:

- Low Queue 최대 길이 제한
- 오래된 요청 TTL 적용
- 일정 시간 이상 대기한 메시지 로그
- 동일 진단 요청 중복 제거

---

## 14. 공유 데이터와 동기화

### 14.1 주요 공유 데이터

- `latestPose`
- `latestSensorFeedback`
- `latestDirectControl`
- `currentVehicleStatus`
- `currentTarget`
- `pendingArrivalEvent`
- 통신 상태와 session 정보

### 14.2 소유권 권장안

| 데이터 | 최종 소유 Task |
|---|---|
| 차량 상태 | VehicleControlTask |
| 제어 모드 | VehicleControlTask |
| 현재 target | VehicleControlTask |
| 모터·서보 출력 | VehicleControlTask |
| 최신 Pose 수신 원본 | CommunicationTask가 갱신, VehicleControlTask가 소비 |
| 엔코더 측정값 | SensorTask가 갱신, VehicleControlTask가 소비 |
| TCP 연결 상태 | CommunicationTask |
| 송신 Queue | TransmitTask |
| pending ARRIVED | VehicleControlTask가 생성, TransmitTask가 재전송 관리 |

### 14.3 보호 방식

- 단순 플래그: atomic 또는 critical section
- 작은 구조체: Queue 전달
- 최신값 구조체: mutex 또는 overwrite Queue
- ISR 공유 카운터: ISR-safe critical section 또는 atomic

오랜 시간 mutex를 잡은 상태에서 JSON 직렬화나 TCP 송신을 수행하지 않는다.

---

## 15. 상태 이벤트 전달 구조

권장 흐름:

```text
CommunicationTask
→ 검증된 CommandMessage
→ VehicleControlTask
→ 상태 전이
→ StatusSnapshot 생성
→ TransmitTask
→ 노트북 전송
```

센서 흐름:

```text
Encoder ISR
→ pulseCount 증가
→ SensorTask가 주기적으로 읽음
→ SensorFeedback 갱신
→ VehicleControlTask가 제어에 사용
```

Pose 흐름:

```text
POSE_UPDATE 수신
→ CommunicationTask 검증
→ latestPose overwrite
→ VehicleControlTask Notification
→ 제어 오차 갱신
```

---

## 16. safeStop(reason) 설계

모든 정지는 VehicleControlTask의 공통 인터페이스를 사용한다.

```text
safeStop(reason)
```

### 16.1 reason 후보

```text
REMOTE_WAIT
POSE_TIMEOUT
DIRECT_CONTROL_TIMEOUT
COMM_TIMEOUT
EMERGENCY_STOP
SENSOR_FAULT
CONTROL_FAULT
BOOT_SAFETY
WATCHDOG_RECOVERY
```

### 16.2 제어된 정지

대상:

- WAIT
- POSE_TIMEOUT
- DIRECT_CONTROL_TIMEOUT

처리:

- 모터 출력 안전정지
- target 유지 여부를 reason에 따라 결정
- WAITING 진입
- 자동 재출발 금지

### 16.3 잠금 정지

대상:

- STOP
- COMM_TIMEOUT
- ERROR
- Watchdog 재부팅

처리:

- 가장 강한 검증된 안전정지
- target 폐기
- waypoint buffer 폐기
- 잠금 상태 진입
- GO 거절
- RESET 또는 재동기화 필요

### 16.4 실제 정지 방식

`PWM=0`이 실제로 coast인지 brake인지는 MD10C 테스트를 통해 확인해야 한다.

따라서 상위 로직에서는 정지를 단순 `PWM=0`으로 정의하지 않고 `safeStop()`으로 추상화한다.

---

## 17. Timeout 감시

### 17.1 COMM_TIMEOUT

판정 기준:

```text
현재 시각 - last_valid_link_rx_ms
> COMM_TIMEOUT
```

처리:

```text
VehicleControlTask에 COMM_TIMEOUT Notification
→ safeStop(COMM_TIMEOUT)
→ COMM_TIMEOUT 상태
→ 자동 재개 금지
```

### 17.2 POSE_TIMEOUT

판정 기준:

```text
현재 시각 - last_valid_pose_ms
> POSE_TIMEOUT
```

처리:

```text
safeStop(POSE_TIMEOUT)
→ WAITING
→ wait_reason=POSE_TIMEOUT
```

### 17.3 DIRECT_CONTROL timeout

판정 기준:

```text
현재 시각 - last_direct_control_ms
> valid_for_ms
```

처리:

```text
safeStop(DIRECT_CONTROL_TIMEOUT)
```

### 17.4 ARRIVED 재전송

```text
현재 시각 - last_arrived_tx_ms
> ARRIVED_RETRY_MS
AND pendingEvent 존재
→ 같은 ARRIVED 재전송
```

---

## 18. Watchdog 및 부팅 안전

### 18.1 부팅 초기 출력

ESP32 부팅 직후 다음을 가장 먼저 수행한다.

```text
모터 PWM 비활성화
서보 안전 중앙값 또는 안전값 설정
드라이버 제어 핀 안전 상태 설정
```

Wi-Fi가 연결되거나 상태머신이 초기화되기 전까지 차량 이동을 허용하지 않는다.

### 18.2 Task Watchdog

중요 Task가 장시간 실행되지 않는 상황을 감지한다.

감시 대상 후보:

- VehicleControlTask
- CommunicationTask
- SensorTask

Watchdog으로 재부팅된 경우:

```text
새 boot_id 생성
→ 모터 출력 OFF
→ SYNCING
→ 이전 route 자동 복구 금지
```

### 18.3 Stack 및 Queue 모니터링

DiagnosticTask에서 다음 값을 기록한다.

- Task별 high-water mark
- Queue 최대 사용량
- Queue full 횟수
- JSON 파싱 실패 횟수
- timeout 횟수
- watchdog reset reason

---

## 19. 초기 주기 및 크기 후보

아래 값은 구현 시작값이며 실제 시험 후 조정한다.

| 항목 | 초기 후보 |
|---|---:|
| VehicleControlTask 제어 주기 | 20~50 ms |
| SensorTask 주기 | 10~20 ms |
| STATUS 생성 주기 | 100~200 ms |
| HEARTBEAT 주기 | 250 ms |
| COMM_TIMEOUT | 1,000 ms |
| POSE_TIMEOUT | 300~500 ms |
| ARRIVED 재전송 | 300 ms |
| General Command Queue 길이 | 8 |
| Low Queue 길이 | 4~8 |
| latestPose Queue 길이 | 1 |
| latestStatus Queue 길이 | 1 |
| Low 기아 방지 비율 | 3:1 또는 5:1 |

정확한 값은 다음을 측정한 뒤 확정한다.

- Wi-Fi 지연
- JSON 파싱 시간
- 카메라 Pose 주기
- 엔코더 PPR
- 차량 속도
- 제동거리
- CPU 사용률
- Task stack 사용량

---

## 20. 구현 단계

### 1단계: 최소 Task 구조

- CommunicationTask
- VehicleControlTask
- TransmitTask
- WAIT·STOP Notification
- General Command Queue

### 2단계: 최신값 데이터

- POSE_UPDATE overwrite Queue
- DIRECT_CONTROL overwrite Queue
- STATUS coalescing

### 3단계: SensorTask 추가

- 엔코더 ISR
- 속도 계산
- 이동거리 계산
- SensorFeedback 전달

### 4단계: timeout 및 fail-safe

- COMM_TIMEOUT
- POSE_TIMEOUT
- DIRECT_CONTROL timeout
- safeStop(reason)

### 5단계: 중요 이벤트 신뢰성

- ARRIVED pending event
- EVENT_ACK
- 재전송
- 재접속 동기화

### 6단계: 진단 및 Watchdog

- DiagnosticTask
- Queue 사용량
- Task stack 확인
- Watchdog
- reset reason 로그

---

## 21. 핵심 설계 원칙

1. VehicleControlTask가 차량 상태머신의 유일한 소유자이다.
2. VehicleControlTask가 모터와 서보 출력의 유일한 소유자이다.
3. CommunicationTask는 메시지를 검증하고 전달하지만 차량을 직접 움직이지 않는다.
4. STOP과 WAIT는 일반 Queue를 거치지 않고 Task Notification으로 전달한다.
5. STOP이 WAIT보다 우선한다.
6. HEARTBEAT는 CommunicationTask에서 즉시 처리한다.
7. POSE_UPDATE와 DIRECT_CONTROL은 과거 값을 쌓지 않고 최신값으로 덮어쓴다.
8. 일반 명령은 검증된 구조체 형태로 General Command Queue에 전달한다.
9. 주기 STATUS는 최신값 하나만 유지한다.
10. ARRIVED는 EVENT_ACK를 받을 때까지 재전송한다.
11. ISR에서는 최소 작업만 수행하고 복잡한 처리는 Task에서 수행한다.
12. Low Queue 기아 방지는 정상 상황에서만 보장하며 안전 상황에서는 제어를 우선한다.
13. 모든 정지는 `safeStop(reason)`을 통해 실행한다.
14. 통신·Pose가 복구되어도 자동으로 주행을 재개하지 않는다.
15. Watchdog 재부팅 후에는 새 boot_id로 SYNCING부터 시작한다.
16. 높은 우선순위 Task도 평상시에는 BLOCKED 상태를 유지해야 한다.