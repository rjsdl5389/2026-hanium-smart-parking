# 시스템 아키텍처

## 1. 문서 목적

본 문서는 2026 한이음 공모전 프로젝트인 **자율주행 기반 지능형 주차 운영 시스템**의 전체 시스템 구조와 구성요소별 역할을 정의한다.

본 시스템은 고정 카메라와 노트북을 이용해 주차장 전체 상황을 관측하고, ESP32 기반 RC카가 전달받은 waypoint를 추종하도록 설계한다.

핵심 설계 원칙은 다음과 같다.

> 노트북은 전역 인식·주차면 배정·경로 생성·충돌 판단을 담당하고, ESP32는 실제 차량의 속도·조향 제어와 즉각적인 안전동작을 담당한다.

본 프로젝트에서는 Raspberry Pi를 사용하지 않는다. 카메라 영상 처리, AI 추론, 경로 생성, 관제 기능은 노트북이 담당하며 노트북과 ESP32는 Wi-Fi 기반 TCP 지속 연결로 통신한다.

---

## 2. 프로젝트 목표

본 프로젝트는 축소형 주차장 테스트베드에서 다음 과정을 통합 검증하는 것을 목표로 한다.

1. 고정 카메라로 차량과 주차면 상태를 인식한다.
2. 차량별로 사용 가능한 주차면을 배정한다.
3. 차량의 현재 위치에서 목표 주차면까지 이동 경로를 생성한다.
4. 경로를 waypoint 단위로 ESP32에 전달한다.
5. ESP32가 모터와 서보를 제어해 waypoint를 추종한다.
6. 주행 중 장애물 또는 차량 간 충돌 위험이 발생하면 즉시 정지한다.
7. 정지된 현재 위치를 기준으로 새로운 경로를 생성한다.
8. 최종 주차 결과를 카메라로 재검증하고 슬롯 상태를 갱신한다.

최종 시연에서는 단순 원격조종이 아니라 다음과 같은 **인프라 기반 협력형 자율주행 주차 시스템**을 구현한다.

- 고정 카메라 기반 전역 관측
- 동적 주차면 배정
- waypoint 기반 자율주행
- 장애물 발생 시 경로 재생성
- 다중 차량 충돌 방지 및 순차 제어

---

## 3. 전체 시스템 구성

전체 시스템은 다음 계층으로 구성한다.

```text
고정 카메라
    ↓
노트북 상위 제어 시스템
    ├─ YOLO 기반 차량·장애물·주차면 인식
    ├─ Homography 기반 픽셀 좌표 → 맵 좌표 변환
    ├─ 차량 위치·방향 추정
    ├─ 슬롯 상태관리
    ├─ PPO 기반 주차면 배정
    ├─ waypoint 경로 생성
    ├─ Safety Shield 기반 충돌 위험 판단
    ├─ Django·Redis 기반 상태관리
    └─ React 대시보드
    ↓ Wi-Fi / TCP / NDJSON
ESP32 하위 차량 제어 시스템
    ├─ 통신 메시지 수신·검증
    ├─ 차량 상태머신
    ├─ waypoint 추종
    ├─ 엔코더 속도·거리 피드백
    ├─ DC모터 PWM·방향 제어
    ├─ 서보 조향 제어
    └─ WAIT·STOP·timeout 안전동작
    ↓
MD10C 모터드라이버 + DC모터 + 조향 서보
    ↓
RC카 이동
    ↓
고정 카메라가 실제 위치 재관측
```

---

## 4. 구성요소별 역할

## 4.1 고정 카메라

고정 카메라는 주차장 테스트베드 전체를 관측한다.

주요 역할:

- 차량 위치 검출용 영상 제공
- 차량 전방 특징 검출용 영상 제공
- 주차 슬롯 상태 판단
- 장애물 및 다른 차량 관측
- 최종 주차 결과 검증

카메라는 차량에 탑재하지 않고 외부 인프라로 사용한다.

---

## 4.2 노트북 상위 제어 시스템

노트북은 영상 처리와 전역 의사결정을 담당한다.

| 구분 | 주요 기능 |
|---|---|
| 영상 입력 | 고정 카메라 프레임 수집 |
| 객체 인식 | YOLO 기반 차량, 전방 특징, 장애물 검출 |
| 좌표 변환 | Homography를 이용한 픽셀 좌표의 cm 단위 맵 좌표 변환 |
| 차량 상태 추정 | 차량 중심 위치, heading, tracking ID 관리 |
| 슬롯 상태관리 | EMPTY, RESERVED, OCCUPIED 등의 슬롯 상태 관리 |
| 주차면 배정 | PPO 기반 차량별 목표 주차면 선택 |
| 경로 생성 | 현재 위치에서 목표 주차면까지 waypoint 목록 생성 |
| 안전 판단 | 장애물 및 차량 간 충돌 위험 감지 |
| 명령 생성 | WAYPOINT, WAIT, GO, STOP, RESET 생성 |
| 상태관리 | Redis와 Django를 통한 차량·슬롯·경로 상태 저장 |
| 관제 UI | React 대시보드로 차량과 슬롯 상태 표시 |

노트북은 최종 자율주행 단계에서 모터 PWM과 서보값을 지속적으로 직접 전송하지 않는다.

노트북이 제공하는 핵심 정보는 다음 두 종류이다.

```text
현재 상태 정보
- POSE_UPDATE
- 차량의 현재 x, y, heading

목표 상태 정보
- WAYPOINT
- 목표 x, y, heading, 속도, phase, 허용오차
```

---

## 4.3 ESP32 하위 차량 제어 시스템

ESP32는 차량 한 대의 실제 움직임과 즉각적인 안전동작을 담당한다.

| 구분 | 주요 기능 |
|---|---|
| 통신 | Wi-Fi 연결 및 TCP 클라이언트 동작 |
| 메시지 처리 | NDJSON 분리, JSON 파싱, 필드·세션·순서 검증 |
| 상태머신 | READY, MOVING, WAITING, EMERGENCY_STOP 등 상태관리 |
| 목표 관리 | 현재 route, waypoint, phase 저장 |
| 위치 입력 | 최신 카메라 Pose 저장 |
| 속도 피드백 | 엔코더를 이용한 실제 속도와 이동거리 계산 |
| 차량 제어 | 위치·방향·속도 오차를 바탕으로 모터와 서보 제어 |
| 도착 판정 | waypoint 위치 및 heading 허용오차 확인 |
| 안전동작 | WAIT, STOP, COMM_TIMEOUT, POSE_TIMEOUT 처리 |
| 상태 전송 | STATUS, ARRIVED, ERROR 등 노트북으로 전송 |

모터 PWM과 서보 출력의 최종 권한은 ESP32의 VehicleControlTask 하나에 집중한다.

---

## 4.4 웹 및 상태관리 시스템

관제와 시스템 상태 공유를 위해 Django, Redis, React를 사용한다.

### Django

- 서버 API 제공
- 차량·슬롯·경로 데이터 관리
- TCP 차량 통신 모듈과 상위 로직 연결
- 대시보드 데이터 제공

### Redis

- 차량별 최신 상태 저장
- 슬롯 상태 공유
- 경로 및 이벤트 상태 공유
- Django 모듈 간 빠른 상태 전달

### React

- 주차장 맵 표시
- 차량 위치와 heading 표시
- 슬롯 EMPTY·RESERVED·OCCUPIED 상태 표시
- 현재 route와 waypoint 표시
- 차량 READY·MOVING·WAITING·ERROR 상태 표시
- 장애물 및 경로 재생성 상황 표시

브라우저와 Django는 HTTP 및 WebSocket을 사용하고, 노트북 차량 통신 모듈과 ESP32는 TCP를 사용한다.

---

## 5. 데이터 처리 흐름

## 5.1 차량 인식 흐름

```text
카메라 프레임 수집
→ YOLO로 RC_CAR 검출
→ 차량 bbox 중심 계산
→ FRONT_CUSHION 또는 보조 방법으로 전방점 계산
→ 차량 중심과 전방점을 Homography 변환
→ 맵 좌표 x_cm, y_cm, heading_deg 계산
→ 차량별 tracking 결과 갱신
```

차량 위치는 일반 YOLO bbox의 중심을 사용한다.

차량 방향은 차량 중심에서 전방 특징 중심으로 향하는 각도로 계산한다.

전방 특징 검출이 불안정한 경우 다음 보조 방식을 사용할 수 있다.

1. 최근 이동 궤적
2. 마지막 유효 heading
3. 향후 Keypoint 또는 OBB 기반 추정

후진 시 이동 방향과 차량 전방 방향이 반대이므로 최종 주차 단계에서는 전방 특징 기반 heading을 우선 사용한다.

---

## 5.2 주차면 배정 흐름

```text
차량 진입 감지
→ 현재 EMPTY 슬롯 확인
→ 슬롯 상태와 차량 조건 입력
→ PPO가 목표 슬롯 선택
→ 선택 슬롯을 RESERVED로 변경
→ 해당 슬롯 기준 경로 생성 요청
```

PPO의 역할은 **주차면 선택**이다.

PPO가 다음 기능을 직접 수행하지 않는다.

- 모터 PWM 생성
- 서보 조향값 생성
- waypoint 추종
- 장애물 충돌 회피 제어

차량 이동 경로는 별도의 경로 생성 모듈이 담당한다.

---

## 5.3 경로 생성 및 waypoint 전달 흐름

```text
현재 차량 Pose
+ 목표 주차 슬롯 정보
+ 맵과 장애물 정보
→ 전체 경로 생성
→ 경로를 waypoint 목록으로 변환
→ 노트북이 현재 waypoint 하나를 ESP32에 전송
→ ESP32가 waypoint 추종
→ ESP32가 ARRIVED 전송
→ 노트북이 다음 waypoint 전송
```

1차 구현에서는 waypoint를 한 개씩 순차 전송한다.

2차 구현에서는 현재 waypoint와 다음 waypoint 1~2개를 미리 전송해 연속 주행을 개선할 수 있다.

다음 상황에서는 기존 waypoint buffer를 전부 폐기한다.

- STOP
- COMM_TIMEOUT
- ERROR
- 재접속
- ESP32 재부팅
- 새로운 route_id 적용
- 경로 재생성

---

## 5.4 동적 경로 재생성 흐름

주행 중 장애물 또는 차량 간 충돌 위험이 감지되면 다음 절차를 사용한다.

```text
노트북이 위험 감지
→ WAIT 전송
→ ESP32 안전정지
→ WAITING 상태 확인
→ 노트북이 정지된 차량의 최신 Pose 확인
→ 기존 route 폐기
→ 새로운 route_id 발급
→ 새 waypoint 목록 생성
→ 첫 waypoint 전송
→ ESP32는 목표를 저장하되 WAITING 유지
→ 노트북이 GO 전송
→ ESP32가 MOVING으로 전환
```

정지된 차량이 정상 Pose를 다시 확보해도 자동으로 출발하지 않는다.

새로운 이동은 노트북의 명시적인 GO 또는 새 WAYPOINT 승인 절차 이후에만 허용한다.

---

## 6. 계층형 폐루프 제어

전체 시스템은 전역 제어 루프와 지역 제어 루프로 구성한다.

## 6.1 전역 제어 루프

노트북이 수행한다.

```text
실제 차량 이동
→ 카메라 재관측
→ 차량의 절대 위치·방향 갱신
→ 경로 및 충돌 상태 확인
→ 새 Pose 또는 명령 전송
```

전역 루프는 다음을 보정한다.

- 경로 이탈
- 차량 간 관계
- 장애물 발생
- 슬롯 상태 변화
- 엔코더 누적오차

---

## 6.2 지역 제어 루프

ESP32가 수행한다.

```text
최신 카메라 Pose
+ 현재 waypoint
+ 엔코더 속도·거리
→ 위치 오차 계산
→ heading 오차 계산
→ 목표 속도와 실제 속도 비교
→ 모터 PWM 결정
→ 서보 조향각 결정
```

ESP32는 카메라 프레임 사이에서도 엔코더를 이용해 빠른 속도 제어를 수행한다.

---

## 6.3 카메라와 엔코더의 역할

### 카메라

- 맵 전체 기준의 절대 위치 제공
- 차량 heading 제공
- 다른 차량·장애물·슬롯과의 관계 제공
- 엔코더 누적오차 보정 기준

### 엔코더

- 바퀴 회전 기반 속도 측정
- 이동거리 측정
- 목표 속도 유지
- 카메라 갱신 사이의 짧은 구간 보조

초기 구현에서는 카메라 Pose를 위치와 heading의 주 기준으로 사용하고, 엔코더는 속도 및 이동거리 보정에 우선 사용한다.

고도화 단계에서는 엔코더 이동거리와 조향각을 이용한 지역 odometry를 계산하고 새 카메라 Pose가 들어올 때 누적오차를 보정한다.

---

## 7. 차량 제어 모드

개발 및 최종 운용을 위해 다음 제어 모드를 구분한다.

| 모드 | 목적 | 입력 방식 |
|---|---|---|
| MANUAL_SERIAL | 기본 모터·서보 배선 및 동작 테스트 | 시리얼 문자 또는 값 입력 |
| REMOTE_DIRECT | Wi-Fi 기반 직접 속도·조향 테스트 | DIRECT_CONTROL |
| WAYPOINT_AUTO | 최종 자율주행 | POSE_UPDATE + WAYPOINT |

모드 변경 규칙:

- READY 및 모터 정지 상태에서만 변경
- MOVING 중 모드 변경 금지
- WAYPOINT_AUTO에서 DIRECT_CONTROL 거절
- REMOTE_DIRECT에서 WAYPOINT 거절
- STOP은 모든 모드에서 항상 허용

REMOTE_DIRECT는 통신과 차량 반응을 시험하기 위한 중간 개발 단계이며 최종 시연은 WAYPOINT_AUTO를 사용한다.

---

## 8. 차량 상태와 주차 phase

차량의 물리적 동작 상태와 주차 경로의 단계는 서로 분리해 관리한다.

## 8.1 차량 상태

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

## 8.2 주차 phase

```text
CRUISE
APPROACH
ALIGN
ENTRY
FINAL
```

예시:

```text
state = WAITING
phase = ALIGN
```

ALIGN 단계에서 충돌 위험으로 멈춘 경우 state만 WAITING으로 변경되고 phase는 ALIGN을 유지한다.

---

## 9. 주차 phase별 역할

| Phase | 목적 | 제어 특성 |
|---|---|---|
| CRUISE | 일반 통로 이동 | 비교적 높은 속도, 넓은 위치 허용오차 |
| APPROACH | 슬롯 인근 접근 | 감속, 정렬 공간 확보 |
| ALIGN | 슬롯 방향으로 차량 정렬 | 낮은 속도, heading 중요 |
| ENTRY | 슬롯 입구 통과 | 정렬 heading 유지, 낮은 속도 |
| FINAL | 슬롯 중심 및 최종 방향 맞춤 | 매우 낮은 속도, 위치와 heading 모두 확인 |

각 슬롯은 단순 중심점뿐 아니라 다음 정보를 포함한다.

```text
slot_id
center_x_cm
center_y_cm
target_heading_deg
width_cm
length_cm
entry_side
```

슬롯 정보를 기준으로 APPROACH, ALIGN, ENTRY, FINAL waypoint를 생성한다.

---

## 10. 도착 및 주차 완료 판정

ESP32의 waypoint 도착과 전체 시스템의 최종 주차 완료를 구분한다.

## 10.1 ARRIVED

ESP32가 현재 waypoint의 도착 여부를 판단한다.

위치만 필요한 waypoint:

```text
현재 위치와 목표 위치의 거리
≤ position_tolerance_cm
```

heading이 필요한 waypoint:

```text
위치 오차 조건 만족
AND
heading 오차 ≤ heading_tolerance_deg
```

도착 시 ESP32는 차량을 정지하고 ARRIVED 이벤트를 전송한다.

## 10.2 PARKED

최종 waypoint의 ARRIVED만으로 슬롯을 즉시 OCCUPIED로 변경하지 않는다.

노트북이 카메라로 다음을 재확인한다.

- 차량 중심이 슬롯 내부에 있는가
- 슬롯 중심과의 위치 오차가 허용범위 이내인가
- 차량 heading이 목표 방향과 일치하는가
- 차량이 실제로 정지했는가

조건을 만족하면 최종적으로 슬롯 상태를 OCCUPIED로 변경한다.

---

## 11. 통신 구조

노트북과 ESP32는 다음 방식으로 통신한다.

```text
노트북: TCP Server
ESP32: TCP Client
네트워크: Wi-Fi
메시지 형식: JSON
메시지 구분: 줄바꿈 문자 \n
전송 형식: NDJSON
```

주요 메시지:

### 노트북 → ESP32

- HELLO_ACK
- SET_MODE
- DIRECT_CONTROL
- POSE_UPDATE
- WAYPOINT
- WAIT
- GO
- STOP
- RESET
- HEARTBEAT
- EVENT_ACK

### ESP32 → 노트북

- HELLO
- STATUS
- COMMAND_RESULT
- ARRIVED
- ERROR 관련 상태

구체적인 필드, 재전송, 멱등성, timeout, 재접속 규칙은 `docs/communication_protocol.md`를 따른다.

---

## 12. 안전 설계

안전 관련 기본 원칙은 다음과 같다.

1. 차량 정지는 넓게 허용하고 출발은 엄격하게 검증한다.
2. STOP은 현재 route 및 waypoint와 무관하게 항상 적용한다.
3. WAIT는 현재 target과 phase를 유지한다.
4. STOP은 target과 waypoint buffer를 폐기한다.
5. COMM_TIMEOUT 발생 시 ESP32가 노트북 명령 없이 자체 정지한다.
6. POSE_TIMEOUT 발생 시 ESP32가 자체 정지하고 WAITING으로 전환한다.
7. 통신 또는 Pose가 복구돼도 자동 재출발하지 않는다.
8. 재접속 이후 기존 경로를 자동 재개하지 않는다.
9. ESP32 재부팅 이후 기존 target과 buffer를 신뢰하지 않는다.
10. 모든 모터와 서보 출력은 VehicleControlTask 하나가 최종 결정한다.
11. 부팅 직후와 Wi-Fi 연결 전에는 모터 출력을 비활성화한다.
12. 잘못된 JSON, 필드 누락, 범위 초과 값은 차량 동작으로 연결하지 않는다.

모든 안전정지는 공통 인터페이스를 사용한다.

```text
safeStop(reason)
```

실제 MD10C의 정지 동작이 관성정지인지 능동제동인지 하드웨어 테스트한 뒤 `safeStop()` 내부 구현을 확정한다.

---

## 13. 다중 차량 제어 구조

다중 차량 환경에서 노트북이 전체 차량을 통합 관리한다.

차량별 관리 항목:

- car_id
- tracking ID
- session_id
- 현재 Pose
- 현재 route_id
- 현재 waypoint_id
- 차량 state
- 주차 phase
- 배정 슬롯

다중 차량 제어 예시:

```text
CAR_01에 SLOT_01 배정
→ CAR_01 주행 시작

CAR_02에 SLOT_02 배정
→ 공용 구간 충돌 예상
→ CAR_02 WAIT

CAR_01이 공용 구간 통과
→ 안전 확인
→ CAR_02 GO
```

Safety Shield는 차량 간 예상 경로와 시간적 충돌을 확인하고 필요 시 차량별 WAIT와 GO를 결정한다.

---

## 14. 개발 단계

| 단계 | 주요 내용 | 목표 |
|---|---|---|
| 1 | 시리얼 기반 모터·서보 제어 | 배선, 방향, PWM, 조향 범위 확인 |
| 2 | Wi-Fi 기반 GO·WAIT·STOP·RESET | 통신과 안전 상태머신 확인 |
| 3 | speed·steering 직접 제어 | 네트워크 지연과 차량 반응 확인 |
| 4 | 카메라 Pose 기반 단일 waypoint | 위치·방향 오차 기반 이동과 ARRIVED 확인 |
| 5 | 엔코더 피드백 | 속도·거리 측정과 폐루프 속도 제어 |
| 6 | 카메라와 엔코더 비교 | 오차 분석과 경로 추종 보정 |
| 7 | 동적 장애물 재경로 | WAIT, 기존 경로 폐기, 새 route 생성 |
| 8 | 다중 차량 제어 | 차량 간 충돌 방지와 순차 주행 |
| 9 | waypoint 버퍼링 | 다음 waypoint 1~2개 선전송 및 연속 주행 |

---

## 15. 주요 기술 스택

| 영역 | 기술 |
|---|---|
| 영상 처리 | Python, OpenCV |
| 객체 인식 | YOLO |
| 좌표 변환 | Homography |
| 주차면 배정 | PPO |
| 경로 생성 | waypoint 기반 경로 생성, A* 계열 확장 가능 |
| 안전 판단 | Safety Shield, 충돌 위험 검사 |
| 상위 서버 | Django |
| 실시간 상태관리 | Redis |
| 대시보드 | React, WebSocket |
| 차량 통신 | Wi-Fi, TCP, NDJSON |
| 차량 제어 | ESP32, C/C++, FreeRTOS |
| 구동부 | MD10C, DC모터, 조향 서보, 엔코더 |

---

## 16. 설계 근거

본 구조를 선택한 이유는 다음과 같다.

- 영상 처리와 AI 추론은 노트북이 담당하는 것이 개발과 시연 안정성 측면에서 유리하다.
- ESP32는 PWM, 서보, 엔코더와 같은 실시간 하위 제어에 적합하다.
- 전역 경로 판단과 지역 차량 제어를 분리하면 각 모듈을 독립적으로 시험할 수 있다.
- waypoint 인터페이스를 사용하면 경로 생성 알고리즘과 하위 차량 제어기를 분리할 수 있다.
- 카메라 절대 위치와 엔코더 상대 이동량을 함께 사용하면 서로의 단점을 보완할 수 있다.
- TCP 세션, 상태머신, fail-safe를 적용하면 단순 RC카 시연이 아니라 실제 시스템에 가까운 구조를 제시할 수 있다.
- 고정 카메라를 활용한 중앙 관제 방식은 다중 차량과 슬롯 상태를 통합 관리하는 프로젝트 목표에 적합하다.

---

## 17. 관련 문서

- 통신 프로토콜: `docs/communication_protocol.md`
- 차량 상태머신: `docs/control_state_machine.md`
- FreeRTOS Task 구조: `docs/freertos_task_design.md`
- 상위 SW 연동 인터페이스: `docs/software_interface.md`
- 하드웨어 배선: `docs/hardware_wiring.md`
- 테스트 요약: `docs/test_log_summary.md`
- 개발 기록: `docs/development_log.md`
- 문제 해결 기록: `docs/troubleshooting.md`