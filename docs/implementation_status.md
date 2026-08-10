# 구현 상태 단일 기준

기준일: **2026-08-10**
기준 통합 경로: **AUTO_HOST + REMOTE_DIRECT**

이 문서는 현재 저장소 구현 상태를 판정하는 단일 기준이다.

## 완료

### 노트북/ESP32 통신

- Wi-Fi TCP 지속 연결 및 재연결
- NDJSON framing
- HELLO / HELLO_ACK
- boot_id / session 동기화
- HEARTBEAT / COMM_TIMEOUT
- STATUS 피드백
- SET_MODE(REMOTE_DIRECT)
- DIRECT_CONTROL 스트리밍
- 통신단절 안전정지

### 실제 차량 수동제어

- READY 직후 MANUAL_WASD shell 생성
- W 전진
- S 후진
- A/D 좌우 조향
- STOP/HOLD
- 입력 해제 시 throttle=0, steering=0
- 수동모드 전용 max_throttle=1.0
- 수동모드 reverse 허용
- ESP32 실제 actuator 출력 검증

### Host 제어 구조

- Controller / HostController 분리
- ManualControlProducer / AutoControlProducer
- VehicleServerDirectSender
- RemoteDirectSession
- ControlScheduler
- AutoHostRunner
- HybridControlMux
- MANUAL_WASD ↔ AUTO_HOST 전환
- AUTO_PENDING + fresh pose gate
- route를 같은 host/session에 재로딩하는 구조
- 다중 차량 세션 독립성 테스트

### 자동 테스트

- controller 32/32
- host_control 59/59
- integration 24/24
- comm 31/31
- pipeline 18/18
- 총 164/164 PASS

## 현재 통합 기준

현재 AUTO 경로에서 ESP32로 보내는 주행 명령은 `DIRECT_CONTROL`이다.

```text
Camera Pose + waypoint
→ HostController
→ AutoControlProducer
→ DIRECT_CONTROL(throttle, steering)
→ ESP32 REMOTE_DIRECT
```

`WAYPOINT`/`GO`를 ESP32에 보내서 ESP32가 위치제어를 수행하는 경로는 기존 프로토콜/대안 구조로 남겨둔다. SW팀 구현과 최신 통합 테스트 후 최종 구조를 확정한다.

## 다음 실차 검증

- SW팀 마우스 클릭 waypoint 기능과 최신 통합 코드 결합
- Camera → Pose → waypoint → HostController → DIRECT_CONTROL → ESP32 종단 간 검증
- waypoint 도달/정지 오차 확인
- 실제 회전반경 확인
- 필요할 때만 서보 운용각 재보정

## 조향 기준

현재 운용 기준:

```text
left strong   50°
left weak     68°
center        86°
right weak   104°
right strong 122°
```

기계 한계 확인값 약 22°/130°는 정상 운용값이 아니다.

## 아직 완료라고 기록하지 않는 항목

- 최신 카메라 + waypoint + AUTO_HOST 종단 간 실차 검증
- 최종 주차면 배정부터 주차 완료까지 전체 데모
- 장애물 발생 후 재경로 종단 간 실차 검증
- RC카 2대 협력 주차
- 엔코더 기반 정밀 거리/속도 폐루프