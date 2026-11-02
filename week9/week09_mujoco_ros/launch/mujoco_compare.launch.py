"""Launch the MuJoCo bridge and real-vs-simulation recorder."""

from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    """Build the Week 9 PC launch description."""
    # ROS CLI와 colcon은 시스템 Python을 사용해도 된다. PC 노드 두 개는
    # 실행 파일의 shebang과 관계없이 MuJoCo를 설치한 venv로 실행한다.
    python_executable = LaunchConfiguration("python_executable")
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "python_executable",
                default_value=str(Path.home() / "week9/.venv/bin/python3"),
                description="Python interpreter for both PC nodes",
            ),
            DeclareLaunchArgument(
                "show_viewer",
                default_value="true",
                description="Open the native MuJoCo viewer",
            ),
            Node(
                package="week09_mujoco_ros",
                executable="mujoco_ros_bridge",
                name="mujoco_ros_bridge",
                output="screen",
                prefix=[python_executable],
                parameters=[
                    {
                        "show_viewer": ParameterValue(
                            LaunchConfiguration("show_viewer"),
                            value_type=bool,
                        )
                    }
                ],
            ),
            Node(
                package="week09_mujoco_ros",
                executable="real_sim_comparator",
                name="real_sim_comparator",
                output="screen",
                prefix=[python_executable],
            ),
        ]
    )
