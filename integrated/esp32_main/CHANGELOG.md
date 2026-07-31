# Firmware changelog

## 0.5.3 — logic hardening

- REMOTE_DIRECT 실차 통합
- 전후진 활성화
- PWM 27 / 45 / 55
- Servo 50 / 68 / 86 / 104 / 122°
- 조향 중 모터 20 ms 정지 제거
- 엔코더 A/B GPIO34/35
- command result high-priority STATUS
- TransmitTask block/yield Watchdog 수정
- 새 session에서 mode·target·direct input 초기화
- WAYPOINT control 미구현 capability guard 추가

## archive

v3·v4·초기 v5 문서는 `docs/archive/`에서 확인한다.
