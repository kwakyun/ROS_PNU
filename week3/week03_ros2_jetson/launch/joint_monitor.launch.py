"""Launch the joint publisher and listener for Practice 1."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Build the joint monitor launch description."""
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
                executable="joint_state_listener",
                name="joint_state_listener",
                output="screen",
            ),
        ]
    )
