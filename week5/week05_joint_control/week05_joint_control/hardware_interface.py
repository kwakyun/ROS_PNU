"""Thread-safe Feetech bus interface adapted from the vendor driver."""

import math
import threading
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
    """Load the QuickRef-compatible flat joint configuration."""
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
        sign={name: int((raw.get("sign") or {}).get(name, 1)) for name in names},
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
    if not names or len(set(names)) != len(names):
        raise ValueError("joint_names must be nonempty and unique")
    if config.servo_type != "sts" or config.ticks_per_rev != 4096:
        raise ValueError("This lab supports STS/STS3215 with 4096 ticks/revolution")
    ids = list(config.servo_id.values())
    if len(set(ids)) != len(ids) or any(i < 0 or i > 253 for i in ids):
        raise ValueError("servo_id must contain unique unicast IDs (0..253)")
    for field in ("publish_hz", "control_hz", "heartbeat_hz"):
        value = getattr(config, field)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{field} must be finite and positive")
    for name in names:
        lower, upper = config.limit_rad[name]
        if not all(math.isfinite(v) for v in (lower, upper)) or lower > upper:
            raise ValueError(f"Invalid limit_rad for {name}")
        if config.sign[name] not in (-1, 1):
            raise ValueError(f"sign must be -1 or 1 for {name}")
        if not math.isfinite(config.zero_offset_rad[name]):
            raise ValueError(f"Invalid zero offset for {name}")
        velocity = config.max_vel_rad_s[name]
        if not math.isfinite(velocity) or velocity <= 0:
            raise ValueError(f"max_vel_rad_s must be finite and positive for {name}")
    return config


class FeetechBus:
    """Own the serial connection used only by the joint controller node."""

    def __init__(self, config: JointConfig) -> None:
        self.config = config
        self.lock = threading.RLock()
        self._port = None
        self._torque_enabled = False
        self._off_confirmed = False
        try:
            from scservo_sdk import COMM_SUCCESS, PortHandler, sms_sts
        except ImportError as exc:
            raise RuntimeError(
                "scservo_sdk가 없습니다. "
                "'python3 -m pip install vassar-feetech-servo-sdk==1.5.0'를 실행하세요."
            ) from exc
        self._success = COMM_SUCCESS
        self._ids = [config.servo_id[name] for name in config.joint_names]
        try:
            self._port = PortHandler(config.device)
            # The bundled SDK opens the port in setBaudRate().
            if not self._port.setBaudRate(config.baudrate):
                raise RuntimeError(f"Cannot open {config.device} at {config.baudrate} baud")
            self._packet = sms_sts(self._port)
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        """Close the SDK connection without changing the torque state."""
        with self.lock:
            if self._port is not None:
                if self._port.is_open:
                    self._port.closePort()
                self._port = None

    def _check(self, servo_id: int, result: int, error: int = 0) -> None:
        if result != self._success or error:
            raise RuntimeError(
                f"servo {servo_id}: {self._packet.getTxRxResult(result)}; "
                f"{self._packet.getRxPacketError(error)}"
            )

    def _require_open(self) -> None:
        if self._port is None:
            raise RuntimeError("Serial port is closed")

    def rad_to_tick(self, name: str, radians: float) -> int:
        """Convert a ROS joint angle to the matching servo tick."""
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
        """Convert a servo tick to a ROS joint angle."""
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
        """Read all positions in configured joint order."""
        with self.lock:
            self._require_open()
            output = []
            for name in self.config.joint_names:
                servo_id = self.config.servo_id[name]
                tick, result, error = self._packet.ReadPos(servo_id)
                self._check(servo_id, result, error)
                if not 0 <= tick <= 4095:
                    raise RuntimeError(f"servo {servo_id}: unexpected position tick {tick}")
                output.append(self.tick_to_rad(name, int(tick)))
            return output

    def write_positions(
        self,
        positions: List[float],
        speed: int,
        acceleration: int,
    ) -> None:
        """Write a complete, already validated target vector."""
        with self.lock:
            self._require_open()
            if len(positions) != len(self.config.joint_names):
                raise ValueError("A complete joint vector is required")
            if not all(math.isfinite(p) for p in positions):
                raise ValueError("Joint positions must be finite")
            command = {
                self.config.servo_id[name]: self.rad_to_tick(name, radians)
                for name, radians in zip(self.config.joint_names, positions)
            }
            if any(tick < 0 or tick > 4095 for tick in command.values()):
                raise ValueError("Joint command is outside STS tick range (0..4095)")
            if not 0 <= speed <= 32767 or not 0 <= acceleration <= 254:
                raise ValueError("Invalid servo speed or acceleration")

            enabling = not self._torque_enabled
            if enabling:
                # Never enable against a previous program's stored target.
                if not self._off_confirmed:
                    raise RuntimeError("Confirm torque OFF before enabling")
                for servo_id in self._ids:
                    mode, result, error = self._packet.read1ByteTxRx(servo_id, 33)
                    self._check(servo_id, result, error)
                    if mode != 0:
                        raise RuntimeError(f"servo {servo_id}: position mode 0 required; ask the instructor")

            group = self._packet.groupSyncWrite
            group.clearParam()
            try:
                for servo_id, tick in command.items():
                    if not self._packet.SyncWritePosEx(servo_id, tick, speed, acceleration):
                        raise RuntimeError(f"Cannot queue servo {servo_id}")
                self._check(254, group.txPacket())
            finally:
                group.clearParam()

            if enabling:
                try:
                    # A successful broadcast send alone does not prove reception.
                    for servo_id, tick in command.items():
                        goal, result, error = self._packet.read2ByteTxRx(servo_id, 42)
                        self._check(servo_id, result, error)
                        if goal != tick:
                            raise RuntimeError(f"servo {servo_id}: initial goal readback mismatch")
                    self._off_confirmed = False
                    for servo_id in self._ids:
                        result, error = self._packet.write1ByteTxRx(servo_id, 40, 1)
                        self._check(servo_id, result, error)
                    self._torque_enabled = True
                except Exception:
                    self.disable_torque()
                    raise

    def disable_torque(self) -> None:
        """Release every servo torque."""
        with self.lock:
            self._require_open()
            self._torque_enabled = False
            self._off_confirmed = False
            failures = []
            # Attempt every servo even when an earlier one fails.
            for servo_id in self._ids:
                try:
                    result, error = self._packet.write1ByteTxRx(servo_id, 40, 0)
                    self._check(servo_id, result, error)
                except Exception as exc:
                    failures.append(str(exc))
            if failures:
                raise RuntimeError("Torque OFF not confirmed: " + "; ".join(failures))
            self._off_confirmed = True
