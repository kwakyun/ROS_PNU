"""Complete the Service launch description for Practice 2."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Build the bringup launch description for the Service exercise."""
    # TODO: joint_state_publisher와 joint_state_service_server를 실행하는
    # Node 정의를 LaunchDescription 안에 추가하시오.
    return LaunchDescription(
        [
            Node(
                package="week03_ros2_jetson",
                executable="joint_state_publisher",
                name="joint_state_publisher",
                output="screen",
            ),
            Node(
                package="week03_ros2_jetson",
                executable="joint_state_service_server",
                name="joint_state_service_server",
                output="screen",
            ),
        ]
    )
