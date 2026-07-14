# 상위 소프트웨어–ESP32 연동 인터페이스 설계

## 1. 문서 목적

본 문서는 노트북 기반 상위 소프트웨어와 ESP32 기반 RC카 하위 제어기 사이에서 공유해야 하는 데이터와 동작 규칙을 정의한다.

주요 목적은 다음과 같다.

- 카메라 인식 결과를 차량 제어 좌표로 변환하는 기준 통일
- 차량 위치와 진행 방향 표현 방식 정의
- 주차 슬롯과 경로 데이터 구조 정의
- waypoint 생성 결과와 ESP32 입력 형식 연결
- 장애물 및 다중 차량 충돌 발생 시 재경로 절차 정의
- ESP32의 ARRIVED와 상위 시스템의 PARKED 판정 구분
- AI·경로 생성·안전 판단·임베디드 제어 모듈 간 책임 분리

본 문서의 핵심 원칙은 다음과 같다.

> 상위 소프트웨어는 차량의 전역 위치를 관측하고 목표 경로를 생성하며, ESP32는 전달받은 현재 Pose와 waypoint를 이용해 실제 차량의 속도와 조향을 제어한다.

---

## 2. 전체 연동 구조

전체 데이터 흐름은 다음과 같다.

```text
고정 카메라
→ 영상 프레임 수집
→ YOLO 차량 및 전방 특징 검출
→ Homography 좌표 변환
→ 차량 Pose 생성
→ 슬롯 상태 및 주변 객체 상태 갱신
→ PPO 기반 주차 슬롯 배정
→ 경로 및 waypoint 생성
→ Safety Shield 검증
→ POSE_UPDATE와 WAYPOINT 전송
→ ESP32 waypoint 추종
→ STATUS와 ARRIVED 수신
→ 최종 주차 상태 검증
```

역할은 다음과 같이 구분한다.

### 상위 소프트웨어

- 차량 및 장애물 인식
- 맵 좌표 변환
- 차량 전역 Pose 계산
- 슬롯 상태관리
- 주차 슬롯 배정
- 전체 경로 생성
- waypoint 목록 생성
- 차량 간 충돌 위험 판단
- WAIT·GO·STOP 결정
- 경로 재생성
- 최종 PARKED 판정

### ESP32

- 최신 Pose 수신
- 현재 waypoint 저장
- 엔코더 기반 속도·거리 측정
- 위치 및 heading 오차 계산
- DC모터 PWM 제어
- 서보 조향 제어
- waypoint 도착 판정
- 즉시 안전정지
- 차량 상태와 ARRIVED 전송

---

## 3. 공통 좌표계

상위 소프트웨어와 ESP32는 동일한 실제 맵 좌표계를 사용한다.

권장 기준:

```text
좌측 하단 = (0, 0)
오른쪽 방향 = +x
위쪽 방향 = +y
거리 단위 = cm
각도 단위 = degree
```

120cm × 120cm 맵 예시:

```text
좌측 하단 = (0, 0)
우측 하단 = (120, 0)
좌측 상단 = (0, 120)
우측 상단 = (120, 120)
```

픽셀 좌표는 경로 생성이나 ESP32 제어에 직접 사용하지 않는다.

반드시 다음 과정을 거친다.

```text
영상 픽셀 좌표
→ Homography
→ 실제 맵 좌표 cm
```

모든 모듈은 다음 값을 동일한 의미로 사용해야 한다.

- `x_cm`
- `y_cm`
- `heading_deg`
- `target_heading_deg`
- `speed_cm_s`
- `position_tolerance_cm`
- `heading_tolerance_deg`

---

## 4. 차량 위치 산출

### 4.1 1차 차량 중심

차량 위치는 YOLO의 `RC_CAR` bounding box 중심으로 정의한다.

```text
cx_pixel = (x_min + x_max) / 2
cy_pixel = (y_min + y_max) / 2
```

이 중심점을 Homography로 변환한다.

```text
(cx_pixel, cy_pixel)
→ Homography
→ (x_cm, y_cm)
```

초기 구현에서는 이 값을 차량의 전역 중심점으로 사용한다.

### 4.2 중심 오차 보정

일반 bbox 중심과 실제 차량 기하학적 중심 사이에 일정한 편차가 확인되면 고정 offset을 적용할 수 있다.

```text
vehicle_x_cm = bbox_center_x_cm + offset_x_cm
vehicle_y_cm = bbox_center_y_cm + offset_y_cm
```

offset은 실제 맵 위에서 차량을 여러 방향으로 놓고 측정한 결과를 바탕으로 결정한다.

방향에 따라 오차가 크게 달라지면 단순 고정 offset보다 Keypoint 또는 OBB 기반 중심 추정을 검토한다.

---

## 5. 차량 Heading 산출

### 5.1 기본 원칙

일반 YOLO axis-aligned bbox만으로 차량의 회전각을 직접 얻을 수 없다.

따라서 초기 고도화 방식은 차량 앞쪽의 시각적 특징을 별도 객체로 검출하는 것이다.

권장 클래스:

```text
RC_CAR
FRONT_CUSHION
```

- `RC_CAR` bbox 중심: 차량 중심점
- `FRONT_CUSHION` bbox 중심: 차량 전방점

두 점을 각각 Homography로 변환한다.

```text
차량 중심 C = (x_c, y_c)
전방점 F = (x_f, y_f)
```

heading 계산:

```text
heading_deg = atan2(y_f - y_c, x_f - x_c)
```

### 5.2 각도 기준

```text
오른쪽 = 0°
위쪽 = 90°
왼쪽 = 180°
아래쪽 = 270°
```

각도는 `0° 이상 360° 미만`으로 정규화한다.

각도 오차는 원형 차이로 계산한다.

```text
현재 heading = 359°
목표 heading = 1°
실제 오차 = 2°
```

### 5.3 Heading Source

상위 소프트웨어는 heading 값과 함께 산출 출처를 관리한다.

권장 값:

```text
FRONT_CUSHION
KEYPOINT
OBB
TRAJECTORY
LAST_VALID
```

우선순위 예시:

```text
FRONT_CUSHION
→ KEYPOINT
→ OBB + 전방 특징
→ TRAJECTORY
→ LAST_VALID
```

### 5.4 이동 궤적 기반 fallback

전방 특징 검출이 실패한 경우 최근 차량 중심 이동 벡터를 이용할 수 있다.

```text
이전 중심점
→ 현재 중심점
→ 이동 방향 계산
```

단, 후진 시 차량 heading과 이동 방향이 반대이므로 후진 주차에서는 단독 기준으로 사용하지 않는다.

정지 상태에서는 최근 유효 heading을 유지한다.

---

## 6. 다중 차량 Association

차량이 여러 대일 경우 검출된 전방 특징을 올바른 차량과 연결해야 한다.

Association 판단 기준:

- 전방 특징 중심이 차량 bbox 내부 또는 인접 영역에 있는가
- 차량 중심과 전방 특징 중심의 거리가 충분히 가까운가
- Tracking ID가 이전 프레임과 일치하는가
- 이전 heading과 후보 heading의 차이가 급격하지 않은가
- 검출 confidence가 기준 이상인가
- 하나의 전방 특징이 여러 차량에 중복 할당되지 않았는가

권장 차량 추적 정보:

```text
car_id
tracking_id
last_x_cm
last_y_cm
last_heading_deg
last_seen_frame_id
position_confidence
heading_confidence
```

`tracking_id`는 영상 추적용 식별자이고, `car_id`는 실제 제어 대상 차량 식별자이다.

두 값을 혼동하지 않는다.

---

## 7. Vehicle Pose 데이터 구조

상위 소프트웨어 내부 권장 구조:

```json
{
  "car_id": "CAR_01",
  "frame_id": 8122,
  "pose_seq": 5021,
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

필드 의미:

| 필드 | 의미 |
|---|---|
| `car_id` | 실제 제어 차량 식별자 |
| `frame_id` | 원본 카메라 프레임 번호 |
| `pose_seq` | 차량별 Pose 생성 순서 |
| `x_cm` | Homography 변환 후 차량 중심 x |
| `y_cm` | Homography 변환 후 차량 중심 y |
| `heading_deg` | 차량 전방 방향 |
| `position_confidence` | 위치 신뢰도 |
| `heading_confidence` | heading 신뢰도 |
| `heading_source` | heading 산출 방식 |
| `measurement_age_ms` | 촬영 후 전송 시점까지 경과시간 |
| `valid` | 제어 사용 가능 여부 |

`valid=false` 후보:

- 차량 검출 실패
- Homography 실패
- 맵 범위 이탈
- 차량과 전방 특징 association 실패
- 위치 confidence 미달
- heading confidence 미달
- 비정상적인 위치 점프 검출

---

## 8. Homography 인터페이스

Homography 모듈 입력:

```text
카메라 픽셀 좌표 (u, v)
```

출력:

```text
맵 좌표 (x_cm, y_cm)
```

보정 데이터는 코드에 직접 하드코딩하지 않고 설정 파일로 관리하는 것을 권장한다.

예시:

```json
{
  "map_width_cm": 120.0,
  "map_height_cm": 120.0,
  "camera_resolution": [1920, 1080],
  "homography_matrix": [
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0]
  ]
}
```

실제 사용 시에는 캘리브레이션으로 계산한 행렬을 저장한다.

검증 항목:

- 맵 네 모서리 좌표 오차
- 맵 중앙 좌표 오차
- 슬롯 중심 좌표 오차
- 차량이 맵 가장자리로 이동했을 때 오차
- 카메라 또는 거치대 이동 후 재보정 필요 여부

---

## 9. 주차 슬롯 데이터 구조

주차 슬롯은 단순 중심점만으로 정의하지 않는다.

권장 구조:

```json
{
  "slot_id": "SLOT_01",
  "center_x_cm": 25.0,
  "center_y_cm": 100.0,
  "target_heading_deg": 90.0,
  "width_cm": 25.0,
  "length_cm": 40.0,
  "entry_side": "BOTTOM",
  "state": "EMPTY"
}
```

권장 상태:

```text
EMPTY
RESERVED
OCCUPIED
BLOCKED
```

의미:

- `EMPTY`: 배정 가능
- `RESERVED`: 특정 차량에 배정됨
- `OCCUPIED`: 차량 주차 완료
- `BLOCKED`: 장애물 또는 운영 조건으로 사용 불가

PPO는 슬롯 선택을 담당한다.

PPO가 직접 담당하지 않는 항목:

- 모터 PWM 계산
- 서보각 계산
- 차량 하위 제어
- waypoint 추종
- 즉시 안전정지

---

## 10. 경로 생성 입력

경로 생성 모듈은 최소한 다음 데이터를 입력받는다.

```text
현재 차량 Pose
배정된 주차 슬롯
맵 경계
주행 가능 영역
고정 장애물
동적 장애물
다른 차량의 현재 Pose
다른 차량의 예약 경로 또는 점유 구간
차량 크기
최소 회전반경
```

차량 모델에 필요한 주요 값:

```text
vehicle_length_cm
vehicle_width_cm
wheelbase_cm
minimum_turning_radius_cm
maximum_steering_deg
```

초기 경로 생성은 단순 waypoint 기반으로 구현한다.

필요 시 이후 확장:

```text
A*
→ smoothing
→ Hybrid A*
```

Hybrid A*는 초기 필수 기능으로 두지 않는다.

---

## 11. 경로 및 Waypoint 구조

전체 경로는 노트북이 보관한다.

```text
Route
├─ waypoint 1
├─ waypoint 2
├─ waypoint 3
└─ final waypoint
```

권장 route 구조:

```json
{
  "car_id": "CAR_01",
  "route_id": 8,
  "slot_id": "SLOT_01",
  "created_from_pose_seq": 5021,
  "waypoints": []
}
```

경로를 재생성할 때마다 새로운 `route_id`를 발급한다.

```text
기존 route_id = 7
장애물 또는 충돌 위험 발생
새 경로 생성
→ route_id = 8
```

이전 route의 늦은 명령이나 이벤트는 현재 제어에 반영하지 않는다.

---

## 12. Waypoint 데이터 구조

ESP32로 전달하는 waypoint 권장 형식:

```json
{
  "route_id": 8,
  "waypoint_id": 1,
  "phase": "CRUISE",
  "x_cm": 54.0,
  "y_cm": 30.0,
  "target_heading_deg": 0.0,
  "motion_direction": "FORWARD",
  "arrival_mode": "STOP",
  "speed_cm_s": 8.0,
  "position_tolerance_cm": 6.0,
  "heading_tolerance_deg": 15.0,
  "heading_required": false,
  "is_final": false
}
```

필드 의미:

| 필드 | 의미 |
|---|---|
| `route_id` | 경로 버전 |
| `waypoint_id` | 경로 내부 순서 |
| `phase` | 현재 주행 목적 |
| `x_cm`, `y_cm` | 목표 중심 좌표 |
| `target_heading_deg` | 목표 차량 방향 |
| `motion_direction` | 전진 또는 후진 |
| `arrival_mode` | 도착 시 정지 여부 |
| `speed_cm_s` | 목표 속도 |
| `position_tolerance_cm` | 위치 도착 허용오차 |
| `heading_tolerance_deg` | 방향 도착 허용오차 |
| `heading_required` | heading 조건 사용 여부 |
| `is_final` | 최종 주차 waypoint 여부 |

---

## 13. 주행 Phase

권장 phase:

```text
CRUISE
APPROACH
ALIGN
ENTRY
FINAL
```

### CRUISE

- 일반 통로 이동
- 상대적으로 높은 속도
- 위치 허용오차 비교적 큼
- heading 조건 선택적

### APPROACH

- 슬롯 주변으로 접근
- 감속 시작
- 정렬을 위한 공간 확보
- 슬롯 진입 방향 고려

### ALIGN

- 차량과 슬롯 방향 정렬
- 저속 운행
- heading 조건 중요
- 최소 회전반경 고려

### ENTRY

- 슬롯 입구를 통과
- 정렬된 heading 유지
- 낮은 속도
- 위치 오차를 더 엄격하게 적용

### FINAL

- 차량 중심과 슬롯 중심 최종 정렬
- 목표 heading 최종 확인
- 매우 낮은 속도
- 위치와 heading 조건 모두 만족해야 완료

차량 상태와 phase는 별도로 관리한다.

예시:

```text
vehicle_state = WAITING
phase = ALIGN
```

WAIT 후 GO를 받아도 phase는 ALIGN 상태를 유지한다.

---

## 14. Waypoint 전송 정책

### 14.1 1차 구현

waypoint 하나씩 순차 전송한다.

```text
노트북이 waypoint 1 전송
→ ESP32 추종
→ ARRIVED 수신
→ 노트북이 waypoint 2 전송
```

장점:

- 통신 검증이 단순함
- 도착 판정 검증이 쉬움
- 경로 취소와 재생성이 명확함
- 오래된 waypoint 처리 방어가 쉬움

### 14.2 2차 구현

현재 waypoint 외에 다음 waypoint 1~2개를 미리 버퍼링한다.

목적:

- 중간 waypoint마다 완전히 정지하는 문제 완화
- 더 부드러운 주행

버퍼링 시:

```text
일반 중간 waypoint = PASS
정렬 또는 최종 waypoint = STOP
```

다음 상황에서는 기존 buffer를 모두 폐기한다.

- WAIT 후 경로 재생성
- STOP
- COMM_TIMEOUT
- ERROR
- TCP 재접속
- ESP32 재부팅
- 새로운 route_id 적용

---

## 15. Safety Shield 인터페이스

Safety Shield는 PPO 또는 경로 생성 결과가 실제로 실행되기 전에 안전 여부를 검사한다.

입력 후보:

```text
현재 차량 Pose
현재 속도
현재 route
다음 waypoint
다른 차량 Pose
다른 차량 route
동적 장애물
맵 경계
슬롯 점유 상태
통신 상태
Pose freshness
```

출력 후보:

```text
GO_ALLOWED
WAIT_REQUIRED
STOP_REQUIRED
REROUTE_REQUIRED
```

권장 결과 구조:

```json
{
  "car_id": "CAR_01",
  "decision": "WAIT_REQUIRED",
  "reason": "COLLISION_RISK",
  "conflict_object_id": "CAR_02",
  "route_id": 8
}
```

Safety Shield는 차량의 PWM을 직접 계산하지 않는다.

결과는 통신 관리자와 경로 관리자에게 전달되어 다음 명령으로 변환된다.

```text
WAIT_REQUIRED
→ WAIT

STOP_REQUIRED
→ STOP

REROUTE_REQUIRED
→ WAIT
→ 경로 재생성
→ 새 WAYPOINT
→ GO
```

---

## 16. 장애물 및 충돌 위험 발생 시 절차

동적 장애물 또는 다중 차량 충돌 위험 발생 시 다음 절차를 사용한다.

```text
1. 상위 소프트웨어가 위험 감지
2. 해당 차량에 WAIT 전송
3. ESP32가 안전정지 후 WAITING 전송
4. 상위 소프트웨어가 정지된 최신 Pose 확인
5. 기존 route 폐기
6. 새로운 route_id 발급
7. 새 경로와 waypoint 목록 생성
8. 새 첫 waypoint 전송
9. ESP32는 목표를 저장하고 WAITING 유지
10. Safety Shield가 재출발 가능 여부 확인
11. GO 전송
12. ESP32가 MOVING으로 전환
```

중요 원칙:

- 새 waypoint를 받았다는 이유만으로 자동 출발하지 않는다.
- 기존 route의 늦은 ARRIVED를 현재 route 완료로 처리하지 않는다.
- 현재 카메라 Pose에서 새 경로를 생성한다.
- WAIT는 기존 target을 유지하지만, 새 route가 생성되면 이전 target은 교체한다.

---

## 17. 다중 차량 제어

노트북은 차량별 상태를 독립적으로 관리한다.

권장 관리 정보:

```text
car_id
session_id
tracking_id
vehicle_state
current_pose
current_route_id
current_waypoint_id
assigned_slot_id
pending_command
last_status
```

다중 차량 충돌 판단 기준 예시:

- 같은 공용 구간을 동시에 점유할 가능성
- 경로 선분 간 시간적 충돌
- 차량 중심 간 최소 안전거리
- 슬롯 진입 구간 중첩
- 정지 차량 주변 통과 가능 여부

충돌 위험이 있으면 한 차량을 WAIT시키고 다른 차량을 우선 통과시킨다.

예시:

```text
CAR_01 공용 구간 진입 중
CAR_02 공용 구간 진입 예정
→ CAR_02 WAIT
→ CAR_01 통과 확인
→ CAR_02 GO
```

우선순위 결정 기준은 초기에는 규칙 기반으로 구현한다.

예:

- 이미 공용 구간에 진입한 차량 우선
- 최종 주차 단계 차량 우선
- 정지거리 내 차량 우선
- 동일 조건이면 먼저 예약된 차량 우선

---

## 18. ARRIVED와 PARKED 구분

### ARRIVED

ESP32가 현재 waypoint에 도착했다고 판단한 이벤트이다.

판정 기준:

```text
위치 오차 ≤ position_tolerance_cm
```

`heading_required=true`인 경우:

```text
위치 오차 만족
AND
heading 오차 만족
```

### PARKED

상위 소프트웨어가 최종 주차 성공을 확인한 시스템 상태이다.

최종 waypoint ARRIVED를 수신했다고 즉시 슬롯을 OCCUPIED로 바꾸지 않는다.

상위 소프트웨어가 다음을 재검증한다.

- 차량 중심이 슬롯 내부에 있는가
- 슬롯 중심과 차량 중심의 거리가 허용범위 이내인가
- 차량 heading이 목표와 일치하는가
- 차량이 실제로 정지했는가
- 인식 결과가 일정 프레임 동안 안정적인가

확인 후:

```text
slot_state = OCCUPIED
vehicle_parking_state = PARKED
```

최종 검증 실패 시:

```text
재정렬 waypoint 생성
또는
WAIT 상태 유지 후 운영자 확인
```

---

## 19. 데이터 Freshness 기준

상위 소프트웨어는 데이터의 생성 시점과 수신 시점을 구분해 관리한다.

권장 항목:

```text
frame_capture_time
pose_generated_time
message_sent_time
message_received_time
measurement_age_ms
```

ESP32에 절대 시각 동기화를 요구하지 않고, `measurement_age_ms`를 전달한다.

초기 후보:

```text
POSE_UPDATE 목표 주기 = 50~100ms
POSE_TIMEOUT = 300~500ms
```

최종 수치는 실제 카메라 FPS, YOLO 처리시간, Wi-Fi 지연, 차량 속도와 제동거리를 측정한 뒤 확정한다.

오래된 Pose는 confidence가 높더라도 제어에 사용하지 않는다.

---

## 20. Confidence 처리 기준

초기에는 다음 값을 별도로 관리한다.

```text
position_confidence
heading_confidence
```

권장 처리 원칙:

- 위치는 유효하지만 heading이 불확실한 경우 phase에 따라 다르게 처리
- CRUISE에서는 짧은 시간 LAST_VALID heading 사용 가능
- ALIGN·ENTRY·FINAL에서는 heading 신뢰도가 낮으면 WAIT 권장
- position confidence가 기준 이하이면 해당 Pose를 invalid 처리
- 비정상적인 좌표 점프가 있으면 한 프레임 값을 즉시 신뢰하지 않음

실제 threshold는 실험 후 결정한다.

---

## 21. 상위 소프트웨어 모듈 권장 구조

권장 최상위 폴더:

```text
laptop_controller/
├─ perception/
│  ├─ detector
│  ├─ tracker
│  ├─ pose_estimator
│  └─ homography
├─ parking/
│  ├─ slot_manager
│  └─ slot_allocator
├─ planning/
│  ├─ route_planner
│  ├─ waypoint_generator
│  └─ route_manager
├─ safety/
│  ├─ collision_checker
│  └─ safety_shield
├─ communication/
│  ├─ tcp_server
│  ├─ session_manager
│  ├─ command_manager
│  └─ message_codec
├─ state/
│  ├─ vehicle_registry
│  └─ event_store
└─ config/
```

초기에는 모든 폴더를 미리 만들 필요는 없다.

실제 코드가 추가되는 시점에 기능별로 생성한다.

---

## 22. Redis·Django·React 연동 원칙

### Redis

실시간 상태 공유와 최신값 저장에 사용한다.

예시 키:

```text
vehicle:CAR_01:pose
vehicle:CAR_01:status
vehicle:CAR_01:route
slot:SLOT_01:state
```

POSE와 STATUS는 최신값 중심으로 저장한다.

### Django

- 차량 및 슬롯 관리 API
- 경로 및 이벤트 기록
- 운영 명령 처리
- 대시보드 데이터 제공

### React

- 맵 표시
- 차량 위치와 heading 표시
- waypoint 및 route 표시
- 슬롯 상태 표시
- WAIT·STOP·오류 표시
- 운영자 명령 UI

브라우저와 Django 사이에는 HTTP와 WebSocket을 사용할 수 있다.

브라우저가 ESP32에 직접 명령을 보내지 않는다.

```text
React
→ Django
→ 상위 제어 로직 검증
→ TCP Command Manager
→ ESP32
```

---

## 23. ID 생성 책임

| ID | 생성 주체 |
|---|---|
| `car_id` | 시스템 설정 |
| `tracking_id` | 영상 추적 모듈 |
| `frame_id` | 카메라 또는 프레임 처리 모듈 |
| `pose_seq` | 차량 Pose 관리자 |
| `session_id` | 노트북 TCP Session Manager |
| `seq` | 노트북 Command Manager |
| `route_id` | Route Manager |
| `waypoint_id` | Waypoint Generator |
| `event_id` | ESP32 |
| `status_seq` | ESP32 |

한 ID를 여러 모듈이 독립적으로 생성하지 않는다.

특히 `seq`는 차량별 Command Manager 한 곳에서만 발급한다.

---

## 24. 상위 소프트웨어 검증 규칙

ESP32로 메시지를 전송하기 전에 다음을 검증한다.

### POSE_UPDATE

- car_id가 등록된 차량인가
- 좌표가 맵 범위 내부인가
- pose_seq가 이전 값보다 새로운가
- measurement_age_ms가 허용범위 이내인가
- position confidence가 기준 이상인가
- heading 값이 정상 범위인가
- valid 값과 필드 상태가 일치하는가

### WAYPOINT

- 현재 차량 session이 유효한가
- route_id가 현재 활성 route인가
- waypoint_id가 올바른 순서인가
- 좌표가 주행 가능 영역 안에 있는가
- speed 값이 phase별 허용범위 안에 있는가
- tolerance 값이 양수인가
- motion_direction이 차량 경로와 일치하는가
- Safety Shield 검증을 통과했는가

### GO

- 차량이 WAITING인가
- target이 로드되어 있는가
- route_id와 waypoint_id가 현재 target과 일치하는가
- Pose가 유효하고 신선한가
- 충돌 위험이 해소됐는가
- ERROR·E-STOP·COMM_TIMEOUT 상태가 아닌가

---

## 25. 통합 테스트 항목

### Pose 인터페이스

- bbox 중심이 실제 차량 중심과 얼마나 차이 나는가
- Homography 변환 좌표 오차
- heading 오차
- FRONT_CUSHION 검출 실패 시 fallback
- 정지 차량의 heading 유지
- 후진 시 trajectory heading 오류 방지
- 다중 차량 association

### Waypoint 인터페이스

- 단일 waypoint 생성
- phase별 속도와 tolerance
- route_id 증가
- waypoint_id 순서
- WAITING 중 새 waypoint 교체
- 오래된 route 명령 거절
- 최종 waypoint heading 조건

### Safety 인터페이스

- 장애물 추가 시 WAIT
- 차량 충돌 예상 시 한 차량 WAIT
- 위험 해소 후 GO
- 경로 재생성 시 기존 route 폐기
- STOP 후 새 경로 생성

### 최종 주차 검증

- 최종 ARRIVED 수신
- 슬롯 내부 여부 확인
- 중심 오차 확인
- heading 오차 확인
- 정지 상태 확인
- OCCUPIED 상태 변경

---

## 26. 구현 단계

### 1단계

- 단일 차량 bbox 중심 추출
- Homography로 cm 좌표 변환
- 대시보드에 차량 중심 표시

### 2단계

- 차량 전방 특징 검출
- heading 계산
- confidence와 heading_source 관리

### 3단계

- 단일 슬롯과 단일 waypoint 생성
- POSE_UPDATE와 WAYPOINT 전송
- ARRIVED 수신

### 4단계

- phase 기반 waypoint 생성
- APPROACH·ALIGN·ENTRY·FINAL 적용
- 최종 PARKED 검증

### 5단계

- 장애물 인식
- WAIT
- route_id 증가
- 새 경로 생성
- GO

### 6단계

- 차량 2대 tracking
- 차량별 Pose 및 route 관리
- 공용 구간 충돌 판단
- 차량별 WAIT·GO

### 7단계

- waypoint 1~2개 버퍼링
- PASS·STOP 구분
- 연속 주행 최적화

---

## 27. 최종 설계 원칙

1. 픽셀 좌표를 ESP32 제어 좌표로 직접 사용하지 않는다.
2. 모든 제어 좌표는 Homography 이후 cm 단위를 사용한다.
3. 차량 위치는 초기에는 RC_CAR bbox 중심으로 정의한다.
4. 차량 heading은 차량 중심과 전방 특징의 방향으로 계산한다.
5. 일반 bbox만으로 차량 회전각을 얻었다고 가정하지 않는다.
6. 후진 주차에서는 이동 궤적만으로 heading을 판단하지 않는다.
7. PPO는 슬롯 배정을 담당하고 하위 차량 제어를 담당하지 않는다.
8. 전체 route는 노트북이 보관하고 ESP32에는 현재 waypoint를 순차 전송한다.
9. route를 재생성할 때마다 route_id를 변경한다.
10. 주행 상태와 parking phase를 별도로 관리한다.
11. Safety Shield 검증 후에만 movement 명령을 전송한다.
12. 장애물 또는 충돌 위험 시 WAIT 후 현재 Pose에서 경로를 다시 생성한다.
13. 새 waypoint를 로드해도 GO 전까지 자동 출발하지 않는다.
14. ARRIVED는 현재 waypoint 완료이고 PARKED는 최종 주차 검증 결과이다.
15. 최종 PARKED는 노트북이 카메라로 재확인한다.
16. 데이터 confidence뿐 아니라 freshness도 함께 검증한다.
17. 브라우저는 ESP32에 직접 명령을 보내지 않는다.
18. 각 식별자는 지정된 단일 모듈에서만 생성한다.