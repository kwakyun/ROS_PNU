"""Launch the Topcam publisher and the detector with a selected Python runtime."""

from pathlib import Path
import sys
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory("week07_vision_control"))
    return LaunchDescription([
        DeclareLaunchArgument("config_path", default_value=str(share / "config/vision.yaml")),
        DeclareLaunchArgument("model_path", default_value=str(share / "models/vision_pose_best.pt")),
        DeclareLaunchArgument("python_executable", default_value=sys.executable),
        Node(
            package="week07_vision_control",
            executable="top_camera_publisher",
            name="top_camera_publisher",
            output="screen",
            parameters=[{"config_path": LaunchConfiguration("config_path")}],
        ),
        ExecuteProcess(
            cmd=[
                LaunchConfiguration("python_executable"),
                "-m",
                "week07_vision_control.yolo_object_detector",
                "--ros-args",
                "-p", ["config_path:=", LaunchConfiguration("config_path")],
                "-p", ["model_path:=", LaunchConfiguration("model_path")],
            ],
            output="screen",
        ),
    ])
