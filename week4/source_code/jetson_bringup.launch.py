"""Launch the Jetson Topic publisher and remote Trigger Service server."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Build the Jetson bringup launch description."""
    return LaunchDescription(
        [
            # Publisher와 Server의 Subscriber에 같은 Reliability를 전달한다.
            DeclareLaunchArgument(
                "reliability",
                default_value="reliable",
                choices=["best_effort", "reliable"],
                description="QoS reliability for /joint_states",
            ),
            Node(
                package="week04_pc_jetson_comm",
                executable="joint_state_publisher",
                name="joint_state_publisher",
                output="screen",
                parameters=[
                    {"reliability": LaunchConfiguration("reliability")}
                ],
            ),
            Node(
                package="week04_pc_jetson_comm",
                executable="joint_state_server",
                name="joint_state_service_server",
                output="screen",
                parameters=[
                    {"reliability": LaunchConfiguration("reliability")}
                ],
            ),
        ]
    )
