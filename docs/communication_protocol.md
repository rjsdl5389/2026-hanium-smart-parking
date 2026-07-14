# 노트북–ESP32 통신 프로토콜 설계

## 1. 문서 목적

본 문서는 「자율주행 기반 지능형 주차 운영 시스템」에서 노트북 기반 상위 제어기와 ESP32 기반 RC카 하위 제어기 사이의 통신 규격을 정의한다.

설계 목표는 다음과 같다.

- 차량 제어 명령의 안전한 전달 및 실행 결과 확인
- 명령 중복, 재전송, 지연 및 오래된 명령 처리
- WAIT·STOP 긴급 명령의 우선 처리
- 카메라 Pose와 waypoint 전달
- ARRIVED 이벤트 유실 방지
- 통신 단절 및 Pose 단절 시 안전정지
- TCP 재접속 및 ESP32 재부팅 시 상태 동기화
- 다중 차량 환경에서 세션 및 경로 상태 분리

핵심 역할은 다음과 같이 구분한다.

- **노트북**: 카메라 인식, 전역 위치 추정, 주차 슬롯 배정, 전체 경로 생성, waypoint 생성, 충돌 판단, WAIT·GO·STOP 결정
- **ESP32**: waypoint 추종, 모터·서보 제어, 엔코더 처리, 즉시 안전정지, 상태 및 이벤트 피드백

---

## 2. 통신 기본 구조

- 통신망: Wi-Fi
- 전송 계층: TCP
- 연결 형태: 지속 연결
- 노트북: TCP Server
- ESP32: TCP Client
- 메시지 형식: JSON
- 메시지 구분자: 줄바꿈 문자 `\n`
- 초기 최대 메시지 길이: 512바이트

전송 예시는 다음과 같다.

```text
{"version":1,"type":"WAIT","seq":31}\n
{"version":1,"type":"GO","seq":32}\n
```

TCP는 메시지 단위가 아니라 바이트 스트림이므로 한 번의 `send()`와 한 번의 `recv()`가 일치한다고 가정하지 않는다.

수신 측은 다음 순서로 처리한다.

```text
TCP 바이트 수신
→ receiveBuffer 뒤에 추가
→ 줄바꿈 문자 검색
→ 줄바꿈 앞까지 완전한 JSON 메시지로 추출
→ JSON 파싱 및 필드 검증
→ 처리한 데이터 제거
→ 남은 버퍼에 줄바꿈이 있으면 반복
```

줄바꿈이 아직 수신되지 않은 불완전 메시지는 파싱하지 않고 다음 데이터가 도착할 때까지 보관한다.

---

## 3. TCP가 보장하는 것과 보장하지 않는 것

TCP는 다음을 보장한다.

- 전송 순서 유지
- 손실된 패킷 재전송
- 중복 패킷 제거
- 바이트 오류 검출

그러나 다음은 보장하지 않는다.

```text
노트북 send() 성공
≠ ESP32 애플리케이션이 메시지를 파싱함
≠ ESP32가 명령을 실행함
≠ 실제 모터가 정지하거나 움직임
```

따라서 TCP 위에 애플리케이션 수준의 다음 처리가 필요하다.

- 명령별 sequence 번호
- 상태 응답을 통한 실행 결과 확인
- 동일 명령 재전송
- 멱등성
- 중요 이벤트 ACK
- heartbeat
- 재접속 상태 동기화

---

## 4. 메시지 성격별 신뢰성 처리

모든 메시지를 동일한 방식으로 처리하지 않는다. 메시지의 성격에 따라 신뢰성 방식을 구분한다.

### 4.1 신뢰성 제어 명령

대상:

- `SET_MODE`
- `WAYPOINT`
- `WAIT`
- `GO`
- `STOP`
- `RESET`

처리 원칙:

- 노트북이 `seq`를 부여한다.
- ESP32는 실제 처리 상태 또는 `COMMAND_RESULT`를 반환한다.
- 응답의 `ack_seq`가 명령 확인 역할을 한다.
- 응답이 없으면 동일 `seq`와 동일 payload로 재전송한다.
- ESP32는 동일 명령을 중복 실행하지 않는다.

### 4.2 최신값 스트리밍 메시지

대상:

- `POSE_UPDATE`
- `DIRECT_CONTROL`
- `HEARTBEAT`
- 주기 `STATUS`

처리 원칙:

- 매 메시지마다 ACK하지 않는다.
- 유실된 과거 데이터를 재전송하지 않는다.
- 각 메시지 종류별 sequence로 최신 여부를 판단한다.
- 오래된 데이터는 폐기하고 최신 데이터만 유지한다.

### 4.3 중요 단발 이벤트

대상:

- `ARRIVED`

처리 원칙:

- ESP32가 `event_id`를 부여한다.
- 노트북의 `EVENT_ACK`를 받을 때까지 동일 이벤트를 재전송한다.
- 노트북은 동일 이벤트를 한 번만 처리한다.
- 중복 이벤트 수신 시 완료 처리를 반복하지 않고 ACK만 다시 보낸다.

### 4.4 지속 상태 및 오류

대상:

- `READY`
- `MOVING`
- `WAITING`
- `EMERGENCY_STOP`
- `COMM_TIMEOUT`
- `ERROR`

처리 원칙:

- 주기 `STATUS`에 반복 포함한다.
- 특정 STATUS가 유실돼도 다음 STATUS를 통해 복구한다.
- 지속 상태마다 별도 ACK를 요구하지 않는다.

---

## 5. 메시지 식별자

### 5.1 car_id

물리 차량 식별자이다.

```text
CAR_01
CAR_02
```

다중 차량 제어, 로그, 대시보드, Redis·Django 연동을 위해 모든 메시지에 포함한다.

### 5.2 boot_id

ESP32가 부팅될 때마다 새로 생성하는 값이다.

용도:

- 단순 TCP 재접속과 ESP32 재부팅 구분
- 이전 부팅의 이벤트와 현재 부팅의 이벤트 구분
- 기존 RAM 상태 신뢰 여부 판단

ARRIVED 이벤트의 실질적인 고유키는 다음과 같다.

```text
car_id + boot_id + event_id
```

### 5.3 session_id

노트북이 새 TCP 연결을 승인할 때 발급한다.

용도:

- 재접속 전후 명령 구분
- 이전 소켓에서 늦게 도착한 메시지 차단
- 동일 `car_id` 중복 연결 방지

`HELLO`에는 새 session_id가 없으며, 노트북이 `HELLO_ACK`에서 발급한다.

### 5.4 seq

노트북이 보내는 신뢰성 제어 명령 번호이다.

규칙:

- session마다 증가한다.
- 새 명령은 새 seq를 사용한다.
- 재전송은 기존 seq를 그대로 사용한다.
- 하나의 seq는 하나의 논리적 명령에만 사용한다.

정상 예시:

```text
WAIT seq=31
WAIT seq=31 재전송
GO seq=32
```

비정상 예시:

```text
WAIT seq=31
GO seq=31
```

### 5.5 pose_seq

`POSE_UPDATE` 순서 번호이다.

- 최신 카메라 Pose 판별
- 이전 pose_seq 무시
- ACK 및 과거 Pose 재전송 없음

### 5.6 control_seq

`DIRECT_CONTROL` 순서 번호이다.

- 최신 speed·steering 값만 적용
- 이전 값 무시

### 5.7 heartbeat_seq

HEARTBEAT 순서 번호이다.

- 링크 생존 및 로그 분석에 사용
- CommunicationTask에서 즉시 처리

### 5.8 status_seq

ESP32가 전송하는 STATUS 순서 번호이다.

- 노트북은 오래된 STATUS를 무시한다.

### 5.9 route_id

전체 경로의 버전이다.

```text
기존 route_id = 7
장애물 또는 충돌 위험으로 경로 재생성
새 route_id = 8
```

현재 route와 다른 오래된 WAYPOINT·GO·ARRIVED는 실행 또는 반영하지 않는다.

### 5.10 waypoint_id

하나의 route 내부 waypoint 순서이다.

### 5.11 event_id

ESP32에서 발생한 중요 이벤트 식별자이다.

1차 적용 대상은 `ARRIVED`이다.

---

## 6. 멱등성 및 중복 명령 처리

차량 상태를 바꾸는 모든 신뢰성 명령은 멱등하게 처리한다.

### 6.1 동일 seq + 동일 payload

동일 명령의 재전송으로 판단한다.

- 명령을 다시 실행하지 않는다.
- 기존 처리 결과 또는 현재 결과 상태만 다시 보낸다.

예시:

```text
WAYPOINT seq=20 최초 수신
→ 목표 저장
→ MOVING

WAYPOINT seq=20 재수신
→ 주행 제어 재초기화 금지
→ MOVING, ack_seq=20 재전송
```

### 6.2 동일 seq + 다른 payload

정상 동작에서는 발생하면 안 되는 프로토콜 오류이다.

가능한 원인:

- 노트북 seq 중복 발급
- 여러 Task의 seq 경쟁
- 잘못된 재전송 구현
- 오래된 Queue 데이터

처리:

```text
SEQ_CONFLICT
→ 명령 실행 금지
→ 현재 상태 유지
→ COMMAND_RESULT 전송
→ 오류 로그 기록
```

ESP32는 최근 처리 명령에 대해 다음 정보를 저장한다.

- session_id
- seq
- type
- route_id
- waypoint_id
- 주요 payload 또는 payload fingerprint
- 처리 결과

### 6.3 마지막 seq보다 작은 명령

오래된 명령으로 판단한다.

- 실행하지 않는다.
- 차량 상태를 변경하지 않는다.
- 필요하면 이전 처리 결과 또는 거절 응답을 보낸다.

---

## 7. Outstanding Command 정책

차량 한 대당 응답을 기다리는 일반 신뢰성 명령은 한 번에 하나만 허용한다.

```text
일반 outstanding command = 1
```

예시:

```text
WAYPOINT 전송
→ MOVING 또는 REJECTED 응답 확인
→ 다음 일반 명령 전송
```

이유:

- 명령과 결과 연결이 단순하다.
- 재전송과 취소가 명확하다.
- 상태 전이 충돌을 줄인다.
- 구현 및 디버깅 난이도가 낮아진다.

예외:

- `WAIT`
- `STOP`

WAIT와 STOP은 일반 명령 응답을 기다리는 중에도 선점할 수 있다.

```text
STOP > WAIT > 일반 신뢰성 명령
```

POSE_UPDATE와 HEARTBEAT는 스트리밍 데이터이므로 일반 outstanding command와 독립적으로 계속 전송한다.

---

## 8. WAIT 선점 처리

WAIT는 현재 주행을 일시 중지한다.

처리 순서:

```text
현재 일반 명령 재전송 일시 중단
→ 제어된 안전정지
→ 현재 target 유지
→ 현재 route·waypoint 유지
→ 현재 phase 유지
→ WAITING 진입
```

WAITING STATUS에는 다음 정보를 포함한다.

- last_processed_cmd_seq
- target_loaded
- route_id
- waypoint_id
- phase
- wait_reason

노트북은 이 정보를 기준으로 선점 이전 WAYPOINT가 ESP32에 적용됐는지 판단한다.

WAIT는 주행 맥락을 보존한다.

---

## 9. STOP 선점 처리

STOP은 현재 주행을 완전히 취소한다.

처리 순서:

```text
현재 일반 명령 재전송 취소
→ 가장 강한 검증된 안전정지
→ 현재 target 폐기
→ waypoint buffer 폐기
→ EMERGENCY_STOP 진입
```

STOP보다 이전에 발행된 명령의 늦은 응답은 차량 상태에 반영하지 않고 로그만 남긴다.

복구 순서:

```text
안전 원인 제거
→ RESET
→ READY
→ 현재 카메라 Pose 기준 새 경로 생성
→ 새 WAYPOINT 전송
```

STOP은 route_id 및 waypoint_id와 무관하게 적용한다.

---

## 10. 제어 모드

지원 모드는 다음과 같다.

```text
MANUAL_SERIAL
REMOTE_DIRECT
WAYPOINT_AUTO
```

### 10.1 MANUAL_SERIAL

- 시리얼 모니터 기반 모터·서보 단독 테스트
- 전진·후진·정지
- 좌·중앙·우 조향

### 10.2 REMOTE_DIRECT

- 노트북이 speed·steering 값을 직접 전달
- Wi-Fi 통신과 차량 반응을 검증하기 위한 중간 개발 단계
- 최종 자율주행 운용 모드는 아님

### 10.3 WAYPOINT_AUTO

- 노트북이 카메라 Pose와 waypoint를 제공
- ESP32가 로컬 조향·속도 제어 수행
- 최종 자율주행 운용 모드

모드 변경 조건:

- 차량 상태 READY
- 모터 정지
- 실행 중인 경로 없음

MOVING 중 SET_MODE는 거절한다.

STOP은 모든 모드에서 허용한다.

---

## 11. 연결 시작 및 동기화

### 11.1 HELLO

TCP 연결 직후 ESP32는 모터를 정지시키고 `SYNCING` 상태에서 HELLO를 보낸다.

```json
{
  "version": 1,
  "type": "HELLO",
  "car_id": "CAR_01",
  "boot_id": "B7A31F42",
  "firmware_version": "0.1.0",
  "state": "SYNCING",
  "previous_state": "COMM_TIMEOUT",
  "previous_session_id": "S16D802A",
  "last_processed_cmd_seq": 27,
  "current_route_id": 7,
  "current_waypoint_id": 3,
  "current_phase": "ALIGN",
  "target_loaded": true,
  "last_completed_route_id": 7,
  "last_completed_waypoint_id": 2,
  "pending_event_id": 51,
  "error_code": "NONE"
}
```

HELLO_ACK가 없으면 HELLO를 재전송한다.

초기 재전송 주기:

```text
500 ms
```

### 11.2 HELLO_ACK

노트북은 HELLO를 확인하고 새 session_id를 발급한다.

```json
{
  "version": 1,
  "type": "HELLO_ACK",
  "car_id": "CAR_01",
  "boot_id": "B7A31F42",
  "session_id": "S82F19C4",
  "result": "READY_ALLOWED",
  "command_seq_start": 1
}
```

result 후보:

- `READY_ALLOWED`: 동기화 완료, READY 전환 가능
- `HOLD`: 추가 상태 정리 또는 운영자 확인 필요
- `REJECTED`: 차량 ID, protocol version 또는 연결 승인 실패

TCP 연결 성공만으로 차량 이동을 허용하지 않는다.

---

## 12. HEARTBEAT

노트북은 카메라 처리 파이프라인과 독립적으로 HEARTBEAT를 전송한다.

```json
{
  "version": 1,
  "type": "HEARTBEAT",
  "car_id": "CAR_01",
  "session_id": "S82F19C4",
  "heartbeat_seq": 1024
}
```

처리:

- 메시지별 ACK 없음
- CommunicationTask에서 즉시 처리
- 일반 Command Queue에 넣지 않음
- 마지막 유효 링크 수신시간 갱신

오류 구분:

```text
HEARTBEAT 미수신
→ COMM_TIMEOUT

HEARTBEAT 정상
+ 유효 POSE_UPDATE 미수신
→ POSE_TIMEOUT
```

---

## 13. DIRECT_CONTROL

REMOTE_DIRECT 모드에서 사용하는 개발용 메시지이다.

```json
{
  "version": 1,
  "type": "DIRECT_CONTROL",
  "car_id": "CAR_01",
  "session_id": "S82F19C4",
  "control_seq": 203,
  "drive_pct": 35.0,
  "steering_pct": -20.0,
  "valid_for_ms": 300
}
```

권장 범위:

- drive_pct: -100 ~ 100
- steering_pct: -100 ~ 100

처리:

- 최신 control_seq만 적용
- 이전 제어값은 폐기
- 매 값 ACK 없음
- `valid_for_ms` 내에 새 명령이 없으면 안전정지

이 deadman 동작은 마지막 전진 명령 이후 송신 프로그램이 멈췄을 때 차량이 계속 주행하는 것을 방지한다.

---

## 14. POSE_UPDATE

노트북이 카메라로 측정한 차량의 현재 Pose를 전달한다.

```json
{
  "version": 1,
  "type": "POSE_UPDATE",
  "car_id": "CAR_01",
  "session_id": "S82F19C4",
  "pose_seq": 5021,
  "frame_id": 8122,
  "x_cm": 42.5,
  "y_cm": 76.0,
  "heading_deg": 91.2,
  "position_confidence": 0.96,
  "heading_confidence": 0.90,
  "heading_source": "FRONT_CUSHION",
  "measurement_age_ms": 42,
  "valid": true
}
```

heading_source 후보:

- `FRONT_CUSHION`
- `KEYPOINT`
- `OBB`
- `TRAJECTORY`
- `LAST_VALID`

처리:

- 최신 pose_seq만 적용
- ACK 없음
- 과거 Pose 재전송 없음
- Low Priority 진단 데이터가 아닌 실시간 제어 입력
- 길이 1 Queue overwrite 또는 mutex로 보호한 latestPose 사용

`valid=false`가 될 수 있는 상황:

- 차량 검출 실패
- Homography 실패
- 맵 범위 이탈
- 위치 confidence 부족
- heading confidence 부족
- 차량과 전방 쿠션 association 실패

유효하지 않은 Pose로 차량을 움직이지 않는다.

---

## 15. Pose Timeout

한두 프레임의 순간 검출 실패는 즉시 오류로 처리하지 않고 짧은 시간 동안 마지막 유효 Pose를 유지할 수 있다.

설정 시간 동안 새 유효 Pose가 없으면 다음과 같이 처리한다.

```text
제어된 안전정지
→ WAITING
→ wait_reason = POSE_TIMEOUT
```

유효 Pose가 다시 들어와도 자동 출발하지 않는다.

```text
유효 Pose 재확보
→ WAITING 유지
→ 노트북이 안전 확인
→ GO 수신
→ MOVING
```

안전 원칙:

> 자동 정지는 허용하지만 자동 재출발은 허용하지 않는다.

---

## 16. WAYPOINT

```json
{
  "version": 1,
  "type": "WAYPOINT",
  "car_id": "CAR_01",
  "session_id": "S82F19C4",
  "seq": 31,
  "route_id": 7,
  "waypoint_id": 3,
  "phase": "ALIGN",
  "x_cm": 42.5,
  "y_cm": 76.0,
  "target_heading_deg": 90.0,
  "motion_direction": "FORWARD",
  "arrival_mode": "STOP",
  "speed_cm_s": 6.0,
  "position_tolerance_cm": 5.0,
  "heading_tolerance_deg": 12.0,
  "heading_required": true,
  "is_final": false
}
```

phase 후보:

- `CRUISE`
- `APPROACH`
- `ALIGN`
- `ENTRY`
- `FINAL`

motion_direction 후보:

- `FORWARD`
- `REVERSE`

arrival_mode 후보:

- `STOP`
- `PASS`

1차 단일 waypoint 구현에서는 대부분 STOP을 사용한다.

향후 waypoint 버퍼링 단계에서는 일반 중간 CRUISE waypoint에 PASS를 사용할 수 있다.

---

## 17. WAYPOINT 상태별 처리

### 17.1 READY + WAYPOINT

```text
필드 및 상태 검증
→ target 저장
→ MOVING 진입
→ ack_seq가 포함된 STATUS 전송
```

### 17.2 WAITING + WAYPOINT

경로 재생성 후 새 목표를 등록할 때 사용한다.

```text
새 target 저장
→ WAITING 유지
→ GO 대기
```

새 target이 저장됐다는 이유만으로 자동 출발하지 않는다.

### 17.3 MOVING + 신규 WAYPOINT

1차 구현에서는 거절한다.

경로 변경 절차:

```text
WAIT
→ WAITING 확인
→ 새 WAYPOINT
→ GO
```

동일 seq의 기존 WAYPOINT 재전송은 신규 target 교체로 보지 않는다.

---

## 18. WAIT

```json
{
  "version": 1,
  "type": "WAIT",
  "car_id": "CAR_01",
  "session_id": "S82F19C4",
  "seq": 32,
  "reason": "COLLISION_RISK"
}
```

reason 후보:

- `COLLISION_RISK`
- `OBSTACLE`
- `REROUTING`
- `OPERATOR_REQUEST`

처리:

```text
제어된 안전정지
→ 현재 target 유지
→ route·waypoint 유지
→ phase 유지
→ WAITING
```

---

## 19. GO

```json
{
  "version": 1,
  "type": "GO",
  "car_id": "CAR_01",
  "session_id": "S82F19C4",
  "seq": 33,
  "route_id": 8,
  "waypoint_id": 1
}
```

실행 조건:

- 현재 session_id 일치
- 새로운 유효 seq
- state == WAITING
- target_loaded == true
- route_id 일치
- waypoint_id 일치
- 최신 Pose 유효
- Pose timeout 아님
- ERROR 아님
- EMERGENCY_STOP 아님
- SYNCING 아님
- COMM_TIMEOUT 아님

GO는 모든 정지를 해제하는 범용 명령이 아니다.

---

## 20. STOP

```json
{
  "version": 1,
  "type": "STOP",
  "car_id": "CAR_01",
  "session_id": "S82F19C4",
  "seq": 34,
  "reason": "EMERGENCY"
}
```

처리:

```text
가장 강한 검증된 안전정지
→ target 폐기
→ waypoint buffer 폐기
→ EMERGENCY_STOP
```

STOP은 다음과 관계없이 적용한다.

- 현재 제어 모드
- route_id
- waypoint_id
- 현재 주행 단계

STOP은 멱등하게 처리하며 GO로 해제하지 않는다.

---

## 21. RESET

```json
{
  "version": 1,
  "type": "RESET",
  "car_id": "CAR_01",
  "session_id": "S82F19C4",
  "seq": 35
}
```

실행 조건:

- 모터 정지
- 통신 정상
- 동기화 완료
- 복구 가능한 오류 원인 제거

처리:

```text
잠금 상태 해제
→ target 및 buffer 폐기
→ READY
```

RESET은 이동 명령이 아니다.

```text
READY
→ 카메라 Pose 확인
→ 새 경로 생성
→ 새 WAYPOINT 수신
```

---

## 22. ARRIVED

ESP32가 waypoint 도착을 판단한다.

위치만 필요한 waypoint:

```text
position_error <= position_tolerance_cm
```

heading_required waypoint:

```text
position_error <= position_tolerance_cm
AND
heading_error <= heading_tolerance_deg
```

도착 처리:

```text
waypoint 정지
→ last_completed 정보 갱신
→ pendingArrival = true
→ ARRIVED 전송
→ 내부 상태 READY
```

```json
{
  "version": 1,
  "type": "ARRIVED",
  "car_id": "CAR_01",
  "boot_id": "B7A31F42",
  "session_id": "S82F19C4",
  "event_id": 51,
  "route_id": 8,
  "waypoint_id": 1,
  "phase": "CRUISE",
  "x_cm": 54.1,
  "y_cm": 32.8,
  "heading_deg": 88.4
}
```

---

## 23. EVENT_ACK

```json
{
  "version": 1,
  "type": "EVENT_ACK",
  "car_id": "CAR_01",
  "boot_id": "B7A31F42",
  "session_id": "S82F19C4",
  "event_id": 51
}
```

처리:

```text
pending event_id 일치 확인
→ pendingArrival 해제
→ ARRIVED 재전송 중단
```

노트북이 동일 ARRIVED를 다시 받으면 waypoint 완료 처리를 반복하지 않고 EVENT_ACK만 다시 전송한다.

---

## 24. STATUS

STATUS는 다음 두 역할을 담당한다.

- 주기적인 차량 상태보고
- 신뢰성 명령의 처리 결과 응답

권장 형식:

```json
{
  "version": 1,
  "type": "STATUS",
  "car_id": "CAR_01",
  "boot_id": "B7A31F42",
  "session_id": "S82F19C4",
  "status_seq": 402,
  "last_processed_cmd_seq": 35,
  "state": "MOVING",
  "mode": "WAYPOINT_AUTO",
  "route_id": 8,
  "waypoint_id": 1,
  "phase": "CRUISE",
  "target_loaded": true,
  "x_cm": 50.2,
  "y_cm": 30.4,
  "heading_deg": 87.5,
  "latest_pose_seq": 5031,
  "pose_age_ms": 58,
  "encoder_speed_cm_s": 5.8,
  "encoder_distance_cm": 123.4,
  "wait_reason": "NONE",
  "error_code": "NONE",
  "last_completed_route_id": 7,
  "last_completed_waypoint_id": 4,
  "pending_event_id": 0
}
```

명령 처리 직후에는 `ack_seq`를 추가한 STATUS를 즉시 전송한다.

예시:

```text
WAIT seq=32
→ STATUS state=WAITING, ack_seq=32
```

주기 STATUS는 송신 Queue에 여러 개 누적하지 않는다. 최신 STATUS 하나만 유지한다.

---

## 25. COMMAND_RESULT 및 거절 사유

명령을 실행할 수 없으면 다음과 같이 응답한다.

```json
{
  "version": 1,
  "type": "COMMAND_RESULT",
  "car_id": "CAR_01",
  "session_id": "S82F19C4",
  "ack_seq": 36,
  "result": "REJECTED",
  "reason": "STALE_ROUTE",
  "state": "WAITING",
  "current_route_id": 8,
  "received_route_id": 7
}
```

초기 reason 후보:

- `INVALID_STATE`
- `INVALID_MODE`
- `INVALID_SESSION`
- `INVALID_SEQUENCE`
- `SEQ_CONFLICT`
- `STALE_ROUTE`
- `WAYPOINT_MISMATCH`
- `POSE_NOT_READY`
- `TARGET_NOT_LOADED`
- `FAULT_NOT_CLEARED`
- `INVALID_FIELD`
- `OUT_OF_RANGE`
- `PROTOCOL_ERROR`

잘못된 메시지 또는 필드가 차량 이동으로 이어져서는 안 된다.

---

## 26. 통신 단절 및 재접속

### 26.1 COMM_TIMEOUT

설정 시간 동안 유효한 HEARTBEAT 또는 링크 메시지가 없으면 다음과 같이 처리한다.

```text
안전정지
→ COMM_TIMEOUT
→ 자동 재출발 금지
```

COMM_TIMEOUT은 GO로 해제하지 않는다.

### 26.2 동일 boot_id 재접속

ESP32가 재부팅되지 않고 TCP 연결만 끊긴 경우이다.

```text
재접속
→ SYNCING
→ HELLO
→ pending ARRIVED 및 최근 완료 상태 확인
→ 기존 session 무효화
→ 기존 target 폐기
→ READY
→ 현재 카메라 Pose 기준 새 경로 생성
```

### 26.3 새로운 boot_id

ESP32가 실제로 재부팅된 경우이다.

기존 RAM 기반 정보를 신뢰하지 않는다.

```text
이전 target 폐기
→ waypoint buffer 폐기
→ 이전 pending event를 자동 복원하지 않음
→ 카메라로 실제 차량 위치와 정지 상태 확인
→ 새 session 생성
→ READY
→ 새 경로 생성
```

### 26.4 동일 car_id 중복 연결

새로운 정상 HELLO가 승인되면:

```text
새 session_id 발급
→ 새 소켓을 유효 연결로 지정
→ 기존 session 무효화
→ 기존 소켓 메시지 거절
```

재접속은 통신 복구이며 기존 주행 자동 재개를 의미하지 않는다.

---

## 27. 안전정지 추상화

모든 Task가 직접 PWM과 서보 출력을 변경하지 않는다.

차량 정지는 VehicleControlTask의 단일 인터페이스를 통해 수행한다.

```text
safeStop(reason)
```

정지 종류:

### WAIT·POSE_TIMEOUT

- 제어된 안전정지
- target 유지
- phase 유지
- WAITING 진입

### STOP·ERROR·COMM_TIMEOUT

- 가장 강한 검증된 안전정지
- target 폐기
- waypoint buffer 폐기
- 잠금 상태 진입
- 자동 재출발 금지

실제 MD10C에서 PWM 0이 관성정지인지 능동제동인지 하드웨어 테스트 후 `safeStop()` 내부 구현을 확정한다.

부팅 직후부터 모터 출력을 비활성화한다.

---

## 28. 초기 시험값

다음 값은 확정값이 아니라 최초 시험값이다.

| 항목 | 초기 후보 |
|---|---:|
| HEARTBEAT 주기 | 250 ms |
| COMM_TIMEOUT | 1,000 ms |
| POSE_UPDATE 주기 | 50~100 ms |
| POSE_TIMEOUT | 300~500 ms |
| STATUS 주기 | 100~200 ms |
| WAYPOINT 응답 timeout | 300 ms |
| WAIT 응답 timeout | 100 ms |
| STOP 응답 timeout | 50~100 ms |
| ARRIVED 재전송 주기 | 300 ms |
| HELLO 재전송 주기 | 500 ms |
| 최대 JSON 길이 | 512 byte |

최종 수치는 다음을 측정한 뒤 확정한다.

- Wi-Fi 지연
- 카메라 FPS
- YOLO 처리 지연
- 차량 속도
- 실제 제동거리
- Homography 오차
- heading 추정 오차

---

## 29. 핵심 설계 원칙

1. TCP 전달 성공과 애플리케이션 명령 실행 성공을 구분한다.
2. 일반 명령은 실제 상태 응답이 ACK 역할을 겸한다.
3. 상태 변경 명령은 멱등하게 처리한다.
4. 재전송은 기존 seq와 동일 payload를 사용한다.
5. 같은 seq에 다른 payload가 오면 SEQ_CONFLICT로 거절한다.
6. 일반 outstanding command는 차량당 하나만 허용한다.
7. WAIT와 STOP은 일반 명령을 선점할 수 있다.
8. WAIT는 target·route·phase를 보존한다.
9. STOP은 target과 waypoint buffer를 폐기한다.
10. 정지 명령은 넓게 허용하고 출발 명령은 엄격하게 검증한다.
11. ARRIVED는 EVENT_ACK를 받을 때까지 재전송한다.
12. POSE_UPDATE와 주기 STATUS는 최신값만 유지한다.
13. COMM_TIMEOUT과 POSE_TIMEOUT을 구분한다.
14. 통신 또는 Pose 복구 후 자동 재출발하지 않는다.
15. 재접속 후 기존 경로를 자동 재개하지 않는다.
16. boot_id로 TCP 재접속과 ESP32 재부팅을 구분한다.
17. 잘못된 JSON 또는 필드가 차량 이동으로 이어져서는 안 된다.
18. 차량 상태와 모터·서보 출력의 최종 권한은 VehicleControlTask 한 곳에서 관리한다.