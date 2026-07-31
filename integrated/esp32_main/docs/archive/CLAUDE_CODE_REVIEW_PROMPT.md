첨부한 아키텍처 문서를 기준으로 DAY3 ESP-IDF 코드를 리뷰해줘. 새로운 아키텍처나 추후 기능을 제안하지 말고 현재 범위의 실제 결함만 찾아라.

현재 범위:
- Wi-Fi, persistent TCP, NDJSON
- HELLO/HELLO_ACK
- WAYPOINT 저장
- GO만 MOVING 진입
- WAIT/STOP/RESET
- heartbeat timeout
- seq 중복/충돌 처리
- 상태머신
- safeStop mock actuator

추후 기능이 없다는 점은 결함이 아님:
- POSE_UPDATE, 실제 waypoint 추종, ARRIVED/PARKED
- 엔코더, 실제 PWM/서보, 재경로, 다중 차량, PASS 버퍼링

집중 검토:
- ESP-IDF v6.0.2 컴파일 호환성
- 버퍼 경계와 NDJSON framing
- socket lifetime/reconnect race
- mutex와 critical section
- STOP > WAIT
- Task Notification이 wake-up 용도로만 쓰이는지
- VehicleControlTask의 상태/출력 소유권
- TransmitTask의 socket send 소유권
- WAYPOINT가 MOVING을 만들지 않는지
- GO 조건
- FINAL_WAYPOINT_REACHED 후 동일 route 거절
- JSON 원문이 아닌 논리 payload fingerprint
- 동일 seq 재실행 금지
- ERROR가 COMM_TIMEOUT으로 덮이지 않는지
- 실제 액추에이터 출력이 완전히 비활성인지

출력:
| 심각도 | 파일:라인 | 문제 | 근거 | 최소 수정 |

마지막 판정은 하나만:
- BUILD-BLOCKED
- FIX-BEFORE-FLASH
- READY-FOR-MOCK-TEST
