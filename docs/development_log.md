# 개발 로그

## 1. 문서 목적

본 문서는 자율주행 기반 지능형 주차 운영 시스템의 일자별 개발 과정과 주요 의사결정을 기록한다.

각 기록은 다음 내용을 중심으로 작성한다.

- 수행한 작업
- 확인한 결과
- 발생한 문제
- 원인 분석
- 적용한 조치
- 확정된 설계
- 다음 작업

실제로 확인하지 않은 결과는 성공으로 기록하지 않는다.  
시험 전 항목은 `TBD`, 예정된 작업은 `예정`, 일부만 확인된 항목은 `부분 확인`으로 표시한다.

상세 시험값은 `docs/test_log_summary.md`, 반복 가능한 문제와 해결 절차는 `docs/troubleshooting.md`에 별도로 기록한다.

---

## 2026-07-02

### 수행한 작업

- 모터드라이버 전원 입력부와 배선 상태를 점검했다.
- DC-DC 강하 컨버터의 납땜 상태를 확인했다.
- DC모터 PWM 구동 테스트와 조향 서보 테스트를 준비했다.
- 기존 2채널 모터드라이버 MDD10A의 상태를 재점검했다.

### 발생한 문제

- 납땜을 보완한 뒤 멀티미터 테스트 과정에서 퓨즈가 다시 단선됐다.
- DC-DC 컨버터의 납땜부가 물리적으로 이탈했다.
- 기존 모터드라이버의 정상 동작을 신뢰하기 어려운 상태가 확인됐다.

### 원인 판단

- MDD10A 자체 고장 가능성이 높다고 판단했다.
- 모터 시동 시 순간전류와 불안정한 전원 접촉이 퓨즈 단선에 영향을 줬을 가능성이 있다.
- DC-DC 모듈 납땜부에 배선 장력이 직접 전달된 것으로 판단했다.

### 조치 및 결정

- 기존 MDD10A 대신 Cytron MD10C 1채널 모터드라이버를 사용하기로 결정했다.
- MD10C 도착 전 비교 및 임시 시험용으로 BTS7960 모터드라이버를 확보했다.
- 납땜부를 재보강하고 열수축튜브 또는 절연재와 케이블 고정을 함께 적용하기로 했다.
- 이후 모터 시험은 낮은 PWM부터 단계적으로 진행하기로 했다.

### 다음 작업

- 배터리부터 모터까지 전원 흐름을 단계별로 재측정한다.
- 퓨즈 홀더와 스위치의 연속성을 확인한다.
- MD10C 기준으로 모터 PWM·DIR 배선을 다시 구성한다.
- 서보 중앙값과 좌우 안전 한계값을 측정한다.
- 실제 시험 결과를 `docs/test_log_summary.md`에 기록한다.

---

## 2026-07-03

### 수행한 작업

- 프로젝트에서 Raspberry Pi를 계속 사용할 필요가 있는지 재검토했다.
- 카메라 위치, 차량 탑재 공간, 통신 구조와 상위 연산 위치를 기준으로 역할을 분석했다.
- 노트북과 ESP32만으로 전체 시스템을 구성하는 구조를 검토했다.

### 검토 결과

- 카메라는 차량 위가 아니라 고정된 외부 위치에 설치한다.
- 영상 인식, 슬롯 관리, 경로 생성과 대시보드는 노트북에서 처리할 수 있다.
- 차량에는 ESP32가 탑재되어 Wi-Fi로 제어 명령을 받을 수 있다.
- Raspberry Pi를 추가해도 차량 탑재 공간, 전원, 배선과 통신 구조만 복잡해지고 현재 시연 목표에서 필수 기능이 증가하지 않는다.

### 확정 결정

- 프로젝트에서 Raspberry Pi를 사용하지 않기로 결정했다.
- 노트북을 상위 제어기, ESP32를 차량 하위 제어기로 사용한다.
- 기존 Raspberry Pi–ESP32 UART/USB Serial 구조를 폐기한다.
- 최종 차량 통신은 노트북–ESP32 Wi-Fi 방식으로 구성한다.
- Raspberry Pi 관련 폴더와 UART 수신 테스트 구조를 저장소에서 제거하기로 했다.

### 다음 작업

- 시스템 아키텍처를 노트북–ESP32 구조로 다시 정의한다.
- Wi-Fi 기반 차량 제어 프로토콜을 설계한다.
- README와 시스템 문서에서 Raspberry Pi 관련 내용을 제거한다.

---

## 2026-07-06

### 수행한 작업

- MD10C 연결과 엔코더 활용 방향을 검토했다.
- DC-DC 강하 컨버터의 납땜부 절연 및 고정 방법을 정리했다.
- RC카 전체 제어 테스트 항목을 보수적인 순서로 재정리했다.
- DC모터 전원선과 모터드라이버 출력선의 접합 상태를 점검했다.

### 발생한 문제

- DC모터와 모터드라이버 연결선을 납땜했음에도 바퀴가 회전하지 않는 현상이 발생했다.
- 전류 전달이 원활하지 않거나 출력부 접촉이 불안정한 가능성이 제기됐다.

### 원인 확인 순서

```text
배터리 전압
→ 퓨즈 연속성
→ 메인 스위치 출력
→ MD10C 전원 입력
→ ESP32–MD10C 공통 GND
→ PWM·DIR 신호
→ MD10C 모터 출력
→ 모터 배선 납땜부
→ DC모터 단독 상태
```

### 조치 방향

- 코드 수정 전에 멀티미터로 전원 흐름과 연속성을 먼저 확인한다.
- 모터 출력선 접합부를 재납땜하고 물리적 장력을 제거한다.
- 납땜부는 열수축튜브를 우선 사용해 절연한다.
- DC-DC 모듈은 방열부를 완전히 감싸지 않고 납땜부 중심으로 절연한다.
- 바퀴를 공중에 띄운 상태에서 낮은 PWM부터 다시 시험한다.

### 다음 작업

- MD10C 단독 모터 구동을 확인한다.
- PWM sweep을 통해 최소 구동값을 측정한다.
- 엔코더 데이터시트와 출력전압을 확인한 뒤 ESP32 GPIO를 확정한다.

---

## 2026-07-14

### 수행한 작업

- 노트북 상위 제어기와 ESP32 하위 제어기의 역할을 최종 구분했다.
- Wi-Fi TCP 기반 차량 제어 프로토콜의 큰 틀을 확정했다.
- 차량 상태머신과 안전정지 정책을 확정했다.
- FreeRTOS Task·Queue·Notification 구조를 설계했다.
- 카메라 절대 위치와 엔코더 상대 이동 피드백을 결합하는 구조를 정리했다.
- SW팀에서 제공해야 할 차량 Pose, 슬롯, route, waypoint 인터페이스를 정의했다.
- 저장소 문서를 현재 설계에 맞춰 한글로 정리했다.

### 최종 시스템 역할

#### 노트북 상위 제어기

- 고정 카메라 영상 수집
- YOLO 차량 및 전방 특징 검출
- Homography 기반 cm 좌표 변환
- 차량 Pose 및 heading 계산
- 슬롯 상태관리
- PPO 기반 주차 슬롯 배정
- route 및 waypoint 생성
- Safety Shield 기반 충돌·장애물 판단
- WAIT·GO·STOP 결정
- 경로 재생성
- Django·Redis·React 기반 상태관리와 대시보드

#### ESP32 하위 제어기

- Wi-Fi TCP 연결
- 차량 명령 수신 및 검증
- 최신 카메라 Pose 저장
- waypoint 추종
- 모터 PWM 및 서보 조향 제어
- 엔코더 속도·거리 측정
- waypoint ARRIVED 판정
- WAIT·STOP 즉시 처리
- 통신·Pose timeout 안전정지
- 상태와 오류 피드백

### 통신 설계 확정

- 노트북을 TCP Server, ESP32를 TCP Client로 사용한다.
- JSON 메시지 끝에 줄바꿈을 추가하는 NDJSON 형식을 사용한다.
- 신뢰성 명령은 `seq`, 상태 ACK, 동일 seq 재전송과 멱등성을 적용한다.
- `POSE_UPDATE`, `STATUS`, `HEARTBEAT`는 최신값 중심으로 처리한다.
- `ARRIVED`는 `event_id`를 사용하고 `EVENT_ACK`까지 재전송한다.
- 재접속은 `session_id`, 재부팅은 `boot_id`로 구분한다.
- 일반 신뢰성 명령은 차량당 한 번에 하나만 응답 대기 상태로 둔다.
- STOP과 WAIT는 일반 명령을 선점할 수 있다.

### 차량 상태머신 확정

상태:

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

주요 원칙:

- READY에서 WAYPOINT를 받으면 MOVING으로 전환한다.
- MOVING에서 WAIT를 받으면 target과 phase를 유지하고 WAITING으로 전환한다.
- WAITING에서 새 WAYPOINT를 받으면 목표만 교체하고 GO 전까지 정지한다.
- STOP은 target과 waypoint buffer를 폐기하고 EMERGENCY_STOP으로 전환한다.
- GO는 복구 가능한 WAITING 상태에서만 허용한다.
- COMM_TIMEOUT, ERROR, EMERGENCY_STOP은 GO로 해제하지 않는다.
- 재접속 또는 재부팅 이후 기존 경로를 자동 재개하지 않는다.
- 모든 정지와 모터 출력은 VehicleControlTask의 `safeStop(reason)`에서 최종 처리한다.

### 위치 및 경로 인터페이스 확정

- 모든 제어 좌표는 Homography 이후 cm 단위를 사용한다.
- 차량 위치는 초기에는 `RC_CAR` bbox 중심으로 정의한다.
- 차량 heading은 차량 중심과 `FRONT_CUSHION` 중심의 방향으로 계산한다.
- 일반 bbox만으로 차량 회전각을 얻었다고 가정하지 않는다.
- 전체 waypoint 목록은 노트북이 보관한다.
- 초기에는 waypoint를 하나씩 순차 전송한다.
- 고도화 단계에서 다음 waypoint 1~2개를 버퍼링한다.
- 주행 phase는 `CRUISE`, `APPROACH`, `ALIGN`, `ENTRY`, `FINAL`로 구분한다.
- ESP32의 ARRIVED와 노트북의 최종 PARKED 판정을 구분한다.
- 장애물 또는 충돌 위험 발생 시 WAIT 후 현재 Pose에서 새 route를 생성한다.

### 카메라와 엔코더 결합 방향

초기 구현:

```text
카메라 Pose
→ 차량 x·y·heading의 주 기준

엔코더
→ 속도 폐루프 제어
→ 상대 이동거리와 정지거리 보조
```

고도화:

```text
이전 Pose
+ 엔코더 이동거리
+ 서보 조향각
→ 지역 odometry 예상값

새 카메라 Pose
→ 누적 오차 보정
```

처음부터 복잡한 센서 융합 필터를 적용하지 않고, 카메라 이동거리와 엔코더 이동거리 비교부터 진행한다.

### FreeRTOS 구조 확정

- `CommunicationTask`: TCP 수신, NDJSON 파싱, 검증과 메시지 분류
- `VehicleControlTask`: 상태머신, waypoint 추종, 모터·서보 출력의 유일한 소유자
- `SensorTask`: 엔코더 수집, 속도와 거리 계산
- `TransmitTask`: 메시지 우선순위 기반 송신
- `DiagnosticTask`: 낮은 우선순위의 설정과 로그

처리 방식:

- STOP·WAIT: Task Notification
- HEARTBEAT: CommunicationTask에서 즉시 처리
- POSE_UPDATE·DIRECT_CONTROL: 최신값 덮어쓰기
- WAYPOINT·GO·RESET: 일반 Command Queue
- 진단·설정: Low Queue
- 주기 STATUS: 최신값 하나만 유지

### 저장소 문서 업데이트

다음 문서를 현재 확정 설계에 맞게 작성 또는 수정했다.

- `docs/communication_protocol.md`
- `docs/system_architecture.md`
- `docs/control_state_machine.md`
- `README.md`
- `docs/freertos_task_design.md`
- `docs/software_interface.md`
- `docs/hardware_wiring.md`
- `docs/test_log_summary.md`

### 남은 미확정 항목

아래 값은 실제 테스트로 확정해야 한다.

- 엔코더 GPIO와 PPR/CPR
- 엔코더 출력전압 및 레벨 변환 필요 여부
- MD10C PWM 주파수
- 모터 최소·권장 PWM
- 서보 중앙값과 좌우 제한값
- MD10C의 관성정지·능동제동 특성
- WAIT와 STOP의 실제 정지거리
- HEARTBEAT·COMM_TIMEOUT 최종값
- POSE_UPDATE·POSE_TIMEOUT 최종값
- phase별 속도와 위치·heading 허용오차
- 카메라 Homography와 heading의 실제 측정오차

### 다음 작업

- `docs/troubleshooting.md`를 현재 하드웨어와 통신 구조에 맞게 업데이트한다.
- README의 상세 문서 링크와 현재 진행상태를 최종 확인한다.
- DAY 3 학습으로 엔코더, 속도·거리 환산, waypoint 추종과 조향 제어를 진행한다.
- MD10C와 서보의 실제 하드웨어 테스트를 낮은 출력부터 수행한다.
- Wi-Fi TCP 수신 테스트 코드와 ESP32 상태머신 기본 코드를 구현한다.

---

## 개발 로그 작성 양식

새 기록은 아래 양식을 복사해 사용한다.

```md
## YYYY-MM-DD

### 수행한 작업

- 

### 테스트 결과

| 테스트 항목 | 결과 | 비고 |
|---|---|---|
|  |  |  |

### 발생한 문제

- 

### 원인 분석

- 

### 조치

- 

### 확정 사항

- 

### 다음 작업

- 
```

---

## 주간 요약 양식

회의록 또는 주간보고를 작성할 때 아래 양식을 사용한다.

```md
## YYYY-MM-DD 주간 요약

### 완료

- 

### 진행 중

- 

### 주요 문제

- 

### 확정된 결정

- 

### 다음 주 계획

- 
```