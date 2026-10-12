#!/usr/bin/env python3
"""Convert gamepad input to a bounded End Effector target pose."""

import math
import time
from dataclasses import dataclass
from typing import Tuple

from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from std_msgs.msg import Bool
import yaml


# 게임패드가 다르면 이 축·버튼 번호를 /joy 출력에 맞게 수정한다.
AXIS_X = 1
AXIS_Y = 0
AXIS_Z = 7
AXIS_PITCH = 3
GRIPPER_BUTTON = 0

RATE_HZ = 25.0
JOY_TIMEOUT_SEC = 0.50

INITIAL_POSE = [0.20, 0.00, 0.10, 1.00]  # X, Y, Z, Pitch


@dataclass(frozen=True)
class PoseConfig:
    """Workspace and joystick limits loaded from joints.yaml."""

    x_limit: Tuple[float, float]
    y_limit: Tuple[float, float]
    z_limit: Tuple[float, float]
    pitch_limit: Tuple[float, float]
    radius_limit: Tuple[float, float]
    deadzone: float
    speed_x: float
    speed_y: float
    speed_z: float
    speed_pitch: float


def load_pose_config(path: str) -> PoseConfig:
    """Read pose range and speed limits from joints.yaml."""
    with open(path, "r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}

    range_limit = raw["pose_range_limit"]
    speed_limit = raw["pose_speed_limit"]

    def pair(key: str) -> Tuple[float, float]:
        values = range_limit[key]
        return float(values[0]), float(values[1])

    return PoseConfig(
        x_limit=pair("X_LIMIT"),
        y_limit=pair("Y_LIMIT"),
        z_limit=pair("Z_LIMIT"),
        pitch_limit=pair("PITCH_LIMIT"),
        radius_limit=pair("RADIUS_LIMIT"),
        deadzone=float(speed_limit["DEADZONE"]),
        speed_x=float(speed_limit["SPEED_X"]),
        speed_y=float(speed_limit["SPEED_Y"]),
        speed_z=float(speed_limit["SPEED_Z"]),
        speed_pitch=float(speed_limit["SPEED_PITCH"]),
    )


class JoystickToPose(Node):
    """Publish /target_pose and /gripper_open from fresh /joy input."""

    def __init__(self, config: PoseConfig) -> None:
        super().__init__("joystick_to_pose")
        self._config = config
        self._x, self._y, self._z, self._pitch = INITIAL_POSE
        self._gripper_open = False
        self._axes = []
        self._buttons = []
        self._previous_buttons = []
        self._last_joy_time = None
        self._warned_timeout = False

        self._pose_publisher = self.create_publisher(
            PoseStamped, "/target_pose", 10
        )
        self._gripper_publisher = self.create_publisher(
            Bool, "/gripper_open", 10
        )
        self.create_subscription(
            Joy,
            "/joy",
            self._on_joy,
            10,
        )
        self.create_timer(1.0 / RATE_HZ, self._tick)

    def _axis(self, index: int) -> float:
        """Return one axis value after range and deadzone checks."""
        if index < 0 or index >= len(self._axes):
            return 0.0
        value = float(self._axes[index])
        return 0.0 if abs(value) < self._config.deadzone else value

    def _button(self, index: int, previous: bool = False) -> int:
        """Return a current or previous button value safely."""
        values = self._previous_buttons if previous else self._buttons
        if index < 0 or index >= len(values):
            return 0
        return int(values[index])

    def _on_joy(self, message: Joy) -> None:
        """Store the latest gamepad state and toggle the gripper on an edge."""
        self._previous_buttons = list(self._buttons)
        self._axes = list(message.axes)
        self._buttons = list(message.buttons)
        self._last_joy_time = time.monotonic()
        self._warned_timeout = False

        pressed = self._button(GRIPPER_BUTTON) == 1
        was_pressed = self._button(GRIPPER_BUTTON, previous=True) == 1
        if pressed and not was_pressed:
            self._gripper_open = not self._gripper_open

    @staticmethod
    def _clamp(value: float, limits) -> float:
        return min(max(value, limits[0]), limits[1])

    def _tick(self) -> None:
        """Integrate fresh stick input and publish one bounded target."""
        if self._last_joy_time is None:
            return
        if time.monotonic() - self._last_joy_time > JOY_TIMEOUT_SEC:
            if not self._warned_timeout:
                self.get_logger().warning(
                    "Joy input timeout; target pose publication stopped."
                )
                self._warned_timeout = True
            return

        dt = 1.0 / RATE_HZ
        self._x += self._config.speed_x * self._axis(AXIS_X) * dt
        self._y += self._config.speed_y * self._axis(AXIS_Y) * dt
        self._z += self._config.speed_z * self._axis(AXIS_Z) * dt
        self._pitch += (
            self._config.speed_pitch * self._axis(AXIS_PITCH) * dt
        )

        self._x = self._clamp(self._x, self._config.x_limit)
        self._y = self._clamp(self._y, self._config.y_limit)
        self._z = self._clamp(self._z, self._config.z_limit)
        self._pitch = self._clamp(
            self._pitch, self._config.pitch_limit
        )

        radius = math.hypot(self._x, self._y)
        if radius > 1.0e-9 and radius < self._config.radius_limit[0]:
            scale = self._config.radius_limit[0] / radius
            self._x *= scale
            self._y *= scale
        elif radius > self._config.radius_limit[1]:
            scale = self._config.radius_limit[1] / radius
            self._x *= scale
            self._y *= scale

        pose = PoseStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = "base_link"
        pose.pose.position.x = self._x
        pose.pose.position.y = self._y
        pose.pose.position.z = self._z
        pose.pose.orientation.y = math.sin(0.5 * self._pitch)
        pose.pose.orientation.w = math.cos(0.5 * self._pitch)
        self._pose_publisher.publish(pose)

        gripper = Bool()
        gripper.data = self._gripper_open
        self._gripper_publisher.publish(gripper)


def main(args=None) -> None:
    rclpy.init(args=args)
    config_path = (
        get_package_share_directory("week06_ee_control")
        + "/config/joints.yaml"
    )
    config = load_pose_config(config_path)
    node = JoystickToPose(config)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
