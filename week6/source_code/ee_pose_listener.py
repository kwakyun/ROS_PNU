#!/usr/bin/env python3
"""Print End Effector values on the Jetson control terminal."""

import math
import time

from geometry_msgs.msg import PoseStamped
import rclpy
from rclpy.node import Node


EE_POSE_TOPIC = "/ee_pose"
PRINT_HZ = 5.0


def quaternion_to_pitch(message: PoseStamped) -> float:
    """Extract pitch for a compact human-readable display."""
    quaternion = message.pose.orientation
    value = 2.0 * (
        quaternion.w * quaternion.y - quaternion.z * quaternion.x
    )
    return math.asin(max(-1.0, min(1.0, value)))


class EEPoseListener(Node):
    """Subscribe to /ee_pose and print position and orientation on Jetson."""

    def __init__(self) -> None:
        super().__init__("ee_pose_listener")
        self._last_print = 0.0
        self.create_subscription(
            PoseStamped,
            EE_POSE_TOPIC,
            self._on_pose,
            20,
        )

    def _on_pose(self, message: PoseStamped) -> None:
        # /ee_pose는 빠르게 들어오지만 사람이 읽기 쉽도록 print_hz로 출력만 제한한다.
        now = time.monotonic()
        period = 1.0 / PRINT_HZ
        if now - self._last_print < period:
            return
        self._last_print = now
        position = message.pose.position
        orientation = message.pose.orientation
        # ROS 자세는 quaternion이므로 수업에서 사용하는 pitch도 함께 계산한다.
        pitch = quaternion_to_pitch(message)
        self.get_logger().info(
            f"frame={message.header.frame_id} | "
            f"XYZ=({position.x:+.4f}, {position.y:+.4f}, "
            f"{position.z:+.4f}) m | "
            f"Q=({orientation.x:+.3f}, {orientation.y:+.3f}, "
            f"{orientation.z:+.3f}, {orientation.w:+.3f}) | "
            f"pitch={pitch:+.3f} rad"
        )


def main(args=None) -> None:
    """Run the Jetson-side EE monitor."""
    rclpy.init(args=args)
    node = EEPoseListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
