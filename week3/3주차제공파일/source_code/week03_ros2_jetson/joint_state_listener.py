#!/usr/bin/env python3
"""Print joint states in radians and degrees."""

import math

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

class JointStateListener(Node):
    """Subscribe to JointState and print it at a readable rate."""

    def __init__(self) -> None:
        super().__init__("joint_state_listener")
        # TODO: create_subscription()을 사용하여 JointState 타입으로 "/joint_states" 토픽을 구독하고, self._on_joint_state 콜백을 연결하시오.
        self._subscription = self.create_subscription(
            JointState,
            "/joint_states",
            self._on_joint_state,
            10,
        )
        self.get_logger().info("Listening to /joint_states")

    def _on_joint_state(self, message: JointState) -> None:
        if len(message.name) != len(message.position):
            self.get_logger().warning("name과 position 배열 길이가 다릅니다.")
            return

        values = [
            f"{name}={position:+.3f} rad ({math.degrees(position):+.1f} deg)"
            for name, position in zip(message.name, message.position)
        ]
        self.get_logger().info(" | ".join(values))


def main(args=None) -> None:
    """Run the listener."""
    rclpy.init(args=args)
    node = JointStateListener()
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
