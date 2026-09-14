#!/usr/bin/env python3
"""Read the real PhysicAI Arm joints and publish sensor_msgs/JointState."""

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

from .hardware_interface import FeetechReader, load_joint_config


class JointStatePublisher(Node):
    """Own /dev/ttyACM0 and publish measured joint positions."""

    def __init__(self) -> None:
        super().__init__("joint_state_publisher")
        config_path = (
            get_package_share_directory("week03_ros2_jetson")
            + "/config/joints.yaml"
        )
        self._config = load_joint_config(config_path)
        self._reader = FeetechReader(self._config)

        # TODO: publisher, timer 객체를 활용해, JointState type으로 "joint_states" topic을 20Hz로 발행하기
        self._publisher = self.create_publisher(JointState, "joint_states", 10)
        self._timer = self.create_timer(
            1.0 / self._config.publish_hz, self._publish_state
        )

    def _publish_state(self) -> None:
        try:
            positions = self._reader.read_positions()
        except Exception as exc:
            self.get_logger().error(f"관절값 읽기 실패: {exc}")
            return

        # TODO: message 객체의 position 값 저장
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = list(self._config.joint_names)
        message.position = list(positions)

        # TODO: publisher 객체를 활용해, message를 publish
        self._publisher.publish(message)

    def destroy_node(self):
        self._reader.close()
        return super().destroy_node()

def main(args=None) -> None:
    """Run the joint-state publisher."""
    rclpy.init(args=args)
    node = JointStatePublisher()
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
