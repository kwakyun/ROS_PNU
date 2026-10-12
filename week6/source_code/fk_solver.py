#!/usr/bin/env python3
"""Publish current End Effector pose from measured joints."""

from geometry_msgs.msg import PoseStamped
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

from .kinematics import NAMES, forward_matrix, matrix_to_quaternion


JOINT_STATES_TOPIC = "/joint_states"
EE_POSE_TOPIC = "/ee_pose"
BASE_FRAME = "base_link"


class FKSolver(Node):
    """Compute the gripper-frame pose for every JointState."""

    def __init__(self) -> None:
        super().__init__("fk_solver")
        self._state = {}
        self.create_subscription(
            JointState,
            JOINT_STATES_TOPIC,
            self._on_joint_state,
            30,
        )
        self._publisher = self.create_publisher(
            PoseStamped,
            EE_POSE_TOPIC,
            30,
        )

    def _on_joint_state(self, message: JointState) -> None:
        # 메시지 배열 순서를 그대로 믿지 않고 관절 이름별로 현재값을 저장한다.
        for name, position in zip(message.name, message.position):
            self._state[name] = float(position)
        if not all(name in self._state for name in NAMES):
            return
        joints = np.array(
            [self._state[name] for name in NAMES],
            dtype=float,
        )
        # 5개 arm joint로 base_link에서 gripper까지의 4x4 변환행렬을 구한다.
        transform = forward_matrix(joints)
        quaternion = matrix_to_quaternion(transform[:3, :3])
        # 변환행렬의 위치와 회전을 ROS PoseStamped 메시지로 옮겨 발행한다.
        pose = PoseStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = BASE_FRAME
        pose.pose.position.x = float(transform[0, 3])
        pose.pose.position.y = float(transform[1, 3])
        pose.pose.position.z = float(transform[2, 3])
        pose.pose.orientation.x = quaternion[0]
        pose.pose.orientation.y = quaternion[1]
        pose.pose.orientation.z = quaternion[2]
        pose.pose.orientation.w = quaternion[3]
        self._publisher.publish(pose)


def main(args=None) -> None:
    """Run the FK solver."""
    rclpy.init(args=args)
    node = FKSolver()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
