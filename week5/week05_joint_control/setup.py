"""Install the Week 5 controller, plotter and joint configuration."""

from glob import glob
import os

from setuptools import find_packages, setup


package_name = "week05_joint_control"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test", "tests"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
    ],
    install_requires=["setuptools", "PyYAML"],
    zip_safe=True,
    maintainer="student",
    maintainer_email="student@example.com",
    description="Week 5 joint position control and measured/requested plots",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "joint_controller = week05_joint_control.joint_controller:main",
            "joint_plotter = week05_joint_control.joint_plotter:main",
        ],
    },
)
