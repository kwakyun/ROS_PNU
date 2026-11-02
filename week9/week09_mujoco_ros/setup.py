import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'week09_mujoco_ros'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # TODO 5: Launch·설정·모델·자산 등록
        (os.path.join('share', package_name, 'launch'),
         glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'),
         glob('config/*.yaml')),
        (os.path.join('share', package_name, 'models'),
         glob('models/*.xml') + glob('models/*.urdf')),
        (os.path.join('share', package_name, 'models', 'assets'),
         glob('models/assets/*.stl') + glob('models/assets/*.png')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='곽윤직',
    maintainer_email='rhkrdbswlr@gmail.com',
    description='Week 9 MuJoCo and ROS 2 real-vs-simulation comparison',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # TODO 6: 실행 파일 등록
            'arm_io = week09_mujoco_ros.arm_io:main',
            'comparison_goal = week09_mujoco_ros.comparison_goal:main',
            'mujoco_ros_bridge = week09_mujoco_ros.mujoco_ros_bridge:main',
            'real_sim_comparator = week09_mujoco_ros.real_sim_comparator:main',
        ],
    },
)
