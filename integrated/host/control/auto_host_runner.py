"""control/auto_host_runner.py (backend 에 추가할 얇은 래퍼 — 템플릿, v4 실제 API).

이 파일을 backend repo 의 control/ 아래에 두고 실제 VehicleServer/Waypoint 와 결선한다.
이 패키지의 controller/ host_control/ integration/ 이 backend PYTHONPATH 에 있어야 한다.

실제 backend 계약:
- car_id 는 int(1,2). wire "CAR_01" 은 서버 내부에서만.
- SET_MODE 비동기: send_set_mode->seq, ACCEPTED 는 on_command_result/on_status 콜백으로 확인.
- callback 은 attach()로 fan-out(기존 pipeline/orchestrator callback 보존).
- AUTO_HOST arm 시 server.direct_control_enabled = True.

camera 콜백과 control loop 를 분리:
- on_camera_pose(): pose_source.observe(obs_time) 만. (관측 timestamp 보존)
- ControlScheduler(100ms): host.tick() → VehicleServer.push_control. camera 무관하게 계속.
"""

from __future__ import annotations

from typing import Any, Optional

from host_control import HostController, HostWaypointMission
from host_control.producers import ManualInput
from integration.backend_adapter import VehicleServerDirectSender, waypoints_from_backend
from integration.control_scheduler import ControlScheduler
from integration.remote_direct_session import RemoteDirectSession, ModeHandshakeError


class AutoHostRunner:
    def __init__(self, server: Any, car_id: int, backend_waypoints) -> None:
        assert isinstance(car_id, int), "production car_id 는 int(1,2)"
        self.car_id = car_id
        self._server = server
        mission = HostWaypointMission(waypoints_from_backend(backend_waypoints))
        self.host = HostController(
            mission=mission, sender=VehicleServerDirectSender(server, car_id))
        self.session = RemoteDirectSession(self.host, server, car_id)
        self.scheduler = ControlScheduler(self.host)  # 100ms
        self.session.attach()   # ★ callback fan-out (기존 보존)

    def start(self, *, wait_s: float = 2.0) -> None:
        """REMOTE_DIRECT 승인 후 AUTO_HOST 시작."""
        self.session.arm_auto(wait_s=wait_s)
        self.scheduler.start()

    def load_waypoints(self, backend_waypoints) -> None:
        """새 primary route 로 교체한다. fresh camera pose 전까지 zero 유지."""
        mapped = waypoints_from_backend(backend_waypoints)
        # route 를 갈아끼우는 순간 기존 pose/제어값을 재사용하지 않는다.
        # 즉시 zero를 내보내고 pose_source 를 비운 뒤 새 route 를 RUNNING 으로 연다.
        self.host.prepare_route_switch()
        self.host.mission.load(mapped)

    def load_recovery_waypoints(self, backend_waypoints):
        """REPLAN_REQUIRED → recovery route 삽입 → RUNNING 전환.

        recovery waypoint 완료 뒤 mission 이 실패했던 기존 target과 남은 route로
        자동 복귀한다. 실제 recovery 경로 생성은 backend planner 몫이다.

        안전 규칙: recovery route 를 받는 순간 즉시 zero + 기존 pose 폐기.
        그 뒤 새 카메라 관측이 들어오기 전까지 HostController 는 NO_POSE zero만
        내보낸다. 즉 REPLAN_REQUIRED 에서 임의로 재출발하지 않는다.
        """
        mapped = waypoints_from_backend(backend_waypoints)
        self.host.prepare_route_switch()
        status = self.host.mission.load_recovery(mapped)
        return status

    def on_camera_pose(self, x_mm, y_mm, heading_deg, obs_time) -> None:
        """CV 파이프라인 콜백. 새 프레임에서만 호출. control 계산은 하지 않는다."""
        self.host.pose_source.observe(x_mm, y_mm, heading_deg, obs_time)

    @property
    def current_target(self):
        return self.host.mission.current_target()

    @property
    def current_phase(self):
        return self.host.mission.current_phase

    @property
    def parking_active(self) -> bool:
        return self.host.mission.parking_active

    @property
    def approach_stage(self) -> str:
        return self.host.approach_guard.stage.value

    @property
    def approach_best_distance_cm(self):
        return self.host.approach_guard.best_distance_cm

    @property
    def replan_reason(self):
        return self.host.mission.replan_reason

    @property
    def final_confirm_count(self) -> int:
        return self.host.final_pose_guard.count

    @property
    def final_confirm_required(self) -> int:
        return self.host.final_pose_guard.required

    def set_manual_input(self, manual: Optional[ManualInput]) -> None:
        self.scheduler.set_manual_input(manual)

    def re_arm(self, *, wait_s: float = 2.0) -> None:
        """stale/comm/resync fault 후 사용자 명시적 재출발."""
        self.session.re_arm_auto(wait_s=wait_s)

    def stop(self, *, disable_global_direct: bool = False) -> None:
        """이 차량 정지. host FAULTED + zero + stop_control(car_id).

        ★ 다중 차량 안전: server.direct_control_enabled 는 server-global 이다.
          기본적으로 끄지 않는다(다른 AUTO_HOST 차량 stream 유지).
          단일 차량 운용이거나 전체 종료 시에만 disable_global_direct=True.
        """
        self.host.stop()                 # FAULTED latch + zero
        self.scheduler.stop()
        stop = getattr(self._server, "stop_control", None)
        if stop is not None:
            stop(self.car_id)            # 이 차량만 zero
        if disable_global_direct:
            try:
                self._server.direct_control_enabled = False
            except Exception:
                pass
