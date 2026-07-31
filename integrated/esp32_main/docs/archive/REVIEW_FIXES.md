# Review fixes

검토 과정에서 아래 항목을 수정했습니다.

- RESET/재접속 후 REMOTE_DIRECT mode가 남아 DIRECT_CONTROL만으로 재출발할 수 있던 문제 수정.
  - 새 TCP 연결, READY_ALLOWED, RESET 시 mode=WAYPOINT_AUTO로 복귀.
  - 다시 SET_MODE(REMOTE_DIRECT)가 필요.
- REMOTE_DIRECT 확장 STATUS가 512B 설계 상한을 넘던 문제 수정.
  - 무선 STATUS는 latest_control_seq/applied_throttle/applied_steering 중심의 compact 형식.
  - 실제 motor PWM/servo angle은 ESP32 serial log에서 확인.
  - MAX_TX_LINE_LENGTH=512로 복귀.
- 모터 DIR 극성을 `MOTOR_FORWARD_DIR_LEVEL`/`MOTOR_REVERSE_DIR_LEVEL`로 설정화.
- GPIO25/26에 펌웨어 초기화 후 내부 pull-down 적용.
  - 리셋/부팅 전 구간 안전을 위해 외부 pull-down 저항은 여전히 하드웨어에서 필요.
- 프로젝트의 16MB flash 기본값을 `sdkconfig.defaults`에 추가.

검증: 수정한 actuator.c / vehicle_control.c를 ESP-IDF API 스텁으로 clang `-fsyntax-only -Wall -Wextra -Wformat=2` 검사. 실제 ESP-IDF v6.0.2 `idf.py build`는 사용자 환경에서 최종 확인 필요.

## Second cross-review fixes
- Claude's review correctly noted that the compact STATUS was only practically (<512 B) safe with the current 9-character IDs, while the C structs still allowed much longer IDs.
- boot_id/session_id/error_code storage caps were tightened to the project's actual wire contract (15/15/31 chars max including null-buffer sizing), making the REMOTE_DIRECT STATUS worst-case fit under 512 B by construction rather than by assumption.
