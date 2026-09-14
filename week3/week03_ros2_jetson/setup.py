from glob import glob
import os
from setuptools import find_packages, setup

package_name = "week03_ros2_jetson"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools", "PyYAML"],
    zip_safe=True,
    maintainer="student",
    maintainer_email="student@todo.todo",
    description="Week 3 ROS2 Basic 2 Package for PhysicAI Arm",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "joint_state_publisher = week03_ros2_jetson.joint_state_publisher:main",
            "joint_state_listener = week03_ros2_jetson.joint_state_listener:main",
            "joint_state_service_server = week03_ros2_jetson.joint_state_service_server:main",
            "joint_state_service_client = week03_ros2_jetson.joint_state_service_client:main",
        ],
    },
)
