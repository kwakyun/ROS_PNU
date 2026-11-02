#!/usr/bin/env python3
"""Connect ROS 2 JointState messages to a MuJoCo arm model."""

from contextlib import nullcontext
import math
import signal
from pathlib import Path
import time
from typing import Dict, Optional

from ament_index_python.packages import get_package_share_directory
import mujoco
import mujoco.viewer
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import JointState
from std_srvs.srv import SetBool, Trigger


JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]
TARGET_TOPIC = "/joint_targets"
REAL_STATE_TOPIC = "/real/joint_states"
SIM_STATE_TOPIC = "/sim/joint_states"
REAL_STATE_TIMEOUT = 0.5
STATE_PUBLISH_HZ = 50.0


class MujocoRosBridge(Node):
    """Step MuJoCo, receive targets, and publish simulated joint states."""

    def __init__(self) -> None:
        super().__init__("mujoco_ros_bridge")
        package_share = Path(
            get_package_share_directory("week09_mujoco_ros")
        )
        model_path = package_share / "models" / "scene.xml"
        if not model_path.is_file():
            raise FileNotFoundError(f"MJCF 파일이 없습니다: {model_path}")

        # Launch에서 Viewer 표시 여부만 선택할 수 있다. Topic과 주기는 수업
        # 전체에서 동일하게 사용하므로 아래 상수로 고정한다.
        self.declare_parameter("show_viewer", True)
        show_viewer = bool(self.get_parameter("show_viewer").value)

        self._model = mujoco.MjModel.from_xml_path(str(model_path))
        self._data = mujoco.MjData(self._model)
        self._joint_ids: Dict[str, int] = {}
        self._actuator_ids: Dict[str, int] = {}
        for name in JOINT_NAMES:
            joint_id = mujoco.mj_name2id(
                self._model, mujoco.mjtObj.mjOBJ_JOINT, name
            )
            actuator_id = mujoco.mj_name2id(
                self._model, mujoco.mjtObj.mjOBJ_ACTUATOR, name
            )
            if joint_id < 0 or actuator_id < 0:
                raise RuntimeError(
                    f"모델에서 joint/actuator '{name}'을 찾지 못했습니다."
                )
            self._joint_ids[name] = int(joint_id)
            self._actuator_ids[name] = int(actuator_id)

        # 처음에는 모델의 현재 qpos를 각 Actuator 목표값으로 사용한다.
        self._target = np.zeros(self._model.nu, dtype=float)
        for name in JOINT_NAMES:
            joint_id = self._joint_ids[name]
            actuator_id = self._actuator_ids[name]
            qpos_index = int(self._model.jnt_qposadr[joint_id])
            self._target[actuator_id] = self._data.qpos[qpos_index]
        self._data.ctrl[:] = self._target
        mujoco.mj_forward(self._model, self._data)

        self._latest_real: Dict[str, float] = {}
        self._last_real_time: Optional[float] = None
        self._follow_real = False
        self._stale_warning_printed = False

        self._viewer: Optional[mujoco.viewer.Handle] = None
        self._viewer_closed_logged = False
        self._last_view_sync = 0.0

        # TODO 3: create_publisher()로 JointState 타입의 "/sim/joint_states"를 생성하고
        # QoS depth 10을 사용하여 self._state_publisher에 저장한다.
        self._state_publisher = self.create_publisher(
            ### TODO ###  메시지 타입
            ### TODO ###  시뮬레이션 상태 Topic
            10,
        )
        # TODO 4: create_subscription()으로 JointState 타입의 "/joint_targets"를 구독하고
        # self._on_target 콜백과 QoS depth 10을 연결하여 self._target_subscription에 저장한다.
        self._target_subscription = self.create_subscription(
            ### TODO ###  메시지 타입
            ### TODO ###  공통 목표 Topic
            ### TODO ###  callback
            10,
        )
        self._real_subscription = self.create_subscription(
            JointState, REAL_STATE_TOPIC, self._on_real_state, 10
        )
        self._sync_service = self.create_service(
            Trigger, "/sim/sync_to_real", self._sync_to_real
        )
        self._follow_service = self.create_service(
            SetBool, "/sim/set_follow_real", self._set_follow_real
        )

        # 학생의 ROS 연결 작업을 마친 뒤에만 Viewer를 연다.
        if show_viewer:
            self._viewer = mujoco.viewer.launch_passive(
                self._model, self._data
            )

        # MuJoCo timestep은 2 ms이다. Timer가 늦게 호출되더라도 누락된 만큼
        # 여러 번 mj_step()하여 시뮬레이션 시간을 실제 시간에 가깝게 맞춘다.
        self._last_wall_time = time.monotonic()
        self._step_accumulator = 0.0
        self._physics_timer = self.create_timer(0.005, self._step_physics)
        self._publish_timer = self.create_timer(
            1.0 / STATE_PUBLISH_HZ, self._publish_state
        )

        self.get_logger().info(
            f"MuJoCo loaded: nq={self._model.nq}, nv={self._model.nv}, "
            f"nu={self._model.nu}, dt={self._model.opt.timestep:.4f} s"
        )
        self.get_logger().info(
            f"{TARGET_TOPIC} -> MuJoCo ctrl, "
            f"publishing {SIM_STATE_TOPIC} at {STATE_PUBLISH_HZ:.1f} Hz"
        )

    @staticmethod
    def _joint_state_map(message: JointState) -> Dict[str, float]:
        """Convert valid JointState name/position pairs to a dictionary."""
        if len(message.name) != len(message.position):
            return {}
        return {
            name: float(position)
            for name, position in zip(message.name, message.position)
            if name in JOINT_NAMES and math.isfinite(float(position))
        }

    def _on_real_state(self, message: JointState) -> None:
        """Save the real pose and copy it to MuJoCo in follow mode."""
        received = self._joint_state_map(message)
        if not received:
            return
        self._latest_real.update(received)
        if all(name in received for name in JOINT_NAMES):
            self._last_real_time = time.monotonic()
            self._stale_warning_printed = False
        if self._follow_real and self._has_complete_real_state():
            self._apply_real_pose(reset_time=False)

    def _on_target(self, message: JointState) -> None:
        """Validate and apply a full or partial simulation target."""
        if self._follow_real:
            self.get_logger().error(
                "실시간 추종 중에는 /joint_targets를 적용하지 않습니다. "
                "먼저 /sim/set_follow_real을 false로 변경하세요."
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
            if name not in self._actuator_ids:
                self.get_logger().error(f"알 수 없는 관절 이름: {name}")
                return
            position = float(raw_position)
            actuator_id = self._actuator_ids[name]
            lower, upper = self._model.actuator_ctrlrange[actuator_id]
            if not math.isfinite(position) or not lower <= position <= upper:
                self.get_logger().error(
                    f"{name}={position:.4f} rad 명령 거부; "
                    f"허용 범위=[{lower:.4f}, {upper:.4f}] rad"
                )
                return
            accepted[name] = position

        for name, position in accepted.items():
            self._target[self._actuator_ids[name]] = position
        values = ", ".join(
            f"{name}={position:.3f}" for name, position in accepted.items()
        )
        self.get_logger().info(f"Accepted simulation target: {values} rad")

    def _has_complete_real_state(self) -> bool:
        return all(name in self._latest_real for name in JOINT_NAMES)

    def _real_state_is_fresh(self) -> bool:
        return (
            self._last_real_time is not None
            and time.monotonic() - self._last_real_time
            <= REAL_STATE_TIMEOUT
        )

    def _viewer_lock(self):
        if self._viewer is None:
            return nullcontext()
        return self._viewer.lock()

    def _bounded_real_position(self, name: str) -> float:
        """Clamp one measured angle to the MuJoCo model limits."""
        joint_id = self._joint_ids[name]
        actuator_id = self._actuator_ids[name]
        joint_lower, joint_upper = self._model.jnt_range[joint_id]
        ctrl_lower, ctrl_upper = self._model.actuator_ctrlrange[actuator_id]
        return float(
            np.clip(
                self._latest_real[name],
                max(joint_lower, ctrl_lower),
                min(joint_upper, ctrl_upper),
            )
        )

    def _apply_real_pose(self, *, reset_time: bool) -> None:
        """Copy the latest complete real pose into MuJoCo qpos and ctrl."""
        with self._viewer_lock():
            if reset_time:
                self._data.time = 0.0
            for name in JOINT_NAMES:
                value = self._bounded_real_position(name)
                joint_id = self._joint_ids[name]
                actuator_id = self._actuator_ids[name]
                qpos_index = int(self._model.jnt_qposadr[joint_id])
                dof_index = int(self._model.jnt_dofadr[joint_id])
                self._data.qpos[qpos_index] = value
                # 실제 로봇 6관절만 동기화하고 자유 큐브의 상태는 덮어쓰지 않는다.
                self._data.qvel[dof_index] = 0.0
                self._target[actuator_id] = value
            self._data.ctrl[:] = self._target
            mujoco.mj_forward(self._model, self._data)

    def _step_physics(self) -> None:
        """Advance MuJoCo in normal mode or hold the copied real pose."""
        now = time.monotonic()
        if self._follow_real:
            self._last_wall_time = now
            self._step_accumulator = 0.0
            if (
                not self._real_state_is_fresh()
                and not self._stale_warning_printed
            ):
                self.get_logger().warning(
                    "/real/joint_states 수신이 끊겨 마지막 MuJoCo 자세를 유지합니다."
                )
                self._stale_warning_printed = True
            self._sync_viewer(now)
            return

        elapsed = min(0.05, max(0.0, now - self._last_wall_time))
        self._last_wall_time = now
        self._step_accumulator += elapsed
        timestep = float(self._model.opt.timestep)
        step_count = min(25, int(self._step_accumulator / timestep))
        if step_count > 0:
            with self._viewer_lock():
                self._data.ctrl[:] = self._target
                for _ in range(step_count):
                    mujoco.mj_step(self._model, self._data)
            self._step_accumulator -= step_count * timestep
        self._sync_viewer(now)

    def _sync_viewer(self, now: float) -> None:
        """Refresh the passive Viewer without stopping ROS callbacks."""
        if self._viewer is None:
            return
        if not self._viewer.is_running():
            if not self._viewer_closed_logged:
                self.get_logger().info(
                    "MuJoCo Viewer가 닫혔지만 시뮬레이션은 계속 실행됩니다."
                )
                self._viewer_closed_logged = True
            self._viewer.close()
            self._viewer = None
        elif now - self._last_view_sync >= 1.0 / 60.0:
            self._viewer.sync()
            self._last_view_sync = now

    def _publish_state(self) -> None:
        """Publish MuJoCo qpos and qvel as sensor_msgs/JointState."""
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = "physicai_arm"
        message.name = list(JOINT_NAMES)
        with self._viewer_lock():
            for name in JOINT_NAMES:
                joint_id = self._joint_ids[name]
                qpos_index = int(self._model.jnt_qposadr[joint_id])
                dof_index = int(self._model.jnt_dofadr[joint_id])
                message.position.append(float(self._data.qpos[qpos_index]))
                message.velocity.append(float(self._data.qvel[dof_index]))
                message.effort.append(
                    float(self._data.qfrc_actuator[dof_index])
                )
        self._state_publisher.publish(message)

    def _set_follow_real(
        self,
        request: SetBool.Request,
        response: SetBool.Response,
    ) -> SetBool.Response:
        """Enable or disable continuous Real-to-Sim pose copying."""
        if request.data:
            if not self._has_complete_real_state():
                missing = [
                    name for name in JOINT_NAMES
                    if name not in self._latest_real
                ]
                response.success = False
                response.message = (
                    "/real/joint_states에서 아직 받지 못한 관절: "
                    + ", ".join(missing)
                )
                return response
            if not self._real_state_is_fresh():
                response.success = False
                response.message = (
                    "/real/joint_states의 관절 상태가 오래되었습니다. "
                    "Topic 수신을 확인하세요."
                )
                return response
            self._follow_real = True
            self._stale_warning_printed = False
            self._apply_real_pose(reset_time=False)
            response.message = "Real-to-Sim 실시간 추종을 시작했습니다."
        else:
            self._follow_real = False
            self._stale_warning_printed = False
            self._last_wall_time = time.monotonic()
            self._step_accumulator = 0.0
            response.message = "Real-to-Sim 실시간 추종을 종료했습니다."

        response.success = True
        self.get_logger().info(response.message)
        return response

    def _sync_to_real(
        self,
        _request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        """Copy the latest real pose to MuJoCo once."""
        if not self._has_complete_real_state():
            missing = [
                name for name in JOINT_NAMES
                if name not in self._latest_real
            ]
            response.success = False
            response.message = (
                "/real/joint_states에서 아직 받지 못한 관절: "
                + ", ".join(missing)
            )
            return response
        if not self._real_state_is_fresh():
            response.success = False
            response.message = (
                "/real/joint_states가 오래되었습니다. Topic 수신을 확인하세요."
            )
            return response

        self._apply_real_pose(reset_time=True)
        self._last_wall_time = time.monotonic()
        self._step_accumulator = 0.0
        response.success = True
        response.message = "MuJoCo 시작 자세를 실제 로봇 자세에 맞췄습니다."
        self.get_logger().info(response.message)
        return response

    def destroy_node(self) -> bool:
        """Close the native Viewer before destroying the ROS node."""
        if self._viewer is not None:
            self._viewer.close()
            self._viewer = None
            # WSLg의 native Viewer 스레드가 종료될 시간을 확보한다.
            time.sleep(1.0)
        return super().destroy_node()


def main(args=None) -> None:
    """Run the ROS–MuJoCo Bridge."""
    rclpy.init(args=args)
    node: Optional[MujocoRosBridge] = None
    try:
        node = MujocoRosBridge()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # 중복 SIGINT가 Viewer·ROS·시리얼 정리를 중단하지 않도록 한다.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
