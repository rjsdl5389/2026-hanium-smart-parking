# 테스트 로그 요약

## 1. 문서 목적

본 문서는 자율주행 기반 지능형 주차 운영 시스템의 하드웨어, 임베디드 펌웨어, 통신, 인식, 경로 추종 및 통합 시연 테스트 결과를 누적 관리하기 위한 문서이다.

상세한 일자별 작업 내용은 `docs/development_log.md`에 기록하고, 본 문서에는 다음 내용을 중심으로 정리한다.

- 테스트 목적
- 시험 조건
- 입력값과 설정값
- 기대 결과
- 실제 결과
- 합격 기준
- 발생 문제와 조치
- 다음 시험 항목
- 사진·영상·로그 등 증빙자료

확인하지 않은 결과를 성공으로 기록하지 않는다.  
실제 측정 전 값은 `TBD`, 예정된 시험은 `예정`, 일부만 확인된 시험은 `부분 확인`으로 표시한다.

---

## 2. 테스트 상태 정의

| 상태 | 의미 |
|---|---|
| 예정 | 아직 테스트하지 않음 |
| 진행 중 | 테스트를 수행 중이거나 결과 분석 중 |
| 부분 확인 | 일부 조건에서만 동작을 확인함 |
| 통과 | 정의된 합격 기준을 만족함 |
| 실패 | 기대 결과를 만족하지 못함 |
| 보류 | 부품 교체, 배선 수정 또는 선행 작업이 필요함 |
| 해당 없음 | 현재 설계에서 더 이상 사용하지 않는 항목 |

---

## 3. 전체 테스트 진행 현황

| 분류 | 테스트 항목 | 현재 상태 | 관련 코드 또는 문서 |
|---|---|---|---|
| 전원 | 배터리·퓨즈·스위치·분배 전압 확인 | 진행 중 | `docs/hardware_wiring.md` |
| 전원 | ESP32용 DC-DC 출력 안정성 | 예정 | `docs/hardware_wiring.md` |
| 전원 | 서보용 DC-DC 출력 안정성 | 예정 | `docs/hardware_wiring.md` |
| 모터 | MD10C 단독 모터 구동 | 예정 | `firmware_esp32/01_motor_basic_test/` |
| 모터 | PWM sweep 및 최소 구동값 측정 | 예정 | `firmware_esp32/04_pwm_sweep_test/` |
| 서보 | 중앙·좌·우 안전 범위 측정 | 예정 | `firmware_esp32/02_servo_steering_test/` |
| 통합 구동 | 모터와 서보 동시 제어 | 예정 | `firmware_esp32/03_drive_servo_integrated_test/` |
| 안전 | WAIT·STOP 실제 정지거리 | 예정 | `docs/control_state_machine.md` |
| 통신 | Wi-Fi TCP 연결 및 HELLO 동기화 | 예정 | `docs/communication_protocol.md` |
| 통신 | GO·WAIT·STOP·RESET 명령 | 예정 | `docs/communication_protocol.md` |
| 통신 | 명령 재전송·중복 방지·SEQ_CONFLICT | 예정 | `docs/communication_protocol.md` |
| 통신 | HEARTBEAT·COMM_TIMEOUT | 예정 | `docs/communication_protocol.md` |
| 인식 | 카메라 전체 맵 가시성 | 예정 | `docs/software_interface.md` |
| 인식 | Homography 좌표 오차 | 예정 | `docs/software_interface.md` |
| 인식 | 차량 bbox 중심 위치 추정 | 예정 | `docs/software_interface.md` |
| 인식 | FRONT_CUSHION 기반 heading | 예정 | `docs/software_interface.md` |
| 제어 | POSE_UPDATE 및 POSE_TIMEOUT | 예정 | `docs/communication_protocol.md` |
| 제어 | 단일 waypoint 추종 | 예정 | `docs/software_interface.md` |
| 제어 | 엔코더 속도·거리 측정 | 예정 | `docs/hardware_wiring.md` |
| 제어 | 카메라 Pose와 엔코더 비교 | 예정 | `docs/software_interface.md` |
| 경로 | 장애물 발생 시 WAIT·재경로·GO | 예정 | `docs/system_architecture.md` |
| 다중 차량 | 차량별 상태와 충돌 제어 | 예정 | `docs/system_architecture.md` |
| 최종 시연 | 슬롯 배정부터 주차 완료까지 | 예정 | `integrated/` |

---

# 4. 전원부 테스트

## 4.1 테스트 목적

차량 구동 전에 배터리, 퓨즈, 스위치, 전원 분배, DC-DC 컨버터의 전압과 연결 상태를 확인한다.

고전류 구동부 문제를 코드 문제로 오판하지 않도록 전원 흐름을 단계별로 검증한다.

## 4.2 전원 흐름 점검

점검 순서:

```text
배터리 출력
→ 퓨즈 양단
→ 메인 스위치 출력
→ 전원 분배 터미널
→ MD10C 전원 입력
→ ESP32용 DC-DC 입력과 출력
→ 서보용 DC-DC 입력과 출력
```

## 4.3 전원부 테스트 기록

| 날짜 | 측정 위치 | 기대값 | 측정값 | 부하 조건 | 결과 | 비고 |
|---|---|---:|---:|---|---|---|
| TBD | 배터리 출력 | 배터리 상태에 따른 3S 전압 | TBD | 무부하 | 예정 | 극성 포함 확인 |
| TBD | 퓨즈 출력 | 배터리 출력과 유사 | TBD | 무부하 | 예정 | 연속성 확인 |
| TBD | 메인 스위치 출력 | ON 시 배터리 전압 | TBD | 무부하 | 예정 | OFF 시 0V 확인 |
| TBD | MD10C 전원 입력 | 배터리 전압 | TBD | 무부하 | 예정 | 극성 확인 |
| TBD | ESP32용 DC-DC 출력 | 설정값 약 5V | TBD | ESP32 연결 전 | 예정 | 연결 전 필수 |
| TBD | ESP32용 DC-DC 출력 | 설정값 유지 | TBD | ESP32 부팅 중 | 예정 | 리셋 여부 확인 |
| TBD | 서보용 DC-DC 출력 | 서보 정격 설정값 | TBD | 무부하 | 예정 | 연결 전 필수 |
| TBD | 서보용 DC-DC 출력 | 설정값 유지 | TBD | 서보 조향 중 | 예정 | 전압강하 확인 |
| TBD | ESP32 전원 | 안정적 부팅 | TBD | 모터 시동 중 | 예정 | brownout 확인 |

## 4.4 합격 기준

- 극성이 모두 올바르다.
- 퓨즈와 스위치를 통과한 전압이 정상이다.
- ESP32용 출력이 허용범위를 벗어나지 않는다.
- 서보용 출력이 서보 정격범위를 벗어나지 않는다.
- 모터와 서보 동작 중 ESP32가 재부팅되지 않는다.
- 컨버터와 배선이 비정상적으로 과열되지 않는다.
- 노출된 납땜부나 도체 간 단락이 없다.

---

# 5. DC모터 및 MD10C 테스트

## 5.1 테스트 목적

MD10C와 DC모터의 정상 연결을 확인하고, 실제 차량이 움직이기 시작하는 최소 PWM과 안정적인 구동 PWM을 측정한다.

테스트는 다음 순서로 진행한다.

```text
바퀴를 공중에 띄운 상태
→ 저 PWM 회전 확인
→ PWM 단계 증가
→ 바닥 저속 직진
→ 하중 상태 안정성 확인
```

## 5.2 기본 연결 확인

| 날짜 | 항목 | 기대 결과 | 실제 결과 | 상태 | 비고 |
|---|---|---|---|---|---|
| TBD | MD10C 전원 입력 | 정상 배터리 전압 | TBD | 예정 | 극성 확인 |
| TBD | ESP32 GPIO 25 PWM | duty 변화 확인 | TBD | 예정 | 오실로스코프 또는 동작 확인 |
| TBD | ESP32 GPIO 26 DIR | 전진·후진 전환 | TBD | 예정 | 한쪽 기준으로 통일 |
| TBD | 공통 GND | 안정적 신호 전달 | TBD | 예정 | ESP32–MD10C |
| TBD | 모터 출력 배선 | 접촉 불량 없음 | TBD | 예정 | 연속성 확인 |

## 5.3 PWM sweep

| 날짜 | PWM 또는 Duty | 시험 조건 | 모터 반응 | 차량 이동 | 퓨즈 | 발열 | 결과 | 비고 |
|---|---:|---|---|---|---|---|---|---|
| TBD | 낮은 값 1 | 바퀴 공중 | TBD | 해당 없음 | TBD | TBD | 예정 | 시작값 |
| TBD | 낮은 값 2 | 바퀴 공중 | TBD | 해당 없음 | TBD | TBD | 예정 | 회전 시작 확인 |
| TBD | 중간 값 1 | 바퀴 공중 | TBD | 해당 없음 | TBD | TBD | 예정 | 안정 회전 |
| TBD | 중간 값 2 | 바닥 | TBD | TBD | TBD | TBD | 예정 | 최소 주행 후보 |
| TBD | 중간 값 3 | 바닥 | TBD | TBD | TBD | TBD | 예정 | 안정 주행 후보 |
| TBD | 높은 값 | 바닥 | TBD | TBD | TBD | TBD | 예정 | 필요 시 제한적으로 진행 |

처음부터 높은 PWM을 인가하지 않는다.  
실제 PWM 범위가 0~255인지 duty percentage인지 코드에서 명확하게 기록한다.

## 5.4 결과 요약

| 항목 | 최종 측정값 |
|---|---|
| 바퀴가 회전하기 시작한 최소 PWM | TBD |
| 바닥에서 차량이 움직이기 시작한 최소 PWM | TBD |
| 안정적인 직진 PWM | TBD |
| 후진 최소 PWM | TBD |
| 전진·후진 방향 논리 | TBD |
| 비정상 진동 또는 소음 발생 구간 | TBD |
| 권장 최대 시험 PWM | TBD |

---

# 6. 조향 서보 테스트

## 6.1 테스트 목적

조향 링크와 서보에 무리 없이 사용할 수 있는 중앙값, 최대 좌회전값, 최대 우회전값을 결정한다.

## 6.2 테스트 기록

| 날짜 | 명령 | PWM 또는 각도 | 바퀴 방향 | 기구 간섭 | 떨림·소음 | 전압강하 | 결과 | 비고 |
|---|---|---:|---|---|---|---|---|---|
| TBD | 중앙 | TBD | 중앙 | TBD | TBD | TBD | 예정 | 초기 기준 |
| TBD | 좌측 단계 1 | TBD | 좌 | TBD | TBD | TBD | 예정 | 작은 각도 |
| TBD | 좌측 최대 후보 | TBD | 좌 | TBD | TBD | TBD | 예정 | 안전 한계 |
| TBD | 우측 단계 1 | TBD | 우 | TBD | TBD | TBD | 예정 | 작은 각도 |
| TBD | 우측 최대 후보 | TBD | 우 | TBD | TBD | TBD | 예정 | 안전 한계 |
| TBD | 중앙 복귀 | TBD | 중앙 | TBD | TBD | TBD | 예정 | 복귀 오차 |

## 6.3 결과 요약

| 항목 | 최종 측정값 |
|---|---|
| 중앙값 | TBD |
| 최대 안전 좌회전값 | TBD |
| 최대 안전 우회전값 | TBD |
| 실사용 좌회전 제한값 | TBD |
| 실사용 우회전 제한값 | TBD |
| 좌우 비대칭 여부 | TBD |
| 중앙 복귀 오차 | TBD |

## 6.4 합격 기준

- 조향 링크가 차체나 바퀴와 충돌하지 않는다.
- 좌우 최대값에서 서보가 계속 힘을 주며 떨지 않는다.
- 중앙 명령 후 바퀴가 반복적으로 유사한 위치에 복귀한다.
- 서보 동작 중 ESP32 전원이 흔들리지 않는다.
- 전원선과 신호선이 조향 기구에 끼이지 않는다.

---

# 7. 모터·서보 통합 구동 테스트

## 7.1 테스트 목적

모터와 서보를 동시에 구동할 때 전원강하, 퓨즈 문제, 조향 저항 및 차량 움직임을 확인한다.

회전 주행은 직진보다 더 많은 토크가 필요할 수 있으므로 별도로 측정한다.

## 7.2 테스트 기록

| 날짜 | 조향 | 서보값 | 모터 PWM | 조건 | 실제 움직임 | ESP32 리셋 | 퓨즈 | 결과 | 비고 |
|---|---|---:|---:|---|---|---|---|---|---|
| TBD | 중앙 | TBD | TBD | 바퀴 공중 | TBD | 없음 / 발생 | TBD | 예정 | 기본 통합 |
| TBD | 중앙 | TBD | TBD | 바닥 | TBD | 없음 / 발생 | TBD | 예정 | 직진 |
| TBD | 좌측 | TBD | TBD | 바닥 | TBD | 없음 / 발생 | TBD | 예정 | 좌회전 |
| TBD | 우측 | TBD | TBD | 바닥 | TBD | 없음 / 발생 | TBD | 예정 | 우회전 |
| TBD | 중앙 복귀 | TBD | TBD | 이동 중 | TBD | 없음 / 발생 | TBD | 예정 | 조향 복귀 |
| TBD | 후진 | TBD | TBD | 바닥 | TBD | 없음 / 발생 | TBD | 예정 | 후진 조향 |

## 7.3 결과 요약

| 항목 | 최종 측정값 |
|---|---|
| 권장 직진 PWM | TBD |
| 권장 저속 회전 PWM | TBD |
| 최소 좌회전 PWM | TBD |
| 최소 우회전 PWM | TBD |
| 조향 중 전압강하 | TBD |
| 통합 동작 중 ESP32 리셋 여부 | TBD |

---

# 8. 안전정지 테스트

## 8.1 테스트 목적

`WAIT`, `STOP`, `POSE_TIMEOUT`, `COMM_TIMEOUT`, `ERROR` 발생 시 차량이 실제로 어떻게 정지하는지 확인하고 `safeStop(reason)`의 구현값을 결정한다.

## 8.2 정지 유형

| 정지 원인 | 목표 동작 |
|---|---|
| WAIT | 제어된 정지, target과 phase 유지 |
| POSE_TIMEOUT | 제어된 정지, WAITING 유지 |
| STOP | 가장 강한 검증된 정지, target과 buffer 폐기 |
| COMM_TIMEOUT | 즉시 안전정지, 자동 재출발 금지 |
| ERROR | 즉시 안전정지, 원인 제거 전 잠금 |

## 8.3 테스트 기록

| 날짜 | 정지 원인 | 시작 속도 | 정지 명령 방식 | 정지거리 | 정지시간 | target 유지 | 최종 상태 | 결과 |
|---|---|---:|---|---:|---:|---|---|---|
| TBD | WAIT | TBD | TBD | TBD | TBD | 예 | WAITING | 예정 |
| TBD | POSE_TIMEOUT | TBD | timeout | TBD | TBD | 예 | WAITING | 예정 |
| TBD | STOP | TBD | 원격 명령 | TBD | TBD | 아니오 | EMERGENCY_STOP | 예정 |
| TBD | COMM_TIMEOUT | TBD | heartbeat 차단 | TBD | TBD | 아니오 | COMM_TIMEOUT | 예정 |
| TBD | ERROR | TBD | 센서 오류 모의 | TBD | TBD | 아니오 | ERROR | 예정 |

## 8.4 확인 항목

- PWM 0이 관성정지인지 제동정지인지
- MD10C에서 더 강한 제동 방식이 가능한지
- 저속과 고속의 정지거리 차이
- WAIT 후 GO 시 기존 target을 정상적으로 재개하는지
- STOP 후 GO가 거절되는지
- STOP 후 RESET과 새 WAYPOINT가 필요한지
- 통신 복구 후 자동으로 움직이지 않는지

---

# 9. Wi-Fi TCP 연결 테스트

## 9.1 테스트 목적

노트북 TCP 서버와 ESP32 TCP 클라이언트 사이의 지속 연결, NDJSON 파싱 및 연결 동기화를 검증한다.

## 9.2 연결 및 파싱 테스트

| 날짜 | 테스트 | 입력 또는 조건 | 기대 결과 | 실제 결과 | 상태 | 비고 |
|---|---|---|---|---|---|---|
| TBD | Wi-Fi 연결 | 정상 AP | ESP32 연결 | TBD | 예정 | RSSI 기록 |
| TBD | TCP 연결 | 서버 실행 | 소켓 연결 | TBD | 예정 | 재시도 확인 |
| TBD | HELLO | TCP 연결 직후 | SYNCING 보고 | TBD | 예정 | boot_id 포함 |
| TBD | HELLO_ACK | 정상 차량 | session 발급 | TBD | 예정 | READY 전환 |
| TBD | 분할 JSON | 한 메시지를 여러 조각으로 전송 | 완전한 줄 수신 후 1회 파싱 | TBD | 예정 | NDJSON |
| TBD | 다중 JSON | 여러 줄을 한 번에 전송 | 각각 순서대로 파싱 | TBD | 예정 | receive buffer |
| TBD | 잘못된 JSON | 문법 오류 | 실행 금지 | TBD | 예정 | 오류 로그 |
| TBD | 512byte 초과 | 과대 메시지 | 폐기 또는 거절 | TBD | 예정 | 버퍼 보호 |
| TBD | car_id 불일치 | 다른 차량 ID | 거절 | TBD | 예정 | 소켓 종료 검토 |
| TBD | session 불일치 | 이전 session | 거절 | TBD | 예정 | 차량 동작 금지 |

## 9.3 연결 결과 요약

| 항목 | 결과 |
|---|---|
| 평균 연결 시간 | TBD |
| 평균 재접속 시간 | TBD |
| Wi-Fi RSSI | TBD |
| NDJSON 분할 수신 성공 여부 | TBD |
| 다중 메시지 연속 처리 성공 여부 | TBD |
| 최대 안정 메시지 크기 | TBD |

---

# 10. 명령 신뢰성 테스트

## 10.1 기본 명령 테스트

| 날짜 | 명령 | 시작 상태 | 기대 상태 | 실제 상태 | ack_seq | 결과 | 비고 |
|---|---|---|---|---|---:|---|---|
| TBD | SET_MODE | READY | 지정 모드 | TBD | TBD | 예정 | 정지 상태 |
| TBD | WAYPOINT | READY | MOVING | TBD | TBD | 예정 | target 로드 |
| TBD | WAIT | MOVING | WAITING | TBD | TBD | 예정 | target 유지 |
| TBD | GO | WAITING | MOVING | TBD | TBD | 예정 | 조건 검증 |
| TBD | STOP | MOVING | EMERGENCY_STOP | TBD | TBD | 예정 | target 폐기 |
| TBD | RESET | EMERGENCY_STOP | READY | TBD | TBD | 예정 | 자동 출발 금지 |

## 10.2 멱등성 및 재전송

| 날짜 | 테스트 | 입력 | 기대 결과 | 실제 결과 | 상태 |
|---|---|---|---|---|---|
| TBD | 동일 WAYPOINT 재전송 | 같은 seq·같은 payload | 중복 실행 없이 기존 결과 재응답 | TBD | 예정 |
| TBD | 동일 WAIT 재전송 | 같은 seq·같은 payload | WAITING 유지 | TBD | 예정 |
| TBD | 동일 STOP 재전송 | 같은 seq·같은 payload | E-STOP 유지 | TBD | 예정 |
| TBD | SEQ_CONFLICT | 같은 seq·다른 payload | 실행 금지 및 거절 | TBD | 예정 |
| TBD | 오래된 seq | 더 작은 seq | 상태 변경 금지 | TBD | 예정 |
| TBD | 응답 유실 | 첫 ACK 폐기 | 같은 seq 재전송 후 복구 | TBD | 예정 |
| TBD | WAIT 선점 | WAYPOINT ACK 대기 중 WAIT | 즉시 정지 후 상태 정리 | TBD | 예정 |
| TBD | STOP 선점 | 일반 명령 ACK 대기 중 STOP | 즉시 E-STOP, 이전 명령 취소 | TBD | 예정 |

---

# 11. HEARTBEAT 및 COMM_TIMEOUT 테스트

## 11.1 테스트 기록

| 날짜 | HEARTBEAT 주기 | timeout 설정 | 차단 방법 | 정지까지 시간 | 최종 상태 | 자동 재출발 | 결과 |
|---|---:|---:|---|---:|---|---|---|
| TBD | 250ms 후보 | 1000ms 후보 | 서버 송신 중지 | TBD | COMM_TIMEOUT | 금지 | 예정 |
| TBD | TBD | TBD | Wi-Fi 끊기 | TBD | COMM_TIMEOUT | 금지 | 예정 |
| TBD | TBD | TBD | TCP 소켓 종료 | TBD | COMM_TIMEOUT | 금지 | 예정 |

## 11.2 복구 테스트

```text
통신 단절
→ 차량 안전정지
→ TCP 재연결
→ HELLO
→ HELLO_ACK
→ 기존 target 폐기
→ READY
→ 새 WAYPOINT 필요
```

| 날짜 | 상황 | boot_id | 기대 결과 | 실제 결과 | 상태 |
|---|---|---|---|---|---|
| TBD | TCP만 재접속 | 동일 | 상태 동기화 후 READY | TBD | 예정 |
| TBD | ESP32 재부팅 | 변경 | 이전 RAM 상태 폐기 | TBD | 예정 |
| TBD | 같은 car_id 중복 연결 | 새 session | 기존 session 무효화 | TBD | 예정 |

---

# 12. 카메라 및 맵 인식 테스트

## 12.1 카메라 설치 테스트

| 날짜 | 고정 방식 | 높이 | 촬영 각도 | 해상도 | 전체 맵 가시성 | 반사·그림자 | FPS | 결과 |
|---|---|---:|---|---|---|---|---:|---|
| TBD | 배경지 거치대 + 클램프 | TBD | 하향 | TBD | TBD | TBD | TBD | 예정 |
| TBD | 위치 조정 후 | TBD | 하향 | TBD | TBD | TBD | TBD | 예정 |

확인 항목:

- 120cm × 120cm 맵 전체가 보이는가
- 네 모서리와 슬롯 경계가 식별 가능한가
- 차량이 맵 가장자리에 있어도 검출 가능한가
- 카메라 흔들림이 없는가
- 조명이 차량과 슬롯 인식에 방해되지 않는가
- 카메라 고정 위치가 반복 설치 후 유지되는가

## 12.2 Homography 좌표 오차

| 날짜 | 기준점 | 실제 x | 실제 y | 변환 x | 변환 y | 위치 오차 | 결과 |
|---|---|---:|---:|---:|---:|---:|---|
| TBD | 좌측 하단 | TBD | TBD | TBD | TBD | TBD | 예정 |
| TBD | 우측 하단 | TBD | TBD | TBD | TBD | TBD | 예정 |
| TBD | 좌측 상단 | TBD | TBD | TBD | TBD | TBD | 예정 |
| TBD | 우측 상단 | TBD | TBD | TBD | TBD | TBD | 예정 |
| TBD | 맵 중앙 | TBD | TBD | TBD | TBD | TBD | 예정 |
| TBD | 슬롯 중심 1 | TBD | TBD | TBD | TBD | TBD | 예정 |
| TBD | 슬롯 중심 2 | TBD | TBD | TBD | TBD | TBD | 예정 |

## 12.3 결과 요약

| 항목 | 최종 결과 |
|---|---|
| 평균 위치 오차 | TBD |
| 최대 위치 오차 | TBD |
| 맵 가장자리 최대 오차 | TBD |
| 재보정이 필요한 카메라 이동량 | TBD |
| 사용 가능한 카메라 해상도와 FPS | TBD |

---

# 13. 차량 Pose 및 Heading 테스트

## 13.1 bbox 중심 위치

| 날짜 | 차량 위치 | 실제 중심 좌표 | bbox 중심 변환 좌표 | 오차 | 결과 | 비고 |
|---|---|---|---|---:|---|---|
| TBD | 맵 중앙 | TBD | TBD | TBD | 예정 | 정면 방향 |
| TBD | 맵 좌측 | TBD | TBD | TBD | 예정 | 회전 상태 |
| TBD | 맵 우측 | TBD | TBD | TBD | 예정 | 회전 상태 |
| TBD | 슬롯 내부 | TBD | TBD | TBD | 예정 | 최종 위치 |

## 13.2 FRONT_CUSHION Heading

| 날짜 | 실제 방향 | 계산 heading | 각도 오차 | heading_source | confidence | 결과 |
|---|---:|---:|---:|---|---:|---|
| TBD | 0° | TBD | TBD | FRONT_CUSHION | TBD | 예정 |
| TBD | 90° | TBD | TBD | FRONT_CUSHION | TBD | 예정 |
| TBD | 180° | TBD | TBD | FRONT_CUSHION | TBD | 예정 |
| TBD | 270° | TBD | TBD | FRONT_CUSHION | TBD | 예정 |
| TBD | 임의 각도 1 | TBD | TBD | FRONT_CUSHION | TBD | 예정 |
| TBD | 임의 각도 2 | TBD | TBD | FRONT_CUSHION | TBD | 예정 |

## 13.3 Fallback 테스트

| 날짜 | 조건 | 기대 heading_source | 기대 동작 | 실제 결과 | 상태 |
|---|---|---|---|---|---|
| TBD | 전방 특징 1프레임 유실 | TRAJECTORY 또는 LAST_VALID | 짧게 유지 | TBD | 예정 |
| TBD | 정지 중 전방 특징 유실 | LAST_VALID | 기존 heading 유지 | TBD | 예정 |
| TBD | 후진 중 전방 특징 유실 | 궤적 단독 사용 금지 | WAIT 또는 낮은 신뢰도 | TBD | 예정 |
| TBD | 여러 차량 존재 | 올바른 association | 차량별 heading | TBD | 예정 |

---

# 14. POSE_UPDATE 및 POSE_TIMEOUT 테스트

## 14.1 POSE_UPDATE

| 날짜 | 전송 주기 | pose_seq 처리 | measurement_age | 실제 수신 주기 | 결과 | 비고 |
|---|---:|---|---:|---:|---|---|
| TBD | 100ms | 증가 | TBD | TBD | 예정 | 10Hz |
| TBD | 50ms | 증가 | TBD | TBD | 예정 | 20Hz |
| TBD | 순서 뒤바꿈 | 오래된 값 무시 | TBD | TBD | 예정 | stale pose |
| TBD | 같은 pose_seq | 중복 무시 | TBD | TBD | 예정 | duplicate |
| TBD | valid=false | 제어 미사용 | TBD | TBD | 예정 | 인식 실패 |

## 14.2 POSE_TIMEOUT

| 날짜 | 정상 주기 | timeout 설정 | Pose 차단 시간 | 정지까지 시간 | 최종 상태 | GO 전 자동 출발 | 결과 |
|---|---:|---:|---:|---:|---|---|---|
| TBD | 50~100ms | 300ms 후보 | TBD | TBD | WAITING | 금지 | 예정 |
| TBD | 50~100ms | 500ms 후보 | TBD | TBD | WAITING | 금지 | 예정 |

복구 확인:

```text
유효 Pose 재확보
→ WAITING 유지
→ 노트북 안전 확인
→ GO
→ MOVING
```

---

# 15. 엔코더 테스트

## 15.1 기본 펄스 확인

| 날짜 | 회전 조건 | Channel A | Channel B | 펄스 수 | 방향 판별 | 결과 | 비고 |
|---|---|---|---|---:|---|---|---|
| TBD | 바퀴 수동 1회전 | TBD | TBD | TBD | TBD | 예정 | 전원 OFF 구동 여부 확인 |
| TBD | 저속 전진 | TBD | TBD | TBD | 전진 | 예정 | 노이즈 확인 |
| TBD | 저속 후진 | TBD | TBD | TBD | 후진 | 예정 | A/B 위상 |
| TBD | 모터 정지 | TBD | TBD | 0 근처 | 해당 없음 | 예정 | 허위 펄스 확인 |

## 15.2 거리·속도 환산

| 날짜 | 실제 이동거리 | 엔코더 계산거리 | 오차 | 목표 속도 | 계산 속도 | 결과 |
|---|---:|---:|---:|---:|---:|---|
| TBD | 20cm | TBD | TBD | TBD | TBD | 예정 |
| TBD | 50cm | TBD | TBD | TBD | TBD | 예정 |
| TBD | 100cm | TBD | TBD | TBD | TBD | 예정 |

## 15.3 결과 요약

| 항목 | 최종 측정값 |
|---|---|
| 1회전당 펄스 수 | TBD |
| 바퀴 둘레 | TBD |
| 거리 환산계수 | TBD |
| 속도 계산 주기 | TBD |
| 저속 최소 검출 속도 | TBD |
| 전진·후진 방향 판별 성공 여부 | TBD |
| 노이즈 필터 필요 여부 | TBD |

---

# 16. 단일 Waypoint 추종 테스트

## 16.1 테스트 목적

노트북이 전달한 현재 Pose와 목표 waypoint를 이용하여 ESP32가 차량의 조향과 속도를 제어하고 ARRIVED를 발생시키는지 확인한다.

## 16.2 테스트 기록

| 날짜 | 시작 Pose | 목표 Pose | phase | 속도 | 위치 허용오차 | heading 조건 | 최종 오차 | ARRIVED | 결과 |
|---|---|---|---|---:|---:|---|---:|---|---|
| TBD | TBD | 직선 전방 | CRUISE | TBD | TBD | 없음 | TBD | TBD | 예정 |
| TBD | TBD | 좌측 목표 | CRUISE | TBD | TBD | 없음 | TBD | TBD | 예정 |
| TBD | TBD | 우측 목표 | CRUISE | TBD | TBD | 없음 | TBD | TBD | 예정 |
| TBD | TBD | 정렬 목표 | ALIGN | TBD | TBD | 있음 | TBD | TBD | 예정 |
| TBD | TBD | 최종 슬롯 중심 | FINAL | TBD | TBD | 있음 | TBD | TBD | 예정 |

## 16.3 확인 항목

- READY에서 WAYPOINT 수신 후 MOVING 전환
- 현재 Pose와 목표점의 거리 계산
- 목표 방향각 계산
- 원형 heading 오차 계산
- 좌·우 조향 방향
- 목표 근처 감속
- 위치 허용오차 적용
- heading_required 적용
- ARRIVED 후 정지
- 같은 ARRIVED를 중복 생성하지 않는지

---

# 17. ARRIVED 및 EVENT_ACK 테스트

| 날짜 | 테스트 | 기대 결과 | 실제 결과 | 상태 |
|---|---|---|---|---|
| TBD | 정상 ARRIVED | 노트북 처리 후 EVENT_ACK | TBD | 예정 |
| TBD | EVENT_ACK 유실 | 같은 event_id 재전송 | TBD | 예정 |
| TBD | ARRIVED 중복 수신 | 완료 처리 1회, ACK 재전송 | TBD | 예정 |
| TBD | ARRIVED 후 TCP 단절 | 재접속 후 pending event 복구 | TBD | 예정 |
| TBD | 이전 route ARRIVED | 현재 route 완료로 반영 금지 | TBD | 예정 |
| TBD | ESP32 재부팅 후 이벤트 | boot_id 변경으로 구분 | TBD | 예정 |

결과 요약:

| 항목 | 결과 |
|---|---|
| ARRIVED 재전송 주기 | TBD |
| 중복 이벤트 방지 성공 여부 | TBD |
| 재접속 후 pending event 복구 | TBD |
| 최종 waypoint와 중간 waypoint 구분 | TBD |

---

# 18. 카메라 Pose와 엔코더 비교 테스트

## 18.1 테스트 목적

카메라가 관측한 실제 이동거리와 엔코더가 계산한 상대 이동거리를 비교해 속도·거리 보정 기준을 정한다.

## 18.2 테스트 기록

| 날짜 | 구간 | 카메라 이동거리 | 엔코더 이동거리 | 차이 | 주행 방향 | 조향 상태 | 결과 |
|---|---|---:|---:|---:|---|---|---|
| TBD | 직선 20cm | TBD | TBD | TBD | 전진 | 중앙 | 예정 |
| TBD | 직선 50cm | TBD | TBD | TBD | 전진 | 중앙 | 예정 |
| TBD | 직선 20cm | TBD | TBD | TBD | 후진 | 중앙 | 예정 |
| TBD | 좌회전 구간 | TBD | TBD | TBD | 전진 | 좌 | 예정 |
| TBD | 우회전 구간 | TBD | TBD | TBD | 전진 | 우 | 예정 |

## 18.3 보정 검토

- 엔코더 환산계수를 즉시 변경하지 않고 반복 측정한다.
- 직진과 회전 구간을 분리한다.
- 바퀴 미끄러짐 여부를 기록한다.
- 배터리 전압과 바닥 재질을 함께 기록한다.
- 큰 불일치가 발생하면 센서 이상 또는 차량 정지를 고려한다.
- 복잡한 필터 적용 전 단순 오차 비교와 보정부터 수행한다.

---

# 19. 동적 장애물 및 재경로 테스트

## 19.1 테스트 시나리오

```text
초기 route 생성
→ 차량 주행 시작
→ 경로 위에 장애물 추가
→ 상위 시스템 위험 판단
→ WAIT
→ WAITING 확인
→ 최신 Pose에서 새 route 생성
→ 새 WAYPOINT 로드
→ GO
→ 새 경로 추종
```

## 19.2 테스트 기록

| 날짜 | 장애물 위치 | 위험 감지시간 | WAIT 응답시간 | 정지 성공 | 새 route_id | 기존 route 폐기 | GO 후 재주행 | 결과 |
|---|---|---:|---:|---|---:|---|---|---|
| TBD | 직선 경로 중앙 | TBD | TBD | TBD | TBD | TBD | TBD | 예정 |
| TBD | 슬롯 진입부 | TBD | TBD | TBD | TBD | TBD | TBD | 예정 |
| TBD | 차량 근처 갑작스러운 장애물 | TBD | TBD | TBD | TBD | TBD | TBD | 예정 |

## 19.3 합격 기준

- 충돌 전에 WAIT 명령이 전달된다.
- 차량이 WAITING 상태로 정지한다.
- 이전 target을 무작정 계속 추종하지 않는다.
- 새 경로에는 새로운 route_id가 사용된다.
- 이전 route의 늦은 메시지는 무시된다.
- 새 WAYPOINT 로드만으로 자동 출발하지 않는다.
- GO 후 새 경로를 정상 추종한다.

---

# 20. 다중 차량 제어 테스트

## 20.1 기본 시나리오

```text
CAR_01과 CAR_02 진입
→ 각 차량 식별
→ 서로 다른 슬롯 배정
→ 공용 구간 충돌 예상
→ 한 차량 WAIT
→ 우선 차량 통과
→ 대기 차량 GO
→ 순차 주차 완료
```

## 20.2 테스트 기록

| 날짜 | 시나리오 | 우선 차량 | 대기 차량 | 충돌 감지 | WAIT 성공 | GO 성공 | 슬롯 상태 | 결과 |
|---|---|---|---|---|---|---|---|---|
| TBD | 공용 통로 교차 | TBD | TBD | TBD | TBD | TBD | TBD | 예정 |
| TBD | 슬롯 진입구 중첩 | TBD | TBD | TBD | TBD | TBD | TBD | 예정 |
| TBD | 선행 차량 주차 후 후속 진입 | TBD | TBD | TBD | TBD | TBD | TBD | 예정 |

확인 항목:

- `car_id`와 영상 `tracking_id`가 올바르게 연결되는가
- 각 차량의 session과 route가 분리되는가
- 한 차량의 명령이 다른 차량에 적용되지 않는가
- 동일 car_id 중복 연결이 차단되는가
- 슬롯 RESERVED와 OCCUPIED가 정확히 갱신되는가

---

# 21. 최종 PARKED 판정 테스트

최종 waypoint ARRIVED 이후 노트북이 실제 주차 성공 여부를 재검증한다.

| 날짜 | 차량 | 슬롯 | 중심 오차 | heading 오차 | 정지 확인 | 슬롯 내부 | 안정 프레임 | PARKED | 결과 |
|---|---|---|---:|---:|---|---|---:|---|---|
| TBD | CAR_01 | SLOT_01 | TBD | TBD | TBD | TBD | TBD | TBD | 예정 |
| TBD | CAR_02 | SLOT_02 | TBD | TBD | TBD | TBD | TBD | TBD | 예정 |

PARKED 조건 후보:

```text
차량 중심이 슬롯 내부
AND
중심 오차가 허용범위 이내
AND
heading 오차가 허용범위 이내
AND
차량이 실제 정지
AND
일정 프레임 동안 결과 안정
```

검증 실패 시:

- 재정렬 waypoint 생성
- WAIT 상태 유지
- 운영자 확인

중 하나를 적용한다.

---

# 22. 문제 연계 기록

현재 확인된 문제 이력과 후속 검증 항목을 기록한다.

| 날짜 | 관련 테스트 | 문제 | 판단 원인 | 조치 | 현재 상태 | 관련 문서 |
|---|---|---|---|---|---|---|
| 2026-07-02 | 전원 및 모터 테스트 | 퓨즈 단선 반복 | 기존 모터드라이버 고장 가능성 | MDD10A 대신 MD10C 재구매, BTS7960 임시 확보 | 후속 테스트 필요 | `docs/troubleshooting.md` |
| 2026-07-02 | 전원 배선 점검 | DC-DC 컨버터 납땜부 이탈 | 납땜 강도 또는 물리적 장력 | 재납땜 및 절연·고정 보완 | 후속 전압 측정 필요 | `docs/troubleshooting.md` |
| 2026-07 | 모터 구동 점검 | 모터가 회전하지 않음 | 출력 배선 접촉 또는 전류 전달 문제 의심 | 연속성·MD10C 출력·모터 단독 점검 필요 | 원인 확인 필요 | `docs/troubleshooting.md` |

새 문제가 발생하면 다음 정보를 반드시 남긴다.

- 재현 조건
- 입력값
- 전압 또는 상태 로그
- 직전 정상 단계
- 변경한 항목
- 조치 전후 결과
- 사진 또는 영상 링크

---

# 23. 증빙자료 기록

대용량 영상은 GitHub 저장소에 직접 올리지 않고 Google Drive, YouTube 일부 공개, Notion 등의 링크를 기록한다.

| 날짜 | 자료 종류 | 설명 | 관련 테스트 | 링크 |
|---|---|---|---|---|
| TBD | 사진 | 전체 전원 배선 | 전원부 테스트 | TBD |
| TBD | 사진 | MD10C와 ESP32 배선 | 모터 테스트 | TBD |
| TBD | 영상 | DC모터 PWM sweep | 모터 테스트 | TBD |
| TBD | 영상 | 서보 좌·우·중앙 | 서보 테스트 | TBD |
| TBD | 영상 | 모터·서보 통합 주행 | 통합 구동 | TBD |
| TBD | 화면 녹화 | TCP 명령과 STATUS 로그 | 통신 테스트 | TBD |
| TBD | 화면 녹화 | Homography 좌표 표시 | 인식 테스트 | TBD |
| TBD | 영상 | 단일 waypoint 도착 | 제어 테스트 | TBD |
| TBD | 영상 | 장애물 추가 및 재경로 | 동적 경로 | TBD |
| TBD | 영상 | 차량 2대 순차 주차 | 최종 시연 | TBD |

---

# 24. 최종 시험값 요약

실제 테스트 후 채운다.

## 24.1 하드웨어

| 항목 | 최종값 |
|---|---|
| 배터리 운용 전압 범위 | TBD |
| 최종 퓨즈 정격 | TBD |
| ESP32용 DC-DC 출력 | TBD |
| 서보용 DC-DC 출력 | TBD |
| 최소 바닥 구동 PWM | TBD |
| 권장 직진 PWM | TBD |
| 권장 회전 PWM | TBD |
| 서보 중앙값 | TBD |
| 좌회전 제한값 | TBD |
| 우회전 제한값 | TBD |
| WAIT 정지거리 | TBD |
| STOP 정지거리 | TBD |

## 24.2 통신

| 항목 | 최종값 |
|---|---|
| HEARTBEAT 주기 | TBD |
| COMM_TIMEOUT | TBD |
| STATUS 주기 | TBD |
| WAIT 응답 timeout | TBD |
| STOP 응답 timeout | TBD |
| WAYPOINT 응답 timeout | TBD |
| ARRIVED 재전송 주기 | TBD |
| 최대 JSON 크기 | TBD |

## 24.3 인식 및 제어

| 항목 | 최종값 |
|---|---|
| 카메라 해상도 | TBD |
| 처리 FPS | TBD |
| POSE_UPDATE 주기 | TBD |
| POSE_TIMEOUT | TBD |
| 평균 Homography 위치 오차 | TBD |
| 평균 heading 오차 | TBD |
| CRUISE 위치 허용오차 | TBD |
| ALIGN 위치 허용오차 | TBD |
| FINAL 위치 허용오차 | TBD |
| FINAL heading 허용오차 | TBD |
| 엔코더 거리 환산계수 | TBD |

---

# 25. 일일 테스트 기록 형식

새 테스트를 수행할 때 다음 형식으로 기록한다.

```text
날짜:
테스트 항목:
목적:
하드웨어 구성:
펌웨어 또는 코드 버전:
입력값:
시험 조건:
기대 결과:
실제 결과:
측정값:
발생 문제:
조치:
최종 판단:
다음 작업:
증빙 링크:
```

하루 테스트가 끝나면 다음 문서를 함께 확인한다.

- `docs/test_log_summary.md`
- `docs/development_log.md`
- `docs/troubleshooting.md`
- `docs/hardware_wiring.md`
- 관련 펌웨어 폴더의 README 또는 소스코드

---

# 26. Notion 테스트 데이터베이스 권장 속성

| 속성명 | 형식 |
|---|---|
| 날짜 | Date |
| 분류 | Select |
| 테스트 항목 | Title |
| 차량 | Select |
| 펌웨어 버전 | Text |
| route_id | Number |
| waypoint_id | Number |
| PWM | Number |
| 서보값 | Number |
| 시험 조건 | Multi-select |
| 기대 결과 | Text |
| 실제 결과 | Text |
| 측정값 | Text |
| 퓨즈 상태 | Select |
| 상태 | Select |
| 문제 | Text |
| 조치 | Text |
| 증빙 링크 | URL |
| 다음 작업 | Text |

권장 분류:

```text
전원
모터
서보
통합 구동
안전정지
통신
카메라
Homography
Pose
엔코더
Waypoint
재경로
다중 차량
최종 시연
```

권장 상태:

```text
예정
진행 중
부분 확인
통과
실패
보류
해당 없음
```

---

# 27. 테스트 운영 원칙

1. 한 번에 여러 원인을 동시에 변경하지 않는다.
2. 첫 구동은 바퀴가 들린 상태와 낮은 PWM에서 시작한다.
3. 전압과 연속성을 확인하지 않고 코드만 수정하지 않는다.
4. 실제 확인하지 않은 결과를 성공으로 기록하지 않는다.
5. 테스트 조건과 입력값을 반드시 함께 기록한다.
6. 통신 성공과 차량 명령 실행 성공을 구분한다.
7. WAIT·STOP·timeout 테스트는 저속에서 먼저 수행한다.
8. 장애물 재경로 테스트 전에 단일 waypoint를 안정화한다.
9. 다중 차량 테스트 전에 차량 한 대의 전체 흐름을 완성한다.
10. 문제 발생 시 직전 정상 단계로 돌아가 원인을 분리한다.
11. 수치는 테스트 시작값과 최종 확정값을 구분한다.
12. 사진·영상·로그를 가능한 한 증빙자료로 남긴다.