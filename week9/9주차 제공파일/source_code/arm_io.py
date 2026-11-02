#!/usr/bin/env python3
"""Read the real arm, publish its state, and apply ROS 2 joint targets."""

import math
import signal
import time
from typing import Dict, List, Optional

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import JointState
from std_srvs.srv import SetBool

from .hardware_interface import FeetechBus, JointConfig, load_joint_config


JOINT_STATE_TOPIC = "/real/joint_states"
JOINT_TARGET_TOPIC = "/joint_targets"
TORQUE_SERVICE = "/robot/set_torque"
WRITE_SPEED = 3000
WRITE_ACCELERATION = 30


class ArmIoNode(Node):
    """Own one servo bus and expose it through simple ROS 2 interfaces."""

    def __init__(self, bus: FeetechBus, config: JointConfig) -> None:
        super().__init__("arm_io")
        self._bus = bus
        self._config = config

        self._measured: Optional[List[float]] = None
        self._commanded: Optional[List[float]] = None
        self._targets: Dict[str, float] = {}
        self._torque_enabled = False
        self._moving_to_target = False
        self._last_write_time = 0.0

        # 이전 프로그램이 토크를 켠 채 종료되었을 수도 있으므로 실제 하드웨어에
        # 해제 명령을 보내고 나서 ROS 인터페이스를 시작한다.
        try:
            self._bus.disable_torque()
        except Exception as exc:
            raise RuntimeError(f"시작 시 토크 해제 실패: {exc}") from exc

        self._state_publisher = self.create_publisher(
            JointState,
            JOINT_STATE_TOPIC,
            10,
        )
        self._target_subscription = self.create_subscription(
            JointState,
            JOINT_TARGET_TOPIC,
            self._on_target,
            10,
        )
        self._torque_service = self.create_service(
            SetBool,
            TORQUE_SERVICE,
            self._on_set_torque,
        )

        # 상태 읽기와 목표 쓰기는 서로 다른 주기로 실행된다.
        self._read_timer = self.create_timer(
            1.0 / self._config.publish_hz,
            self._read_and_publish,
        )
        self._control_timer = self.create_timer(
            1.0 / self._config.control_hz,
            self._control_step,
        )

        self.get_logger().info(
            f"Publishing measured positions on {JOINT_STATE_TOPIC}"
        )
        self.get_logger().info(
            f"Subscribing to targets on {JOINT_TARGET_TOPIC}"
        )
        self.get_logger().info(f"Torque service: {TORQUE_SERVICE}")
        self.get_logger().warning("Servo torque is disabled on startup")

    def _read_and_publish(self) -> None:
        """Read every servo and publish one JointState message."""
        try:
            self._measured = self._bus.read_positions()
        except Exception as exc:
            self.get_logger().error(f"관절값 읽기 실패: {exc}")
            return

        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = list(self._config.joint_names)
        message.position = list(self._measured)
        self._state_publisher.publish(message)

    def _on_set_torque(
        self,
        request: SetBool.Request,
        response: SetBool.Response,
    ) -> SetBool.Response:
        """Turn all servo torque on or off."""
        if request.data:
            if self._torque_enabled:
                response.success = True
                response.message = "실제 로봇 토크가 이미 켜져 있습니다."
                return response
            if self._measured is None:
                response.success = False
                response.message = (
                    "현재 관절값을 아직 읽지 못해 토크를 켤 수 없습니다."
                )
                return response

            # 토크를 켤 때 현재 자세를 첫 목표로 사용한다. 갑작스러운 이동을
            # 방지하고 현재 자세에서 그대로 힘이 들어가게 하기 위한 처리다.
            try:
                self._measured = self._bus.enable_torque_at_current_pose(
                    WRITE_SPEED,
                    WRITE_ACCELERATION,
                )
            except Exception as exc:
                response.success = False
                response.message = f"토크 활성화 실패: {exc}"
                self.get_logger().error(response.message)
                return response

            self._commanded = list(self._measured)
            self._targets = dict(
                zip(self._config.joint_names, self._measured)
            )
            self._torque_enabled = True
            self._moving_to_target = False
            self._last_write_time = time.monotonic()
            response.success = True
            response.message = "현재 자세를 유지하며 실제 로봇 토크를 켰습니다."
            self.get_logger().info(response.message)
            return response

        if not self._torque_enabled:
            response.success = True
            response.message = "실제 로봇 토크가 이미 꺼져 있습니다."
            return response

        try:
            self._bus.disable_torque()
        except Exception as exc:
            response.success = False
            response.message = f"토크 해제 실패: {exc}"
            self.get_logger().error(response.message)
            return response

        self._torque_enabled = False
        self._commanded = None
        self._targets.clear()
        self._moving_to_target = False
        response.success = True
        response.message = "실제 로봇 토크를 해제했습니다."
        self.get_logger().warning(response.message)
        return response

    def _on_target(self, message: JointState) -> None:
        """Validate a full or partial JointState target and save it."""
        if not self._torque_enabled:
            self.get_logger().warning(
                "토크가 꺼져 있어 /joint_targets 명령을 무시합니다."
            )
            return
        if not message.name or len(message.name) != len(message.position):
            self.get_logger().error("name과 position 배열을 확인하세요.")
            return
        if len(set(message.name)) != len(message.name):
            self.get_logger().error("같은 관절 이름을 중복해서 보낼 수 없습니다.")
            return

        accepted: Dict[str, float] = {}
        for name, raw_position in zip(message.name, message.position):
            if name not in self._config.joint_names:
                self.get_logger().error(f"알 수 없는 관절 이름: {name}")
                return
            position = float(raw_position)
            lower, upper = self._config.limit_rad[name]
            if not math.isfinite(position) or not lower <= position <= upper:
                self.get_logger().error(
                    f"{name}={position:.4f} rad 명령 거부; "
                    f"허용 범위=[{lower:.4f}, {upper:.4f}] rad"
                )
                return
            accepted[name] = position

        # 일부 관절만 들어오면 나머지 관절은 기존 목표를 유지한다.
        self._targets.update(accepted)
        self._moving_to_target = True
        values = ", ".join(
            f"{name}={position:.3f}" for name, position in accepted.items()
        )
        self.get_logger().info(f"Accepted real-arm target: {values} rad")

    def _control_step(self) -> None:
        """Move the saved command toward the target within velocity limits."""
        if not self._torque_enabled or self._commanded is None:
            return

        target = [
            self._targets.get(name, self._commanded[index])
            for index, name in enumerate(self._config.joint_names)
        ]
        now = time.monotonic()
        heartbeat_period = 1.0 / self._config.heartbeat_hz
        if (
            not self._moving_to_target
            and now - self._last_write_time < heartbeat_period
        ):
            return

        # 한 제어 주기에 이동할 수 있는 최대 각도만큼 목표에 접근한다.
        dt = 1.0 / self._config.control_hz
        next_command: List[float] = []
        for index, name in enumerate(self._config.joint_names):
            current = self._commanded[index]
            difference = target[index] - current
            max_step = self._config.max_vel_rad_s[name] * dt
            step = max(-max_step, min(max_step, difference))
            next_command.append(current + step)

        try:
            self._bus.write_positions(
                next_command,
                WRITE_SPEED,
                WRITE_ACCELERATION,
            )
        except Exception as exc:
            self.get_logger().error(f"관절 목표 쓰기 실패: {exc}")
            return

        self._commanded = next_command
        self._last_write_time = now
        reached = all(
            abs(goal - command) <= 1.0e-9
            for goal, command in zip(target, next_command)
        )
        if reached and self._moving_to_target:
            self._moving_to_target = False
            self.get_logger().info("목표 명령에 도달해 현재 목표를 유지합니다.")

    def stop(self) -> None:
        """Release torque before closing the serial connection."""
        try:
            # 쓰기 도중의 부분 실패에서는 내부 bool과 실제 토크가 다를 수 있다.
            self._bus.disable_torque()
            if rclpy.ok():
                self.get_logger().warning("종료 전에 실제 로봇 토크를 해제했습니다.")
            else:
                print("종료 전에 실제 로봇 토크를 해제했습니다.", flush=True)
        except Exception as exc:
            message = f"종료 중 토크 해제 실패: {exc}"
            if rclpy.ok():
                self.get_logger().error(message)
            else:
                print(message, flush=True)
        finally:
            self._bus.close()


def main(args=None) -> None:
    """Load the joint configuration and run one ArmIoNode."""
    rclpy.init(args=args)
    bus = None
    node = None
    try:
        config_path = (
            get_package_share_directory("week09_mujoco_ros")
            + "/config/joints.yaml"
        )
        config = load_joint_config(config_path)
        bus = FeetechBus(config)
        node = ArmIoNode(bus, config)
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # 중복 SIGINT가 Viewer·ROS·시리얼 정리를 중단하지 않도록 한다.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            if node is not None:
                node.stop()
            elif bus is not None:
                # 노드 초기화에 실패한 경우에도 시리얼 포트를 정리한다.
                try:
                    bus.disable_torque()
                finally:
                    bus.close()
        finally:
            if node is not None:
                node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()


if __name__ == "__main__":
    main()
