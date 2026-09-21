#!/usr/bin/env python3
"""Receive the Jetson joint-state Topic on the PC with fixed RELIABLE QoS."""

import math

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import JointState


class JointStateTopicListener(Node):
    """Print remote Topic data at a readable rate."""

    def __init__(self) -> None:
        super().__init__("joint_state_topic_listener")

        self._subscription = self.create_subscription(
            JointState,
            "/joint_states",
            self._on_state,
            QoSProfile(depth=10, reliability=QoSReliabilityPolicy.RELIABLE),
        )

    def _on_state(self, message: JointState) -> None:
        values = " | ".join(
            f"{name}={float(position):+.3f}rad "
            f"({math.degrees(float(position)):+.1f}deg)"
            for name, position in zip(message.name, message.position)
        )
        self.get_logger().info(values)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = JointStateTopicListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
