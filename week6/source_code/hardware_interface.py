"""Minimal Feetech servo interface used by the week 6 arm driver."""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import yaml


@dataclass
class JointConfig:
    """Joint limits, conversion values, control rates, and bus settings."""

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
    command_timeout_ms: int
    heartbeat_hz: float
    ticks_per_rev: int
    center_tick: int
    servo_type: str


def load_joint_config(path: str) -> JointConfig:
    """Read joints.yaml and convert each setting to its expected type."""
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
        sign={name: int((raw.get("sign") or {}).get(name, 1)) for name in names},
        zero_offset_rad={
            name: float((raw.get("zero_offset_rad") or {}).get(name, 0.0))
            for name in names
        },
        limit_rad={
            name: (
                float(raw["limit_rad"][name][0]),
                float(raw["limit_rad"][name][1]),
            )
            for name in names
        },
        max_vel_rad_s={
            name: float(raw["max_vel_rad_s"][name]) for name in names
        },
        device=str(raw.get("device", "/dev/ttyACM0")),
        baudrate=int(raw.get("baudrate", 1000000)),
        publish_hz=float(raw.get("publish_hz", 50.0)),
        control_hz=float(raw.get("control_hz", 100.0)),
        command_timeout_ms=int(raw.get("command_timeout_ms", 300)),
        heartbeat_hz=float(raw.get("heartbeat_hz", 10.0)),
        ticks_per_rev=int(feetech.get("ticks_per_rev", 4096)),
        center_tick=int(feetech.get("center_tick", 2048)),
        servo_type=servo_type,
    )


class FeetechBus:
    """Connect to the servos and convert between radians and encoder ticks."""

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
            servo_ids=[config.servo_id[name] for name in config.joint_names],
            servo_type=config.servo_type,
            port=config.device,
            baudrate=config.baudrate,
        )
        self._controller.connect()

    def close(self) -> None:
        """Close the serial connection."""
        if self._controller is not None:
            self._controller.disconnect()
            self._controller = None

    def rad_to_tick(self, name: str, radians: float) -> int:
        """Convert a ROS joint angle to a servo encoder tick."""
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
        """Convert a servo encoder tick to a ROS joint angle."""
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
        """Read every servo and return radians in configured joint order."""
        ticks = self._controller.read_all_positions()
        positions = []
        for name in self.config.joint_names:
            servo_id = self.config.servo_id[name]
            if servo_id not in ticks:
                raise RuntimeError(f"servo id {servo_id} 응답이 없습니다.")
            positions.append(self.tick_to_rad(name, int(ticks[servo_id])))
        return positions

    def write_positions(
        self,
        positions: List[float],
        speed: int,
        acceleration: int,
    ) -> None:
        """Convert a complete radian target and send it to every servo."""
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
                servo_id for servo_id, succeeded in result.items()
                if not succeeded
            ]
            if failures:
                raise RuntimeError(f"servo write 실패: ids={failures}")

    def disable_torque(self) -> None:
        """Release every servo torque."""
        self._controller.disable_all_servos()
