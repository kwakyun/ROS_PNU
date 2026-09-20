"""Launch the Jetson Topic publisher and remote Trigger Service server."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Build the Jetson bringup launch description."""
    return LaunchDescription(
        [
            # ros2 launch <package name> <*.launch.py>로 실행할 때, 사용 가능한 parameter 선언
            DeclareLaunchArgument(
                "reliability",
                default_value="best_effort",
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
