#!/usr/bin/env python3
"""Single ROS 2 node to read joints, receive targets, and hold position."""

import math
import time
from typing import List, Optional

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool

from .hardware_interface import FeetechBus, load_joint_config


class JointPositionController(Node):
    """Single node managing joint state publishing, target receiving, and safety torque."""

    def __init__(self, bus: FeetechBus) -> None:
        super().__init__("joint_controller")
        self._bus = bus
        self._config = bus.config

        self._torque_requested = False
        self._torque_enabled = False
        self._release_pending = False

        self._target: Optional[List[float]] = None
        self._commanded: Optional[List[float]] = None
        self._measured: Optional[List[float]] = None
        self._last_write_time = 0.0
        self._moving_to_target = False
        self._waiting_for_state_warning_time = 0.0

        self._publisher = self.create_publisher(JointState, "/joint_states", 10)
        self._target_subscription = self.create_subscription(
            JointState,
            "/joint_targets",
            self._on_target,
            QoSProfile(depth=1),
        )

        self._torque_subscription = self.create_subscription(
            Bool,
            "/safety/torque_enable",
            self._on_torque,
            10,
        )

        self.create_timer(
            1.0 / max(1.0, self._config.publish_hz),
            self._read_and_publish_state,
        )

        self.create_timer(
            1.0 / max(1.0, self._config.control_hz),
            self._control_step,
        )

        self.get_logger().info(
            "Joint controller ready on /joint_states & /joint_targets"
        )
        if not self._torque_requested:
            self.get_logger().warning(
                "Torque is disabled. Publish 'data: true' on /safety/torque_enable to enable torque."
            )

    def _read_and_publish_state(self) -> None:
        """20Hz timer: Read measured positions and publish JointState."""
        try:
            positions = self._bus.read_positions()
        except Exception as exc:
            self.get_logger().error(f"관절값 읽기 실패: {exc}")
            self._measured = None
            if self._torque_enabled:
                self._torque_requested = False
                self._release_pending = True
            return

        self._measured = list(positions)

        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = list(self._config.joint_names)
        message.position = list(positions)
        self._publisher.publish(message)

    def _on_torque(self, message: Bool) -> None:
        """Receive safety torque enable/disable request."""
        if message.data and self._release_pending:
            self.get_logger().error("토크 해제가 확인될 때까지 재활성화할 수 없습니다.")
            return
        self._torque_requested = bool(message.data)

    def _on_target(self, message: JointState) -> None:
        """Receive target joint positions and verify against Soft Limits."""
        if not message.name or len(message.name) != len(message.position):
            self.get_logger().error("name과 position 배열 길이가 다릅니다.")
            return

        received = {}
        for name, raw_pos in zip(message.name, message.position):
            if name not in self._config.joint_names:
                self.get_logger().error(f"알 수 없는 관절 이름: {name}")
                return
            if name in received:
                self.get_logger().error(f"중복 관절 이름: {name}")
                return
            pos = float(raw_pos)

            lower, upper = self._config.limit_rad[name]
            if not lower <= pos <= upper:
                self.get_logger().error(
                    f"{name}={pos:.4f} rad 명령 거부; 허용 범위=[{lower:.4f}, {upper:.4f}] rad"
                )
                return
            received[name] = pos

        if (not self._torque_enabled or not self._torque_requested
                or self._release_pending or self._target is None):
            self.get_logger().warning(
                "Torque가 활성화된 뒤 목표 관절값을 보내세요."
            )
            return

        updated = list(self._target)
        for idx, name in enumerate(self._config.joint_names):
            if name in received:
                updated[idx] = received[name]
        self._target = updated
        self._moving_to_target = True

        values = ", ".join(
            f"{n}={p:.3f}rad" for n, p in received.items()
        )
        self.get_logger().info(f"Target accepted: {values}")

    def _apply_torque_request(self) -> bool:
        """Apply torque on/off safely."""
        requested = self._torque_requested
        enabled = self._torque_enabled

        if requested == enabled and not self._release_pending:
            return enabled

        if not requested:
            self._bus.disable_torque()
            self._torque_enabled = False
            self._release_pending = False
            self._target = None
            self._commanded = None
            self._moving_to_target = False
            self.get_logger().warning("Servo torque disabled")
            return False

        if self._measured is None:
            now = time.monotonic()
            if now - self._waiting_for_state_warning_time >= 1.0:
                self.get_logger().warning("현재 관절값을 기다리는 중입니다...")
                self._waiting_for_state_warning_time = now
            return False

        # Refresh immediately before enabling; an old cached pose could cause a jump.
        measured = list(self._bus.read_positions())
        self._measured = list(measured)
        self._bus.write_positions(
            measured, 3000, 30
        )
        self._torque_enabled = True
        self._target = list(measured)
        self._commanded = list(measured)
        self._last_write_time = time.monotonic()
        self._moving_to_target = False
        self.get_logger().warning(
            "Servo torque enabled; current pose is initial target"
        )
        return True

    def _stop_after_error(self) -> None:
        """Cancel motion and retry release on later control ticks if necessary."""
        self._torque_requested = False
        self._release_pending = True
        self._target = None
        self._commanded = None
        self._moving_to_target = False
        try:
            self._apply_torque_request()
        except Exception as exc:
            self.get_logger().error(f"토크 해제 미확인; 다음 주기에 재시도: {exc}")

    def _control_step(self) -> None:
        """30Hz timer: apply torque requests, interpolate, and write targets."""
        # 1. 먼저 토크 켬/끔 요청을 실제 하드웨어에 반영한다.
        # 토크가 꺼져 있거나 현재 관절값을 아직 읽지 못했다면 제어하지 않는다.
        try:
            torque_enabled = self._apply_torque_request()
        except Exception as exc:
            self.get_logger().error(f"토크 요청 처리 실패: {exc}")
            self._stop_after_error()
            return
        if not torque_enabled:
            return

        # 토크를 켤 때 현재 자세로 초기화되지만, 방어적으로 값이 있는지 확인한다.
        if self._target is None or self._commanded is None:
            return

        # target: 최종적으로 도달할 목표값
        # commanded: 직전 제어 주기에 서보로 보낸 명령값
        target = list(self._target)
        commanded = list(self._commanded)
        # 제어주기 == 30 Hz
        dt = 1.0 / max(1.0, self._config.control_hz)

        # 2. 각 관절을 한 번에 목표로 보내지 않고 최대 속도만큼만 이동시킨다.
        next_command = []
        for name, curr, goal in zip(
            self._config.joint_names, commanded, target
        ):
            # 한 주기 동안 이동할 수 있는 최대 각도 = 최대 속도 × 주기 시간
            max_step = self._config.max_vel_rad_s[name] * dt
            err = goal - curr
            if abs(err) <= max_step:
                # 목표가 한 걸음 안에 있으면 목표값을 그대로 사용한다.
                next_command.append(goal)
            else:
                # 목표가 멀면 목표 방향으로 max_step만큼만 이동한다.
                next_command.append(curr + math.copysign(max_step, err))

        # 3. 명령값이 변했거나 Heartbeat 전송 시각이 되었는지 확인한다.
        now = time.monotonic()
        cmd_changed = any(
            abs(n - o) > 1e-9 for n, o in zip(next_command, commanded)
        )
        hb_due = (now - self._last_write_time) >= (
            1.0 / self._config.heartbeat_hz
        )

        # 이동 중이 아니고 Heartbeat 시각도 아니면 불필요한 시리얼 쓰기를 생략한다.
        if not cmd_changed and not hb_due:
            return

        # 4. 계산한 다음 명령값을 실제 Feetech 서보에 전송한다.
        try:
            self._bus.write_positions(
                next_command, 3000, 30
            )
        except Exception as exc:
            self.get_logger().error(f"관절 목표 쓰기 실패: {exc}")
            self._stop_after_error()
            return

        # 전송에 성공한 값과 시각을 다음 제어 주기에서 사용할 수 있도록 저장한다.
        self._commanded = list(next_command)
        self._last_write_time = now

        # 5. 모든 관절이 목표에 도달하면 이동 상태를 한 번만 종료 처리한다.
        reached = all(
            abs(g - c) <= 1e-9 for g, c in zip(target, next_command)
        )
        if reached and self._moving_to_target:
            self._moving_to_target = False
            self.get_logger().info(
                f"Target reached; holding target with {self._config.heartbeat_hz:.1f}Hz heartbeat"
            )


def main(args=None) -> None:
    rclpy.init(args=args)
    bus = None
    node = None
    try:
        config_path = (
            get_package_share_directory("week05_joint_control")
            + "/config/joints.yaml"
        )
        config = load_joint_config(config_path)
        bus = FeetechBus(config)
        # 이전 프로그램의 종료 상태와 관계없이 실제 서보 토크를 OFF로 맞춘다.
        bus.disable_torque()
        node = JointPositionController(bus)
        node.get_logger().warning("Servo torque disabled on startup")
        try:
            rclpy.spin(node)
        except (KeyboardInterrupt, ExternalShutdownException):
            pass
    finally:
        try:
            if bus is not None:
                bus.disable_torque()
                if node is not None:
                    node.get_logger().warning("Servo torque disabled on shutdown")
        except Exception as exc:
            if node is not None:
                node.get_logger().error(f"종료 중 토크 해제 실패: {exc}")
            else:
                print(f"종료 중 토크 해제 실패: {exc}")
        finally:
            try:
                if node is not None:
                    node.destroy_node()
            finally:
                try:
                    if bus is not None:
                        bus.close()
                finally:
                    if rclpy.ok():
                        rclpy.shutdown()


if __name__ == "__main__":
    main()
