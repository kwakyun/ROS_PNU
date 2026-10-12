"""Kinematic model taken from physicai_arm/ik_calc.py."""

import math

import numpy as np


# URDF에서 가져온 각 관절의 고정 위치·방향과 가동 범위이다.
# 마지막 gripper_frame_joint는 모터가 없는 고정 연결이다.
CHAIN = [
    {
        "name": "shoulder_pan",
        "type": "revolute",
        "xyz": [0.0388353, -8.97657e-09, 0.0624],
        "rpy": [3.14159, 4.18253e-17, -3.14159],
        "lower": -1.91986,
        "upper": 1.91986,
    },
    {
        "name": "shoulder_lift",
        "type": "revolute",
        "xyz": [-0.0303992, -0.0182778, -0.0542],
        "rpy": [-1.5708, -1.5708, 0.0],
        "lower": -1.74533,
        "upper": 1.74533,
    },
    {
        "name": "elbow_flex",
        "type": "revolute",
        "xyz": [-0.11257, -0.028, 1.73763e-16],
        "rpy": [-3.63608e-16, 8.74301e-16, 1.5708],
        "lower": -1.69,
        "upper": 1.69,
    },
    {
        "name": "wrist_flex",
        "type": "revolute",
        "xyz": [-0.1349, 0.0052, 3.62355e-17],
        "rpy": [4.02456e-15, 8.67362e-16, -1.5708],
        "lower": -1.65806,
        "upper": 1.65806,
    },
    {
        "name": "wrist_roll",
        "type": "revolute",
        "xyz": [5.55112e-17, -0.0611, 0.0181],
        "rpy": [1.5708, 0.0486795, 3.14159],
        "lower": -2.74385,
        "upper": 2.84121,
    },
    {
        "name": "gripper_frame_joint",
        "type": "fixed",
        "xyz": [-0.0079, -0.000218121, -0.0981274],
        "rpy": [0.0, 3.14159, 0.0],
    },
]

# IK/FK가 계산하는 로봇 암 관절은 5개이며 gripper는 포함하지 않는다.
NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
]
LOWER = np.array(
    [-1.91986, -1.74533, -1.69, -1.65806, -2.74385],
    dtype=float,
)
UPPER = np.array(
    [1.91986, 1.74533, 1.69, 1.65806, 2.84121],
    dtype=float,
)
TICK_RAD = 2.0 * math.pi / 4096.0
PAN_X = float(CHAIN[0]["xyz"][0])
PAN_Y = float(CHAIN[0]["xyz"][1])


def rx(angle: float) -> np.ndarray:
    """Rotation matrix around X."""
    cosine, sine = math.cos(angle), math.sin(angle)
    return np.array(
        [[1.0, 0.0, 0.0], [0.0, cosine, -sine], [0.0, sine, cosine]],
        dtype=float,
    )


def ry(angle: float) -> np.ndarray:
    """Rotation matrix around Y."""
    cosine, sine = math.cos(angle), math.sin(angle)
    return np.array(
        [[cosine, 0.0, sine], [0.0, 1.0, 0.0], [-sine, 0.0, cosine]],
        dtype=float,
    )


def rz(angle: float) -> np.ndarray:
    """Rotation matrix around Z."""
    cosine, sine = math.cos(angle), math.sin(angle)
    return np.array(
        [[cosine, -sine, 0.0], [sine, cosine, 0.0], [0.0, 0.0, 1.0]],
        dtype=float,
    )


# 반복 계산 전에 각 링크의 고정 변환행렬을 한 번 만들어 둔다.
FIXED = []
REVOLUTE = []
for joint in CHAIN:
    transform = np.eye(4, dtype=float)
    roll, pitch, yaw = joint["rpy"]
    transform[:3, :3] = rz(yaw) @ ry(pitch) @ rx(roll)
    transform[:3, 3] = np.array(joint["xyz"], dtype=float)
    FIXED.append(transform)
    REVOLUTE.append(joint["type"] == "revolute")


def rz4(angle: float) -> np.ndarray:
    """Homogeneous rotation around local Z."""
    transform = np.eye(4, dtype=float)
    transform[:3, :3] = rz(angle)
    return transform


def forward_matrix(joints: np.ndarray) -> np.ndarray:
    """Return base_link-to-gripper homogeneous transform."""
    # base_link부터 링크를 순서대로 곱하고, 회전 관절에서는 현재 각도를 추가한다.
    transform = np.eye(4, dtype=float)
    joint_index = 0
    for fixed, is_revolute in zip(FIXED, REVOLUTE):
        transform = transform @ fixed
        if is_revolute:
            transform = transform @ rz4(float(joints[joint_index]))
            joint_index += 1
    return transform


def forward_position(joints: np.ndarray) -> np.ndarray:
    """Return the End Effector XYZ position."""
    return forward_matrix(joints)[:3, 3].copy()


def matrix_to_quaternion(rotation: np.ndarray):
    """Convert a 3x3 rotation matrix to ROS quaternion order x,y,z,w."""
    trace = float(np.trace(rotation))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * scale
        x = (rotation[2, 1] - rotation[1, 2]) / scale
        y = (rotation[0, 2] - rotation[2, 0]) / scale
        z = (rotation[1, 0] - rotation[0, 1]) / scale
    elif rotation[0, 0] > rotation[1, 1] and rotation[0, 0] > rotation[2, 2]:
        scale = math.sqrt(
            1.0 + rotation[0, 0] - rotation[1, 1] - rotation[2, 2]
        ) * 2.0
        w = (rotation[2, 1] - rotation[1, 2]) / scale
        x = 0.25 * scale
        y = (rotation[0, 1] + rotation[1, 0]) / scale
        z = (rotation[0, 2] + rotation[2, 0]) / scale
    elif rotation[1, 1] > rotation[2, 2]:
        scale = math.sqrt(
            1.0 + rotation[1, 1] - rotation[0, 0] - rotation[2, 2]
        ) * 2.0
        w = (rotation[0, 2] - rotation[2, 0]) / scale
        x = (rotation[0, 1] + rotation[1, 0]) / scale
        y = 0.25 * scale
        z = (rotation[1, 2] + rotation[2, 1]) / scale
    else:
        scale = math.sqrt(
            1.0 + rotation[2, 2] - rotation[0, 0] - rotation[1, 1]
        ) * 2.0
        w = (rotation[1, 0] - rotation[0, 1]) / scale
        x = (rotation[0, 2] + rotation[2, 0]) / scale
        y = (rotation[1, 2] + rotation[2, 1]) / scale
        z = 0.25 * scale
    quaternion = np.array([x, y, z, w], dtype=float)
    quaternion /= np.linalg.norm(quaternion)
    return tuple(float(value) for value in quaternion)
