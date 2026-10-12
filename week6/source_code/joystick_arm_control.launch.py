"""Launch the complete QuickRef-style joystick control chain on Jetson."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Build the Jetson-only gamepad, IK, arm, FK, and EEF chain."""
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "device_id",
                default_value="0",
                description=(
                    "SDL joystick device ID reported by "
                    "joy_enumerate_devices"
                ),
            ),
            DeclareLaunchArgument(
                "start_joy",
                default_value="true",
                description="Start joy_node; false allows manual /joy tests",
            ),
            Node(
                package="joy",
                executable="joy_node",
                name="joystick_pub_node",
                output="screen",
                condition=IfCondition(
                    LaunchConfiguration("start_joy")
                ),
                parameters=[
                    {
                        "device_id": LaunchConfiguration(
                            "device_id"
                        )
                    }
                ],
            ),
            Node(package="week06_ee_control", executable="joystick_to_pose", name="joystick_to_pose", output="screen"),
            Node(package="week06_ee_control", executable="arm_driver", name="arm_driver", output="screen"),
            Node(package="week06_ee_control", executable="ik_solver", name="ik_solver", output="screen"),
            Node(package="week06_ee_control", executable="fk_solver", name="fk_solver", output="screen"),
            Node(package="week06_ee_control", executable="ee_pose_listener", name="ee_pose_listener", output="screen"),
        ]
    )
