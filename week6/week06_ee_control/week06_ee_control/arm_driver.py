#!/usr/bin/env python3
"""Read arm joints, accept IK targets, and drive the physical servos."""

import math
import time
from typing import List, Optional

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool

from .hardware_interface import FeetechBus, load_joint_config


JOINT_STATES_TOPIC = "/joint_states"
JOINT_TARGETS_TOPIC = "/joint_targets"
TORQUE_TOPIC = "/safety/torque_enable"
WRITE_SPEED = 32767
WRITE_ACCELERATION = 50


class ArmDriver(Node):
    """Connect ROS 2 joint topics to one Feetech servo bus."""

    def __init__(self, bus: FeetechBus) -> None:
        super().__init__("arm_driver")
        self._bus = bus
        self._config = bus.config

        self._torque_requested = False
        self._torque_enabled = False
        self._measured: Optional[List[float]] = None
        self._commanded: Optional[List[float]] = None
        self._target: Optional[List[float]] = None
        self._last_target_time: Optional[float] = None
        self._last_write_time = 0.0
        self._holding_after_timeout = True
        self._last_disabled_warning = 0.0
        self._last_state_warning = 0.0

        self._state_publisher = self.create_publisher(
            JointState, JOINT_STATES_TOPIC, 10
        )
        self.create_subscription(
            JointState, JOINT_TARGETS_TOPIC, self._on_target, 1
        )
        self.create_subscription(Bool, TORQUE_TOPIC, self._on_torque, 10)

        self.create_timer(
            1.0 / self._config.publish_hz,
            self._read_and_publish_state,
        )
        self.create_timer(
            1.0 / self._config.control_hz,
            self._control_step,
        )

    def _read_and_publish_state(self) -> None:
        """Read measured joints and publish /joint_states."""
        try:
            self._measured = self._bus.read_positions()
        except Exception as exc:
            self.get_logger().error(f"관절값 읽기 실패: {exc}")
            return

        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = list(self._config.joint_names)
        message.position = list(self._measured)
        self._state_publisher.publish(message)

    def _on_target(self, message: JointState) -> None:
        """Validate and store one complete IK target."""
        if not message.name or len(message.name) != len(message.position):
            self.get_logger().error("관절 name과 position 개수가 올바르지 않습니다.")
            return
        if len(set(message.name)) != len(message.name):
            self.get_logger().error("중복된 관절 이름이 있습니다.")
            return

        received = {
            name: float(position)
            for name, position in zip(message.name, message.position)
        }
        expected = set(self._config.joint_names)
        if set(received) != expected:
            missing = sorted(expected - set(received))
            unknown = sorted(set(received) - expected)
            self.get_logger().error(
                "5개 arm joint와 gripper 전체 목표가 필요합니다. "
                f"missing={missing}, unknown={unknown}"
            )
            return

        ordered = []
        for name in self._config.joint_names:
            value = received[name]
            lower, upper = self._config.limit_rad[name]
            if not math.isfinite(value) or not lower <= value <= upper:
                self.get_logger().error(
                    f"{name}={value:.4f} rad 목표 거부; "
                    f"허용 범위=[{lower:.4f}, {upper:.4f}] rad"
                )
                return
            ordered.append(value)

        if not self._torque_enabled:
            now = time.monotonic()
            if now - self._last_disabled_warning >= 2.0:
                self.get_logger().warning(
                    "토크가 꺼져 있어 IK 목표를 실행하지 않습니다."
                )
                self._last_disabled_warning = now
            return

        self._target = ordered
        self._last_target_time = time.monotonic()
        self._holding_after_timeout = False

    def _on_torque(self, message: Bool) -> None:
        """Store a torque request; the control timer applies it."""
        self._torque_requested = bool(message.data)

    def _apply_torque_request(self) -> bool:
        """Hold the current pose when enabling or release all servos."""
        if self._torque_requested == self._torque_enabled:
            return self._torque_enabled

        if not self._torque_requested:
            self._bus.disable_torque()
            self._torque_enabled = False
            self._target = None
            self._commanded = None
            self._last_target_time = None
            self._last_write_time = 0.0
            self._holding_after_timeout = True
            self.get_logger().warning("Servo torque disabled")
            return False

        if self._measured is None:
            now = time.monotonic()
            if now - self._last_state_warning >= 1.0:
                self.get_logger().warning("현재 관절값을 기다리는 중입니다.")
                self._last_state_warning = now
            return False

        # 현재 자세를 첫 명령으로 기록한 뒤 토크를 켜서 갑작스러운 이동을 막는다.
        self._bus.write_positions(
            self._measured, WRITE_SPEED, WRITE_ACCELERATION
        )
        self._torque_enabled = True
        self._target = list(self._measured)
        self._commanded = list(self._measured)
        self._last_target_time = None
        self._last_write_time = time.monotonic()
        self._holding_after_timeout = True
        self.get_logger().warning(
            "Servo torque enabled; current pose is the initial hold target"
        )
        return True

    def _control_step(self) -> None:
        """Apply torque requests and move one speed-limited step."""
        try:
            if not self._apply_torque_request():
                return
        except Exception as exc:
            self.get_logger().error(f"토크 요청 처리 실패: {exc}")
            return

        if self._target is None or self._commanded is None:
            return

        now = time.monotonic()
        target = list(self._target)

        age_ms = (
            (now - self._last_target_time) * 1000.0
            if self._last_target_time is not None
            else math.inf
        )
        if age_ms > self._config.command_timeout_ms:
            # IK 입력이 끊기면 진행 중인 이동을 멈추고 마지막 명령을 유지한다.
            target = list(self._commanded)
            if not self._holding_after_timeout:
                self._target = list(self._commanded)
                self._holding_after_timeout = True
                self.get_logger().warning(
                    "Joint target timeout: holding the last commanded pose"
                )

        dt = 1.0 / self._config.control_hz
        next_command = []
        for name, previous, goal in zip(
            self._config.joint_names, self._commanded, target
        ):
            maximum_step = self._config.max_vel_rad_s[name] * dt
            error = goal - previous
            if abs(error) <= maximum_step:
                next_command.append(goal)
            else:
                next_command.append(
                    previous + math.copysign(maximum_step, error)
                )

        command_changed = any(
            abs(new - old) > 1.0e-9
            for new, old in zip(next_command, self._commanded)
        )
        heartbeat_due = (
            now - self._last_write_time
            >= 1.0 / self._config.heartbeat_hz
        )
        if not command_changed and not heartbeat_due:
            return

        try:
            self._bus.write_positions(
                next_command, WRITE_SPEED, WRITE_ACCELERATION
            )
        except Exception as exc:
            self.get_logger().error(f"관절 목표 쓰기 실패: {exc}")
            return

        self._commanded = next_command
        self._last_write_time = now


def main(args=None) -> None:
    """Run the arm driver with explicit startup and shutdown safety."""
    rclpy.init(args=args)
    config_path = (
        get_package_share_directory("week06_ee_control")
        + "/config/joints.yaml"
    )
    config = load_joint_config(config_path)
    bus = FeetechBus(config)
    node = None

    try:
        bus.disable_torque()
        node = ArmDriver(bus)
        node.get_logger().warning("Servo torque disabled on startup")
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            bus.disable_torque()
            if node is not None:
                node.get_logger().warning("Servo torque disabled on shutdown")
        except Exception as exc:
            if node is not None:
                node.get_logger().error(f"종료 중 토크 해제 실패: {exc}")
        if node is not None:
            node.destroy_node()
        bus.close()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
