"""Install the Week 4 nodes, launch description, and joint configuration."""

from glob import glob
import os

from setuptools import find_packages, setup


package_name = "week04_pc_jetson_comm"

setup(
    name=package_name,
    version="0.1.0",
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
    maintainer_email="student@example.com",
    description="Read-only PC and Jetson joint-state Topic and Trigger Service lab",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "joint_state_publisher = week04_pc_jetson_comm.joint_state_topic_publisher:main",
            "joint_state_topic_listener = week04_pc_jetson_comm.joint_state_topic_listener:main",
            "joint_state_server = week04_pc_jetson_comm.joint_state_service_server:main",
            "joint_state_client = week04_pc_jetson_comm.joint_state_service_client:main",
        ],
    },
)
