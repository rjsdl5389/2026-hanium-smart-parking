# Integrated Host Controller

이 디렉터리는 backend 코드와 차량 제어 계층을 결합한 **현재 노트북 통합 기준 코드**다.

핵심 패키지:

- `controller/`: pose → control 수학/제어
- `host_control/`: authority, producers, mission, host controller
- `control/`: AUTO_HOST runner, hybrid manual/auto mux, WASD GUI
- `integration/`: backend/camera/REMOTE_DIRECT adapters
- `comm/`: ESP32 TCP/NDJSON server
- `pipeline/`: camera/backend/vehicle orchestration
- `parking/`, `cv/`, `rl/`: SW/backend 기능

현재 실차 통합 경로:

```text
Camera Pose + waypoint
→ HostController
→ DIRECT_CONTROL
→ ESP32 REMOTE_DIRECT
```

## Regression

```text
controller 32
host_control 59
integration 24
comm 31
pipeline 18
total 164
```

자세한 현재 상태는 저장소 루트의 `docs/integration_status_2026-08-10.md`를 참고한다.