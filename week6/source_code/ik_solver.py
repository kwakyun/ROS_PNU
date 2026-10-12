#!/usr/bin/env python3
"""Numerical IK node adapted from physicai_arm/ik_calc.py."""

import math
from typing import Optional

from geometry_msgs.msg import PoseStamped
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool

from .kinematics import (
    LOWER,
    NAMES,
    PAN_X,
    PAN_Y,
    TICK_RAD,
    UPPER,
    forward_position,
)


JOINT_STATES_TOPIC = "/joint_states"
TARGET_POSE_TOPIC = "/target_pose"
GRIPPER_TOPIC = "/gripper_open"
JOINT_TARGETS_TOPIC = "/joint_targets"
PUBLISH_HZ = 60.0
ITERATIONS = 8
DAMPING = 0.02
MAXIMUM_DELTA = 0.20
ACCEPT_ERROR = 0.020
TARGET_TIMEOUT_SEC = 0.25
GRIPPER_OPEN_POSITION = 0.80
GRIPPER_CLOSED_POSITION = 0.00


def quaternion_pitch(message: PoseStamped) -> float:
    """Extract pitch from a normalized pose quaternion."""
    x = float(message.pose.orientation.x)
    y = float(message.pose.orientation.y)
    z = float(message.pose.orientation.z)
    w = float(message.pose.orientation.w)
    value = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    return math.asin(value)


class IKSolver(Node):
    """Convert an EEF target into five arm joints plus a gripper target."""

    def __init__(self) -> None:
        super().__init__("ik_solver")
        self._state = {}
        self._measured: Optional[np.ndarray] = None
        self._target_position: Optional[np.ndarray] = None
        self._target_pitch: Optional[float] = None
        self._last_target_time = None
        self._solution: Optional[np.ndarray] = None
        self._target_version = 0
        self._solved_version = -1
        self._gripper_open = False

        self.create_subscription(
            JointState,
            JOINT_STATES_TOPIC,
            self._on_joint_state,
            10,
        )

        self.create_subscription(
            PoseStamped,
            TARGET_POSE_TOPIC,
            self._on_target_pose,
            10,
        )

        self.create_subscription(
            Bool,
            GRIPPER_TOPIC,
            self._on_gripper,
            10,
        )

        self._publisher = self.create_publisher(
            JointState, JOINT_TARGETS_TOPIC, 10
        )

        self._timer = self.create_timer(
            1.0 / PUBLISH_HZ,
            self._tick,
        )

    def _on_joint_state(self, message: JointState) -> None:
        # 모터 6개 중 IK 계산에 필요한 5개 arm joint를 이름 기준으로 모은다.
        # 이 값은 수치 IK를 시작할 초기 관절 자세(seed)로 사용된다.
        for name, position in zip(message.name, message.position):
            self._state[name] = float(position)
        if all(name in self._state for name in NAMES):
            self._measured = np.array(
                [self._state[name] for name in NAMES],
                dtype=float,
            )

    def _on_target_pose(self, message: PoseStamped) -> None:
        # 조이스틱 노드가 보낸 base_link 기준 XYZ와 pitch를 저장한다.
        if message.header.frame_id not in ("", "base_link"):
            self.get_logger().error(
                f"target frame must be base_link, got {message.header.frame_id}"
            )
            return
        position = np.array(
            [
                message.pose.position.x,
                message.pose.position.y,
                message.pose.position.z,
            ],
            dtype=float,
        )
        if not np.all(np.isfinite(position)):
            return
        self._target_position = position
        self._target_pitch = quaternion_pitch(message)
        self._last_target_time = self.get_clock().now()
        self._target_version += 1

    def _on_gripper(self, message: Bool) -> None:
        self._gripper_open = bool(message.data)

    @staticmethod
    def _pan_for(position: np.ndarray) -> float:
        return float(
            np.clip(
                -math.atan2(
                    float(position[1]) - PAN_Y,
                    float(position[0]) - PAN_X,
                ),
                LOWER[0],
                UPPER[0],
            )
        )

    @staticmethod
    def _pack(
        pan: float,
        shoulder: float,
        elbow: float,
        pitch: float,
        roll: float,
    ) -> np.ndarray:
        wrist = float(
            np.clip(pitch - shoulder - elbow, LOWER[3], UPPER[3])
        )
        return np.array(
            [
                np.clip(pan, LOWER[0], UPPER[0]),
                np.clip(shoulder, LOWER[1], UPPER[1]),
                np.clip(elbow, LOWER[2], UPPER[2]),
                wrist,
                np.clip(roll, LOWER[4], UPPER[4]),
            ],
            dtype=float,
        )

    def _solve(self) -> Optional[np.ndarray]:
        # pan은 목표의 X-Y 방향으로 직접 계산하고, shoulder와 elbow는
        # Jacobian으로 위치 오차가 작아지는 방향을 반복해서 찾는다.
        if (
            self._measured is None
            or self._target_position is None
            or self._target_pitch is None
        ):
            return None
        seed = (
            self._solution.copy()
            if self._solution is not None
            else self._measured.copy()
        )
        pan = self._pan_for(self._target_position)
        shoulder = float(seed[1])
        elbow = float(seed[2])
        roll = float(seed[4])
        damping_squared = DAMPING ** 2
        step_limit = MAXIMUM_DELTA
        best = self._pack(
            pan,
            shoulder,
            elbow,
            self._target_pitch,
            roll,
        )
        best_error = float(
            np.linalg.norm(self._target_position - forward_position(best))
        )
        finite_difference = 1e-4
        for _ in range(ITERATIONS):
            joints = self._pack(
                pan,
                shoulder,
                elbow,
                self._target_pitch,
                roll,
            )
            position = forward_position(joints)
            error = self._target_position - position
            error_norm = float(np.linalg.norm(error))
            if error_norm < best_error:
                best = joints.copy()
                best_error = error_norm

            shoulder_step = self._pack(
                pan,
                shoulder + finite_difference,
                elbow,
                self._target_pitch,
                roll,
            )
            elbow_step = self._pack(
                pan,
                shoulder,
                elbow + finite_difference,
                self._target_pitch,
                roll,
            )
            # 두 관절을 아주 조금 움직였을 때 EEF가 변하는 양으로
            # 3x2 Jacobian을 수치적으로 근사한다.
            jacobian = np.column_stack(
                (
                    (
                        forward_position(shoulder_step) - position
                    )
                    / finite_difference,
                    (
                        forward_position(elbow_step) - position
                    )
                    / finite_difference,
                )
            )
            delta = np.linalg.solve(
                jacobian.T @ jacobian
                + damping_squared * np.eye(2, dtype=float),
                jacobian.T @ error,
            )
            delta = np.clip(delta, -step_limit, step_limit)
            shoulder = float(
                np.clip(shoulder + delta[0], LOWER[1], UPPER[1])
            )
            elbow = float(
                np.clip(elbow + delta[1], LOWER[2], UPPER[2])
            )

        if best_error > ACCEPT_ERROR:
            self.get_logger().warning(
                f"IK target rejected: position error={best_error:.4f} m"
            )
            return None
        return np.clip(best, LOWER, UPPER)

    def _tick(self) -> None:
        # 최근 목표만 계산한다. 오래된 목표는 발행하지 않아 driver가
        # 마지막 명령 자세를 유지하도록 한다.
        if self._last_target_time is None:
            return
        age = (
            self.get_clock().now() - self._last_target_time
        ).nanoseconds / 1e9
        if age > TARGET_TIMEOUT_SEC:
            return
        if self._target_version != self._solved_version:
            solution = self._solve()
            self._solved_version = self._target_version
            if solution is None:
                self._solution = None
                return
            self._solution = solution
        if self._solution is None:
            return

        # 관절 제한이 encoder tick의 정수 배수와 정확히 일치하지 않을 수 있다.
        # 각도 양자화 후에도 제한 안쪽에 남도록 tick 범위를 다시 제한한다.
        quantized_ticks = np.round(self._solution / TICK_RAD)
        minimum_ticks = np.ceil(LOWER / TICK_RAD)
        maximum_ticks = np.floor(UPPER / TICK_RAD)
        quantized = (
            np.clip(quantized_ticks, minimum_ticks, maximum_ticks)
            * TICK_RAD
        )
        gripper = (
            GRIPPER_OPEN_POSITION
            if self._gripper_open
            else GRIPPER_CLOSED_POSITION
        )
        # IK로 구한 arm joint 5개와 별도 gripper 목표 1개를 결합한다.
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = NAMES + ["gripper"]
        message.position = [float(value) for value in quantized] + [gripper]
        self._publisher.publish(message)


def main(args=None) -> None:
    """Run the IK solver."""
    rclpy.init(args=args)
    node = IKSolver()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
