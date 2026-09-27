#!/usr/bin/env python3
"""Publish real PhysicAI Arm joint states on the Jetson."""

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

from .hardware_interface import FeetechReader, load_joint_config
from .qos import joint_state_qos


class JointStatePublisher(Node):
    """Own /dev/ttyACM0 and expose measured joints to the DDS network."""

    def __init__(self) -> None:
        super().__init__("joint_state_publisher")
        self._reader = None
        try:
            config_path = (
                get_package_share_directory("week04_pc_jetson_comm")
                + "/config/joints.yaml"
            )
            self._config = load_joint_config(config_path)
            self.declare_parameter("reliability", "reliable")
            reliability = str(self.get_parameter("reliability").value)
            self._publisher = self.create_publisher(
                JointState, "/joint_states", joint_state_qos(reliability)
            )
            self._reader = FeetechReader(self._config)
            self._timer = self.create_timer(
                1.0 / self._config.publish_hz, self._publish_state
            )
        except Exception:
            self.destroy_node()
            raise

    def _publish_state(self) -> None:
        try:
            positions = self._reader.read_positions()
        except Exception as exc:
            self.get_logger().error(f"관절값 읽기 실패: {exc}")
            return
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = list(self._config.joint_names)
        message.position = list(positions)
        self._publisher.publish(message)

    def destroy_node(self):
        try:
            if self._reader is not None:
                self._reader.close()
                self._reader = None
        finally:
            super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = JointStatePublisher()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
