#!/usr/bin/env python3
"""Read Topcam frames and publish the configured sample geometry."""

from pathlib import Path
import cv2
from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

from .vision_common import load_config, open_source, sample_frame


class TopCameraPublisher(Node):
    def __init__(self):
        super().__init__("top_camera_publisher")
        share = Path(get_package_share_directory("week07_vision_control"))
        self.declare_parameter("config_path", str(share / "config/vision.yaml"))
        self._config = load_config(self.get_parameter("config_path").value, share)
        self._camera = open_source(self._config)
        self._bridge = CvBridge()
        self._publisher = self.create_publisher(Image, "/top_cam", qos_profile_sensor_data)
        self.create_timer(1.0 / self._config.data["camera"]["publish_hz"], self._capture)
        width, height = self._config.size
        self.get_logger().info(f"Publishing Topcam on /top_cam ({width}x{height}, bgr8)")

    def _capture(self):
        ok, frame = self._camera.read()
        if not ok:
            self.get_logger().warning("Topcam frame read failed")
            return
        message = self._bridge.cv2_to_imgmsg(sample_frame(frame, self._config), encoding="bgr8")
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = "top_camera"
        self._publisher.publish(message)

    def destroy_node(self):
        self._camera.release()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = TopCameraPublisher()
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
