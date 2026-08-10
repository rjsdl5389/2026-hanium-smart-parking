# 2026-08-10 통합/HIL 상태

## 이번 마일스톤

기존 backend 기반 통합 코드 위에 다음을 추가했다.

- host-side pose controller
- AUTO_HOST runner
- REMOTE_DIRECT session adapter
- MANUAL_WASD / AUTO_HOST hybrid mux
- 개발용 Tkinter GUI
- READY 직후 manual shell
- MANUAL → AUTO_PENDING → fresh pose → AUTO_HOST 전환
- same host/session route reload
- 실차 ESP32 HIL

## 실제 HIL 결과

노트북 모바일 핫스팟을 이용해 ESP32와 동일 LAN을 구성하고 TCP port 5000으로 연결했다.

확인 흐름:

```text
ESP32 Wi-Fi join
→ TCP connect
→ HELLO / HELLO_ACK
→ READY
→ SET_MODE REMOTE_DIRECT
→ DIRECT_CONTROL
→ HEARTBEAT
```

실제 actuator 출력 ON 상태에서:

- 전진 정상
- 후진 정상
- 좌/우 조향 정상
- STOP/neutral 정상

## 수동 속도/후진 문제 해결

기존 `ControllerConfig`는 frozen dataclass이며 기본값은 AUTO용 보수적 설정이다.

```text
max_throttle = 0.40
allow_reverse = False
```

이를 직접 수정하면 `FrozenInstanceError`가 발생하고 READY manual shell 생성이 중단되어 GUI가 `UNAVAILABLE`에 남는 문제가 있었다.

최종 해결:

- 원본 AUTO config를 수정하지 않음
- `dataclasses.replace()`로 MANUAL 전용 config 복사본 생성
- MANUAL producer에만 `max_throttle=1.0`, `allow_reverse=True` 적용

## 회귀 테스트

최종 수정 후:

```text
controller      32/32
host_control    59/59
integration     24/24
comm            31/31
pipeline        18/18
------------------
total          164/164 PASS
```

## SW팀 연동 다음 단계

SW팀은 마우스 클릭 지점을 waypoint로 사용한 주행 기능을 별도 구현/시험했다.

다음 단계는 최신 통합 코드 기준으로:

```text
Camera
→ Pose
→ click waypoint
→ AUTO_HOST
→ DIRECT_CONTROL
→ actual ESP32
→ actual RC car
```

을 다시 확인하는 것이다.

이 결과를 본 뒤 회전반경이 여전히 크면 `app_config.h`의 servo strong/weak 운용각을 단계적으로 조정한다.