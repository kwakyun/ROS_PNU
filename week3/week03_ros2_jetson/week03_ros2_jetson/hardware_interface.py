"""Small read-only Feetech interface derived from the vendor driver."""

import math
from dataclasses import dataclass
from typing import Dict, List

import yaml


@dataclass
class JointConfig:
    """Joint and serial-bus configuration."""

    joint_names: List[str]
    servo_id: Dict[str, int]
    sign: Dict[str, int]
    zero_offset_rad: Dict[str, float]
    device: str
    baudrate: int
    publish_hz: float
    ticks_per_rev: int
    center_tick: int
    servo_type: str


def load_joint_config(path: str) -> JointConfig:
    """Load the subset of joints.yaml needed in this exercise."""
    with open(path, "r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}

    names = list(raw["joint_names"])
    sign = {name: int((raw.get("sign") or {}).get(name, 1)) for name in names}
    zero = {
        name: float((raw.get("zero_offset_rad") or {}).get(name, 0.0))
        for name in names
    }
    feetech = raw.get("feetech") or {}
    servo_type = str(feetech.get("model", "sts")).lower()
    if "sts" in servo_type or "3215" in servo_type:
        servo_type = "sts"

    return JointConfig(
        joint_names=names,
        servo_id={name: int(raw["servo_id"][name]) for name in names},
        sign=sign,
        zero_offset_rad=zero,
        device=str(raw.get("device", "/dev/ttyACM0")),
        baudrate=int(raw.get("baudrate", 1000000)),
        publish_hz=float(raw.get("publish_hz", 20.0)),
        ticks_per_rev=int(feetech.get("ticks_per_rev", 4096)),
        center_tick=int(feetech.get("center_tick", 2048)),
        servo_type=servo_type,
    )


class FeetechReader:
    """Own one SDK connection and convert servo ticks to radians."""

    def __init__(self, config: JointConfig) -> None:
        try:
            from vassar_feetech_servo_sdk import ServoController
        except ImportError as exc:
            raise RuntimeError(
                "vassar_feetech_servo_sdk가 없습니다. "
                "'pip install vassar-feetech-servo-sdk'를 실행하세요."
            ) from exc

        self._config = config
        self._controller = ServoController(
            servo_ids=[config.servo_id[name] for name in config.joint_names],
            servo_type=config.servo_type,
            port=config.device,
            baudrate=config.baudrate,
        )
        self._controller.connect()

    def close(self) -> None:
        """Disconnect the serial bus."""
        if self._controller is not None:
            self._controller.disconnect()
            self._controller = None

    def _tick_to_rad(self, name: str, tick: int) -> float:
        config = self._config
        shifted = (
            (tick - config.center_tick)
            * (2.0 * math.pi)
            / config.ticks_per_rev
        )
        return shifted * config.sign[name] + config.zero_offset_rad[name]

    def read_positions(self) -> List[float]:
        """Read every configured servo and return positions in joint order."""
        ticks = self._controller.read_all_positions()
        positions = []
        for name in self._config.joint_names:
            servo_id = self._config.servo_id[name]
            if servo_id not in ticks:
                raise RuntimeError(f"servo id {servo_id}의 응답이 없습니다.")
            positions.append(self._tick_to_rad(name, int(ticks[servo_id])))
        return positions
