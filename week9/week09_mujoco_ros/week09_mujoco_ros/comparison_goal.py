#!/usr/bin/env python3
"""Preview or publish one stamped multi-joint comparison pose from the PC."""

import argparse
import math
from pathlib import Path
import time

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_srvs.srv import SetBool
import yaml

from .hardware_interface import load_joint_config


START_TOLERANCE = 0.15
STATE_TIMEOUT = 0.5
REQUIRED_SUBSCRIBERS = {"arm_io", "mujoco_ros_bridge", "real_sim_comparator"}


def load_poses(path, config):
    """Validate both poses before a caller can publish either one."""
    raw = yaml.safe_load(Path(path).read_text())
    if raw["joint_names"] != config.joint_names:
        raise ValueError("comparison_poses.yaml의 관절 순서를 확인하세요.")
    poses = {}
    for label in ("A", "B"):
        values = [float(value) for value in raw["poses"][label]]
        if len(values) != len(config.joint_names):
            raise ValueError(f"자세 {label}의 관절값 개수를 확인하세요.")
        for name, value in zip(config.joint_names, values):
            lower, upper = config.limit_rad[name]
            if not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f"자세 {label}: {name} 목표가 범위를 벗어났습니다.")
        poses[label] = dict(zip(config.joint_names, values))
    return poses


class ComparisonGoal(Node):
    """Check state/discovery, turn follow off, and publish exactly one goal."""

    def __init__(self):
        super().__init__("comparison_goal")
        self.latest = {}
        self.received_at = {}
        self.publisher = self.create_publisher(JointState, "/joint_targets", 10)
        self.subscriptions_to_states = [
            self.create_subscription(
                JointState, f"/{kind}/joint_states",
                lambda message, kind=kind: self.on_state(kind, message), 10
            )
            for kind in ("real", "sim")
        ]
        self.follow_client = self.create_client(SetBool, "/sim/set_follow_real")

    def on_state(self, kind, message):
        if len(message.name) != len(message.position):
            return
        self.latest[kind] = dict(zip(message.name, message.position))
        self.received_at[kind] = time.monotonic()

    def wait_ready(self, names):
        # Let the comparator collect pre-command history even when this helper
        # is launched immediately after discovery.
        first_ready = None
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            now = time.monotonic()
            subscribers = {
                info.node_name
                for info in self.get_subscriptions_info_by_topic("/joint_targets")
            }
            ready = REQUIRED_SUBSCRIBERS <= subscribers and all(
                kind in self.latest
                and now - self.received_at[kind] < STATE_TIMEOUT
                and all(
                    name in self.latest[kind]
                    and math.isfinite(self.latest[kind][name]) for name in names
                )
                for kind in ("real", "sim")
            )
            if ready:
                first_ready = first_ready or now
                if now - first_ready >= 2.0:
                    return
            else:
                first_ready = None
        raise RuntimeError("3개 구독 노드와 최신 실제·시뮬레이션 6관절 상태가 필요합니다.")

    def send_pose(self, label, poses, names):
        self.wait_ready(names)
        if not self.follow_client.wait_for_service(timeout_sec=2.0):
            raise RuntimeError("추종 OFF Service를 찾지 못했습니다.")
        request = SetBool.Request()
        request.data = False
        future = self.follow_client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=3.0)
        if not future.done() or future.result() is None or not future.result().success:
            raise RuntimeError("추종 OFF 성공을 확인하지 못해 목표를 보내지 않습니다.")
        # Re-check discovery and fresh state after the service round trip.
        self.wait_ready(names)
        if label == "B":
            for kind in ("real", "sim"):
                far = [name for name in names if abs(
                    self.latest[kind][name] - poses["A"][name]
                ) > START_TOLERANCE]
                if far:
                    raise RuntimeError(
                        f"{kind} 시작 자세가 A와 다릅니다: {', '.join(far)}. "
                        "A 준비와 기록 종료 후 sync_to_real을 먼저 수행하세요."
                    )
        message = JointState()
        message.name = list(names)
        message.position = [poses[label][name] for name in names]
        message.header.stamp = self.get_clock().now().to_msg()
        self.publisher.publish(message)
        self.get_logger().info(f"Published pose {label} once with PC timestamp")
        end = time.monotonic() + 0.5
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.05)


def main(args=None):
    parser = argparse.ArgumentParser(description="자세 미리보기 / 공통 목표 1회 발행")
    parser.add_argument("--pose", choices=("A", "B"), required=True)
    parser.add_argument("--send", action="store_true", help="지정할 때만 실제 ROS 목표 발행")
    parsed, ros_args = parser.parse_known_args(args)
    share = Path(get_package_share_directory("week09_mujoco_ros"))
    config = load_joint_config(str(share / "config/joints.yaml"))
    poses = load_poses(share / "config/comparison_poses.yaml", config)
    print("joint                 A [rad]   B [rad]   |B-A| [deg]")
    for name in config.joint_names:
        delta = math.degrees(abs(poses["B"][name] - poses["A"][name]))
        print(f"{name:20s} {poses['A'][name]:8.2f} {poses['B'][name]:9.2f} {delta:12.1f}")
    if not parsed.send:
        print("Preview only. --send를 추가해야 목표를 발행합니다.")
        return
    rclpy.init(args=ros_args)
    node = ComparisonGoal()
    try:
        node.send_pose(parsed.pose, poses, config.joint_names)
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
