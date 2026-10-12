"""Install the Week 6 joystick EEF control ROS 2 package."""

from glob import glob
import os

from setuptools import find_packages, setup


package_name = "week06_ee_control"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test", "tests"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools", "numpy", "PyYAML"],
    zip_safe=True,
    maintainer="PNU ROS 2 course",
    maintainer_email="student@example.com",
    description="Joystick-based end-effector control with FK and IK",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "arm_driver = week06_ee_control.arm_driver:main",
            "joystick_to_pose = week06_ee_control.joystick_to_pose:main",
            "ik_solver = week06_ee_control.ik_solver:main",
            "fk_solver = week06_ee_control.fk_solver:main",
            "ee_pose_listener = week06_ee_control.ee_pose_listener:main",
        ],
    },
)
