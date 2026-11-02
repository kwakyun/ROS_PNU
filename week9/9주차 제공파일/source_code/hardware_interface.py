"""Small Feetech servo interface adapted from the vendor driver."""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import yaml


@dataclass
class JointConfig:
    """Physical Arm Lite joint and communication settings."""

    joint_names: List[str]
    servo_id: Dict[str, int]
    sign: Dict[str, int]
    zero_offset_rad: Dict[str, float]
    limit_rad: Dict[str, Tuple[float, float]]
    max_vel_rad_s: Dict[str, float]
    device: str
    baudrate: int
    publish_hz: float
    control_hz: float
    heartbeat_hz: float
    ticks_per_rev: int
    center_tick: int
    servo_type: str


def load_joint_config(path: str) -> JointConfig:
    """Load joint and serial settings from joints.yaml."""
    with open(path, "r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}

    names = list(raw["joint_names"])
    feetech = raw.get("feetech") or {}
    servo_type = str(feetech.get("model", "sts")).lower()
    if "sts" in servo_type or "3215" in servo_type:
        servo_type = "sts"

    return JointConfig(
        joint_names=names,
        servo_id={name: int(raw["servo_id"][name]) for name in names},
        sign={
            name: int((raw.get("sign") or {}).get(name, 1))
            for name in names
        },
        zero_offset_rad={
            name: float((raw.get("zero_offset_rad") or {}).get(name, 0.0))
            for name in names
        },
        limit_rad={
            name: (
                float((raw.get("limit_rad") or {})[name][0]),
                float((raw.get("limit_rad") or {})[name][1]),
            )
            for name in names
        },
        max_vel_rad_s={
            name: float((raw.get("max_vel_rad_s") or {}).get(name, 0.3))
            for name in names
        },
        device=str(raw.get("device", "/dev/ttyACM0")),
        baudrate=int(raw.get("baudrate", 1000000)),
        publish_hz=float(raw.get("publish_hz", 20.0)),
        control_hz=float(raw.get("control_hz", 30.0)),
        heartbeat_hz=float(raw.get("heartbeat_hz", 10.0)),
        ticks_per_rev=int(feetech.get("ticks_per_rev", 4096)),
        center_tick=int(feetech.get("center_tick", 2048)),
        servo_type=servo_type,
    )


class FeetechBus:
    """Own the serial connection and convert radians to servo ticks."""

    def __init__(self, config: JointConfig) -> None:
        self.config = config
        try:
            from vassar_feetech_servo_sdk import ServoController
        except ImportError as exc:
            raise RuntimeError(
                "vassar_feetech_servo_sdk가 없습니다. "
                "'pip install vassar-feetech-servo-sdk'를 실행하세요."
            ) from exc

        self._controller = ServoController(
            servo_ids=[
                config.servo_id[name] for name in config.joint_names
            ],
            servo_type=config.servo_type,
            port=config.device,
            baudrate=config.baudrate,
        )
        try:
            self._controller.connect()
        except Exception:
            # connect() 도중 포트가 열린 뒤 예외가 나도 정리를 시도한다.
            try:
                self._controller.disconnect()
            except Exception:
                pass
            self._controller = None
            raise

    def close(self) -> None:
        """Close the SDK connection."""
        if self._controller is not None:
            self._controller.disconnect()
            self._controller = None

    def rad_to_tick(self, name: str, radians: float) -> int:
        """Convert one ROS joint angle to a servo encoder tick."""
        shifted = (
            (radians - self.config.zero_offset_rad[name])
            * self.config.sign[name]
        )
        return int(
            round(
                self.config.center_tick
                + shifted
                * self.config.ticks_per_rev
                / (2.0 * math.pi)
            )
        )

    def tick_to_rad(self, name: str, tick: int) -> float:
        """Convert one servo encoder tick to a ROS joint angle."""
        shifted = (
            (tick - self.config.center_tick)
            * (2.0 * math.pi)
            / self.config.ticks_per_rev
        )
        return (
            shifted * self.config.sign[name]
            + self.config.zero_offset_rad[name]
        )

    def read_positions(self) -> List[float]:
        """Read all servo positions in joint_names order."""
        ticks = self._controller.read_all_positions()
        positions = []
        for name in self.config.joint_names:
            servo_id = self.config.servo_id[name]
            if servo_id not in ticks:
                raise RuntimeError(f"servo id {servo_id}의 응답이 없습니다.")
            positions.append(
                self.tick_to_rad(name, int(ticks[servo_id]))
            )
        return positions

    def write_positions(
        self,
        positions: List[float],
        speed: int,
        acceleration: int,
    ) -> None:
        """Write one complete target vector to all servos."""
        command = {
            self.config.servo_id[name]: self.rad_to_tick(name, radians)
            for name, radians in zip(self.config.joint_names, positions)
        }
        result = self._controller.write_position(
            command,
            speed=speed,
            acceleration=acceleration,
        )
        if isinstance(result, dict):
            failures = [
                servo_id for servo_id, ok in result.items() if not ok
            ]
            if failures:
                raise RuntimeError(f"servo write 실패: ids={failures}")

    def enable_torque_at_current_pose(
        self, speed: int, acceleration: int
    ) -> List[float]:
        """Stage fresh measured goals on every servo before enabling torque."""
        positions = self.read_positions()
        packet = self._controller.packet_handler
        command = {
            self.config.servo_id[name]: self.rad_to_tick(name, position)
            for name, position in zip(self.config.joint_names, positions)
        }
        try:
            for servo_id, target in command.items():
                mode, comm, error = packet.read1ByteTxRx(servo_id, 33)
                if comm != 0 or error != 0 or mode != 0:
                    raise RuntimeError(f"servo {servo_id}: position mode 확인 실패")
                torque, comm, error = packet.read1ByteTxRx(servo_id, 40)
                if comm != 0 or error != 0 or torque != 0:
                    raise RuntimeError(f"servo {servo_id}: torque OFF 확인 실패")
                if not 0 <= target <= 4095:
                    raise ValueError(f"servo {servo_id}: 현재 자세 tick 범위 오류")

            # SDK write_position() enables torque before writing the goals.
            # Its low-level WritePosEx() only writes goal/speed/acceleration.
            for servo_id, target in command.items():
                comm, error = packet.WritePosEx(
                    servo_id, target, speed, acceleration
                )
                if comm != 0 or error != 0:
                    raise RuntimeError(f"servo {servo_id}: 현재 자세 목표 기록 실패")

            # Every servo now has its current pose as the stored target.
            for servo_id in command:
                comm, error = packet.write1ByteTxRx(servo_id, 40, 1)
                if comm != 0 or error != 0:
                    raise RuntimeError(f"servo {servo_id}: torque ON 실패")
        except Exception:
            try:
                self.disable_torque()
            except Exception:
                pass
            raise
        return positions

    def disable_torque(self) -> None:
        """Release every servo torque."""
        self._controller.disable_all_servos()
