# Legacy ESP32-side test tools

`day3_tcp_server.py`는 현재 `remote-direct-bridge` 이전에 사용한 DAY3 독립 TCP 시험 서버다.

주의:

- 현재 브리지의 ACK ordering·stale STATUS 보강을 포함하지 않는다.
- 과거 문서의 `GO → MOVING` 기대는 실제 waypoint 추종 완료를 의미하지 않는다.
- 현행 실차 제어에는 `remote-direct-bridge/bridge_gui.py`를 사용한다.
