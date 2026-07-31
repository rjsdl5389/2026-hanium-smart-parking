# Review fixes

검토 과정에서 아래 항목을 수정했습니다.

- 같은 TCP 연결의 HELLO 재전송에서 session_id가 매번 바뀌던 문제 수정: 같은 sync 시도는 기존 HELLO_ACK 재전송.
- HOLD 후 RESET으로 새 HELLO가 들어오는 경우에는 새 세션을 발급하도록 구분.
- previous_state=ERROR/EMERGENCY_STOP, motor_stopped=false, error_code 존재 시 HELLO_ACK=HOLD.
- SET_MODE(REMOTE_DIRECT)가 STATUS에서 ACCEPTED된 뒤에만 DIRECT_CONTROL 스트리밍 시작.
- 새 소켓이 기존 소켓을 대체할 때 이전 session을 먼저 폐기하여 old session_id가 새 소켓으로 전송되지 않게 수정.
- `stream pause` / `stream resume` 추가: HEARTBEAT를 유지하며 DIRECT_CONTROL 500ms timeout을 실제로 시험 가능.
- Windows 키보드 모드에 0.75초 deadman 추가: 키 반복이 끊기면 throttle=0.
- 송수신 NDJSON을 현재 아키텍처의 512B 상한으로 통일.
- mock ESP32의 모터 매핑/RESET mode/compact STATUS를 실제 펌웨어와 맞춤.

검증: `python -m unittest discover -s tests -t .` 31개 통과.

## Second cross-review fixes
- STOP now cancels a pending REMOTE_DIRECT mode-ACK gate, so a later STOP STATUS cannot accidentally enable streaming for an older SET_MODE.
- Reliable retry timing is now per command: STOP/WAIT 100 ms, other reliable commands 300 ms. This matches the architecture's safety timing more closely.
- Added regression coverage for STOP preemption/retry timing and compact STATUS size.
