#!/usr/bin/env python3
"""ROS adapter: /top_cam -> shared YOLO inference -> /vision/<class> topics."""

import os
from pathlib import Path
import time
from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
from geometry_msgs.msg import PointStamped
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Float32, Float32MultiArray

from .vision_common import draw_detections, load_config, load_model, predict, sample_frame


class YoloObjectDetector(Node):
    def __init__(self):
        super().__init__("yolo_object_detector")
        share = Path(get_package_share_directory("week07_vision_control"))
        self.declare_parameter("config_path", str(share / "config/vision.yaml"))
        self.declare_parameter("model_path", "")
        self._config = load_config(self.get_parameter("config_path").value, share)
        model_path = self.get_parameter("model_path").value or str(share / "models/vision_pose_best.pt")
        self._model = load_model(model_path, self._config)
        self._bridge = CvBridge()
        # rclpy.Node owns _publishers. Application publishers use another name.
        self._detection_publishers = {}
        for item in self._config.classes:
            prefix = f"/vision/{item['name']}"
            pixel_publisher = self.create_publisher(PointStamped, prefix + "/pixel", 10)
            self._detection_publishers[item["name"]] = {
                "pixel": pixel_publisher,
                "detected": self.create_publisher(Bool, prefix + "/detected", 10),
                "confidence": self.create_publisher(Float32, prefix + "/confidence", 10),
                "bbox": self.create_publisher(Float32MultiArray, prefix + "/bbox", 10),
            }
        self._debug_publisher = self.create_publisher(Image, "/vision/debug_image", qos_profile_sensor_data)
        self.create_subscription(
            Image,
            "/top_cam",
            self._on_image,
            qos_profile_sensor_data,
        )
        self._last_log = 0.0
        self._last_error = float("-inf")
        self.get_logger().info("YOLO classes: " + ", ".join(self._config.names.values()))

    def _publish_detections(self, image, detections):
        for name, publishers in self._detection_publishers.items():
            detection = detections.get(name)
            publishers["detected"].publish(Bool(data=detection is not None))
            publishers["confidence"].publish(Float32(data=0.0 if detection is None else detection["confidence"]))
            if detection is None:
                continue
            point = PointStamped()
            point.header.stamp = image.header.stamp
            point.header.frame_id = "top_camera_pixel"
            point.point.x, point.point.y = map(float, detection["point"])
            publishers["pixel"].publish(point)
            publishers["bbox"].publish(Float32MultiArray(data=list(map(float, detection["bbox"]))))

    def _on_image(self, image):
        try:
            frame = sample_frame(self._bridge.imgmsg_to_cv2(image, desired_encoding="bgr8"), self._config)
            detections = predict(self._model, frame, self._config)
            self._publish_detections(image, detections)
            debug = self._bridge.cv2_to_imgmsg(draw_detections(frame, detections, self._config), encoding="bgr8")
            debug.header = image.header
            self._debug_publisher.publish(debug)
            if time.monotonic() - self._last_log >= 2:
                self.get_logger().info("Detected: " + (", ".join(detections) or "none"))
                self._last_log = time.monotonic()
        except Exception as exc:
            self._publish_detections(image, {})
            if time.monotonic() - self._last_error >= 2:
                self.get_logger().error(f"YOLO inference failed: {exc}")
                self._last_error = time.monotonic()


def main(args=None):
    os.environ["YOLO_AUTOINSTALL"] = "false"
    rclpy.init(args=args)
    node = None
    try:
        node = YoloObjectDetector()
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
