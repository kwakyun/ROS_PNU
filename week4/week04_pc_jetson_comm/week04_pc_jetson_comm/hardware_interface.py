"""Read STS positions without the high-level controller's automatic writes."""

import math
from dataclasses import dataclass
from typing import Dict, List

import yaml


@dataclass
class JointConfig:
    """Joint names, encoder conversion, and serial-bus settings."""

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
    """Load the read-only settings used by the Week 4 publisher."""
    with open(path, "r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}

    names = list(raw["joint_names"])
    feetech = raw.get("feetech") or {}
    servo_type = str(feetech.get("model", "sts")).lower()
    if "sts" in servo_type or "3215" in servo_type:
        servo_type = "sts"

    config = JointConfig(
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
        device=str(raw.get("device", "/dev/ttyACM0")),
        baudrate=int(raw.get("baudrate", 1000000)),
        publish_hz=float(raw.get("publish_hz", 50.0)),
        ticks_per_rev=int(feetech.get("ticks_per_rev", 4096)),
        center_tick=int(feetech.get("center_tick", 2048)),
        servo_type=servo_type,
    )
    if not names or len(set(names)) != len(names):
        raise ValueError("joint_names must contain unique joint names")
    if config.servo_type != "sts":
        raise ValueError("This lab supports the supplied STS/STS3215 configuration")
    if not math.isfinite(config.publish_hz) or config.publish_hz <= 0:
        raise ValueError("publish_hz must be finite and greater than zero")
    if config.ticks_per_rev <= 0:
        raise ValueError("ticks_per_rev must be greater than zero")
    ids = list(config.servo_id.values())
    if len(set(ids)) != len(ids) or any(i < 0 or i > 253 for i in ids):
        raise ValueError("servo_id values must be unique unicast IDs (0..253)")
    return config


class FeetechReader:
    """Own one SDK connection and read positions without writing commands."""

    def __init__(self, config: JointConfig) -> None:
        try:
            from scservo_sdk import COMM_SUCCESS, PortHandler, sms_sts
        except ImportError as exc:
            raise RuntimeError(
                "scservo_sdk import failed. "
                "Run: python3 -m pip install vassar-feetech-servo-sdk==1.5.0"
            ) from exc

        self._config = config
        self._success = COMM_SUCCESS
        self._port = PortHandler(config.device)
        try:
            # In the bundled SDK, setBaudRate opens the serial port itself.
            if not self._port.setBaudRate(config.baudrate):
                raise RuntimeError(f"Cannot open {config.device} at {config.baudrate} baud")
            self._packet = sms_sts(self._port)
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        """Disconnect the serial bus."""
        if self._port is not None:
            if self._port.is_open:
                self._port.closePort()
            self._port = None

    def _tick_to_rad(self, name: str, tick: int) -> float:
        config = self._config
        shifted = (
            (tick - config.center_tick)
            * (2.0 * math.pi)
            / config.ticks_per_rev
        )
        return shifted * config.sign[name] + config.zero_offset_rad[name]

    def read_positions(self) -> List[float]:
        """Read every configured servo in joint-name order."""
        if self._port is None:
            raise RuntimeError("Serial port is closed")
        positions = []
        for name in self._config.joint_names:
            servo_id = self._config.servo_id[name]
            tick, result, error = self._packet.ReadPos(servo_id)
            if result != self._success:
                raise RuntimeError(
                    f"servo {servo_id}: {self._packet.getTxRxResult(result)}"
                )
            if error:
                raise RuntimeError(
                    f"servo {servo_id}: {self._packet.getRxPacketError(error)}"
                )
            positions.append(self._tick_to_rad(name, int(tick)))
        return positions
