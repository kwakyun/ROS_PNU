#!/usr/bin/env python3
"""Record and compare real and MuJoCo joint responses after each target."""

import csv
from collections import deque
from datetime import datetime
import math
import signal
from pathlib import Path
import time
from typing import Deque, Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rclpy  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.executors import ExternalShutdownException  # noqa: E402
from sensor_msgs.msg import JointState  # noqa: E402
import yaml  # noqa: E402


JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]
JOINT_LIMITS = {
    "shoulder_pan": (-1.91986, 1.91986),
    "shoulder_lift": (-1.74533, 1.74533),
    "elbow_flex": (-1.69, 1.69),
    "wrist_flex": (-1.65806, 1.65806),
    "wrist_roll": (-2.74385, 2.84121),
    "gripper": (-0.17453, 1.74533),
}
RECORD_SECONDS = 8.0
SAMPLE_HZ = 50.0
OUTPUT_DIR = Path("~/week9/results").expanduser()
STATE_TIMEOUT = 0.5
HISTORY_SECONDS = 2.0
RESPONSE_THRESHOLD = 0.01
SETTLING_TOLERANCE = 0.03
SETTLING_HOLD_SECONDS = 0.25

Sample = Tuple[float, Dict[str, float]]


class RealSimComparator(Node):
    """Start one comparison recording whenever a target is published."""

    def __init__(self) -> None:
        super().__init__("real_sim_comparator")
        self._latest_real: Dict[str, float] = {}
        self._latest_sim: Dict[str, float] = {}
        self._last_real_time: Optional[float] = None
        self._last_sim_time: Optional[float] = None
        self._recording = False
        self._start_time = 0.0
        self._target: Dict[str, float] = {}
        self._active_joints: List[str] = []
        self._real_samples: List[Sample] = []
        self._sim_samples: List[Sample] = []
        self._real_history: Deque[Sample] = deque()
        self._sim_history: Deque[Sample] = deque()
        self._time_origin = "pc_target_callback"
        self._target_callback_delay = 0.0

        self._target_subscription = self.create_subscription(
            JointState, "/joint_targets", self._on_target, 10
        )
        self._real_subscription = self.create_subscription(
            JointState, "/real/joint_states", self._on_real, 10
        )
        self._sim_subscription = self.create_subscription(
            JointState, "/sim/joint_states", self._on_sim, 10
        )
        self._finish_timer = self.create_timer(0.05, self._check_finish)
        self.get_logger().info(
            "Waiting for /real/joint_states, /sim/joint_states, "
            "and one-shot /joint_targets"
        )

    @staticmethod
    def _message_map(message: JointState) -> Dict[str, float]:
        """Return finite, known name/position pairs from a JointState."""
        if (
            len(message.name) != len(message.position)
            or len(set(message.name)) != len(message.name)
        ):
            return {}
        result: Dict[str, float] = {}
        for name, raw_position in zip(message.name, message.position):
            position = float(raw_position)
            if name in JOINT_NAMES and math.isfinite(position):
                result[name] = position
        return result

    def _on_real(self, message: JointState) -> None:
        """Save the latest real pose and record it during a trial."""
        received = self._message_map(message)
        if not all(name in received for name in JOINT_NAMES):
            return
        now = time.monotonic()
        if self._recording and not self._states_are_fresh(now):
            self._invalidate_trial("상태 수신이 0.5초 이상 끊겼습니다.")
        self._latest_real.update(received)
        self._last_real_time = now
        self._remember(self._real_history, now, self._latest_real)
        if self._recording:
            elapsed = time.monotonic() - self._start_time
            self._real_samples.append((elapsed, dict(self._latest_real)))

    def _on_sim(self, message: JointState) -> None:
        """Save the latest simulation pose and record it during a trial."""
        received = self._message_map(message)
        if not all(name in received for name in JOINT_NAMES):
            return
        now = time.monotonic()
        if self._recording and not self._states_are_fresh(now):
            self._invalidate_trial("상태 수신이 0.5초 이상 끊겼습니다.")
        self._latest_sim.update(received)
        self._last_sim_time = now
        self._remember(self._sim_history, now, self._latest_sim)
        if self._recording:
            elapsed = time.monotonic() - self._start_time
            self._sim_samples.append((elapsed, dict(self._latest_sim)))

    def _on_target(self, message: JointState) -> None:
        """Use one target publication as the trigger for an 8-second trial."""
        if self._recording:
            self._invalidate_trial("기록 중 새 목표가 들어왔습니다.")
            return
        if (
            not message.name
            or len(message.name) != len(message.position)
            or len(set(message.name)) != len(message.name)
        ):
            self.get_logger().error("target의 name/position 형식을 확인하세요.")
            return
        if any(name not in JOINT_NAMES for name in message.name):
            self.get_logger().error("알 수 없는 target 관절 이름입니다.")
            return
        if not all(name in self._latest_real for name in JOINT_NAMES):
            self.get_logger().warning(
                "/real/joint_states의 전체 관절값을 먼저 수신해야 합니다."
            )
            return
        if not all(name in self._latest_sim for name in JOINT_NAMES):
            self.get_logger().warning(
                "/sim/joint_states의 전체 관절값을 먼저 수신해야 합니다."
            )
            return

        if not self._states_are_fresh(time.monotonic()):
            self.get_logger().warning(
                "상태가 오래되어 기록하지 않습니다. 두 상태 Topic 수신을 확인하세요."
            )
            return

        commanded = self._message_map(message)
        if len(commanded) != len(message.name):
            self.get_logger().error("target에는 유한한 관절값만 사용할 수 있습니다.")
            return
        for name, position in commanded.items():
            lower, upper = JOINT_LIMITS[name]
            if not lower <= position <= upper:
                self.get_logger().error(
                    f"{name}={position:.4f} rad는 허용 범위 "
                    f"[{lower:.4f}, {upper:.4f}] 밖입니다."
                )
                return

        now = time.monotonic()
        stamp_ns = (
            message.header.stamp.sec * 1_000_000_000
            + message.header.stamp.nanosec
        )
        start_time = now
        self._time_origin = "pc_target_callback"
        self._target_callback_delay = 0.0
        if stamp_ns:
            age = (self.get_clock().now().nanoseconds - stamp_ns) / 1e9
            if not 0.0 <= age < HISTORY_SECONDS - STATE_TIMEOUT:
                self.get_logger().warning(
                    "목표 시각이 PC 시간과 맞지 않거나 너무 오래되었습니다. "
                    "PC의 comparison_goal로 발행하세요. 기록하지 않습니다."
                )
                return
            start_time = now - age
            self._time_origin = "pc_target_header_stamp"
            self._target_callback_delay = age
        else:
            self.get_logger().warning(
                "목표 timestamp가 0이므로 callback 수신 시각을 사용합니다. "
                "응답 시작이 잘릴 수 있습니다. 비교에는 comparison_goal을 사용하세요."
            )

        real_samples = self._samples_since(self._real_history, start_time)
        sim_samples = self._samples_since(self._sim_history, start_time)
        if not real_samples or not sim_samples:
            self.get_logger().warning(
                "목표 이전 상태가 부족해 기록하지 않습니다. "
                "두 상태가 수신된 뒤 2초 이상 기다리세요."
            )
            return

        # 목표 callback 전에 시뮬레이션이 이미 반응했어도, 목표 발행 이전의
        # 상태를 0초 값으로 사용하고 버퍼에 있는 이후 상태를 함께 보존한다.
        self._target = dict(real_samples[0][1])
        self._target.update(commanded)
        self._active_joints = list(message.name)
        self._real_samples = real_samples
        self._sim_samples = sim_samples
        self._start_time = start_time
        self._recording = True
        self.get_logger().info(
            f"Trial started for {', '.join(self._active_joints)}; "
            f"recording {RECORD_SECONDS:.1f} s"
        )

    @staticmethod
    def _remember(
        history: Deque[Sample], now: float, pose: Dict[str, float]
    ) -> None:
        history.append((now, dict(pose)))
        while history and now - history[0][0] > HISTORY_SECONDS:
            history.popleft()

    @staticmethod
    def _samples_since(history: Deque[Sample], start: float) -> List[Sample]:
        before = [sample for sample in history if sample[0] <= start]
        if not before or start - before[-1][0] >= STATE_TIMEOUT:
            return []
        return [(0.0, dict(before[-1][1]))] + [
            (stamp - start, dict(pose))
            for stamp, pose in history if stamp > start
        ]

    def _states_are_fresh(self, now: float) -> bool:
        return all(
            stamp is not None and 0.0 <= now - stamp < STATE_TIMEOUT
            for stamp in (self._last_real_time, self._last_sim_time)
        )

    def _invalidate_trial(self, reason: str) -> None:
        self._recording = False
        self._real_samples.clear()
        self._sim_samples.clear()
        self.get_logger().warning(
            f"Trial invalid: {reason} 결과를 저장하지 않습니다. "
            "로봇이 정지하고 두 상태가 정상 수신되는지 확인한 뒤 "
            "다른 목표를 한 번만 보내 재실험하세요."
        )

    def _check_finish(self) -> None:
        """Save the trial after the fixed recording time has elapsed."""
        if not self._recording:
            return
        if not self._states_are_fresh(time.monotonic()):
            self._invalidate_trial("상태 수신이 0.5초 이상 끊겼습니다.")
            return
        if time.monotonic() - self._start_time < RECORD_SECONDS:
            return
        self._recording = False
        try:
            self._save_trial()
        except Exception as exc:
            self.get_logger().error(f"결과 저장 실패: {exc}")

    @staticmethod
    def _interpolate(
        samples: List[Sample],
        timeline: np.ndarray,
        joint_name: str,
    ) -> np.ndarray:
        """Put asynchronous ROS samples onto one common timeline."""
        times = []
        values = []
        for sample_time, pose in samples:
            if joint_name in pose:
                times.append(min(sample_time, RECORD_SECONDS))
                values.append(pose[joint_name])
        if not times:
            return np.full_like(timeline, np.nan, dtype=float)
        return np.interp(timeline, times, values)

    @staticmethod
    def _response_delay(
        timeline: np.ndarray,
        values: np.ndarray,
        target: float,
    ) -> Optional[float]:
        """Return when motion first exceeds 0.01 rad from its start."""
        if abs(target - values[0]) < RESPONSE_THRESHOLD:
            return 0.0
        indices = np.flatnonzero(
            np.abs(values - values[0]) >= RESPONSE_THRESHOLD
        )
        if not indices.size:
            return None
        return float(timeline[int(indices[0])])

    @staticmethod
    def _settling_time(
        timeline: np.ndarray,
        values: np.ndarray,
        target: float,
    ) -> Optional[float]:
        """Return when the target tolerance lasts for 0.25 seconds."""
        in_tolerance = np.abs(values - target) <= SETTLING_TOLERANCE
        hold_count = max(
            1, int(math.ceil(SETTLING_HOLD_SECONDS * SAMPLE_HZ))
        )
        for index in range(len(in_tolerance) - hold_count + 1):
            if (
                index + hold_count < len(timeline)
                and timeline[index + hold_count] - timeline[index]
                >= SETTLING_HOLD_SECONDS
                and np.all(in_tolerance[index:index + hold_count + 1])
            ):
                return float(timeline[index])
        return None

    @staticmethod
    def _rounded(value: Optional[float]) -> Optional[float]:
        return None if value is None else round(float(value), 6)

    @staticmethod
    def _delay_gap_ms(
        real_delay: Optional[float],
        sim_delay: Optional[float],
    ) -> Optional[float]:
        if real_delay is None or sim_delay is None:
            return None
        return round((real_delay - sim_delay) * 1000.0, 3)

    @staticmethod
    def _delay_text(value: Optional[float]) -> str:
        return "N/A" if value is None else f"{value * 1000.0:.1f} ms"

    def _save_trial(self) -> None:
        """Write aligned CSV, graph, metrics, and a terminal summary."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = OUTPUT_DIR / f"trial_{timestamp}"
        timeline = np.linspace(
            0.0,
            RECORD_SECONDS,
            int(RECORD_SECONDS * SAMPLE_HZ) + 1,
        )
        real = {
            name: self._interpolate(self._real_samples, timeline, name)
            for name in JOINT_NAMES
        }
        sim = {
            name: self._interpolate(self._sim_samples, timeline, name)
            for name in JOINT_NAMES
        }

        csv_path = stem.with_suffix(".csv")
        headers = ["time_s"]
        for name in JOINT_NAMES:
            headers.extend(
                [f"{name}_target", f"{name}_real", f"{name}_sim"]
            )
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(headers)
            for index, sample_time in enumerate(timeline):
                row = [float(sample_time)]
                for name in JOINT_NAMES:
                    row.extend(
                        [
                            self._target[name],
                            float(real[name][index]),
                            float(sim[name][index]),
                        ]
                    )
                writer.writerow(row)

        metrics = {
            "record_seconds": RECORD_SECONDS,
            "sample_hz": SAMPLE_HZ,
            "time_origin": self._time_origin,
            "target_callback_delay_s": self._rounded(self._target_callback_delay),
            "history_seconds": HISTORY_SECONDS,
            "active_joints": self._active_joints,
            "response_threshold_rad": RESPONSE_THRESHOLD,
            "settling_tolerance_rad": SETTLING_TOLERANCE,
            "settling_hold_seconds": SETTLING_HOLD_SECONDS,
            "joints": {},
        }
        active_squared_errors = []
        delay_gaps = []
        for name in self._active_joints:
            error = real[name] - sim[name]
            active_squared_errors.append(np.square(error))
            real_delay = self._response_delay(
                timeline, real[name], self._target[name]
            )
            sim_delay = self._response_delay(
                timeline, sim[name], self._target[name]
            )
            delay_gap = self._delay_gap_ms(real_delay, sim_delay)
            if delay_gap is not None:
                delay_gaps.append(delay_gap)
            metrics["joints"][name] = {
                "target_rad": round(self._target[name], 6),
                "real_vs_sim_rmse_rad": round(
                    float(np.sqrt(np.mean(np.square(error)))), 6
                ),
                "real_response_delay_s": self._rounded(real_delay),
                "sim_response_delay_s": self._rounded(sim_delay),
                "real_minus_sim_response_delay_ms": delay_gap,
                "real_settling_time_s": self._rounded(
                    self._settling_time(
                        timeline, real[name], self._target[name]
                    )
                ),
                "sim_settling_time_s": self._rounded(
                    self._settling_time(
                        timeline, sim[name], self._target[name]
                    )
                ),
            }

        metrics["overall_real_vs_sim_rmse_rad"] = round(
            float(
                np.sqrt(np.mean(np.concatenate(active_squared_errors)))
            ),
            6,
        )
        metrics["mean_real_minus_sim_response_delay_ms"] = (
            None if not delay_gaps else round(float(np.mean(delay_gaps)), 3)
        )

        metrics_path = Path(f"{stem}_metrics.yaml")
        with metrics_path.open("w", encoding="utf-8") as yaml_file:
            yaml.safe_dump(
                metrics, yaml_file, allow_unicode=True, sort_keys=False
            )

        figure, axes = plt.subplots(3, 2, figsize=(14, 11), sharex=True)
        for axis, name in zip(axes.flat, JOINT_NAMES):
            axis.axhline(
                self._target[name],
                color="black",
                linestyle="--",
                linewidth=1.3,
                label="target",
            )
            axis.plot(timeline, real[name], label="real")
            axis.plot(timeline, sim[name], label="simulation")
            axis.set_title(name)
            axis.set_ylabel("position [rad]")
            axis.grid(True, alpha=0.3)
            axis.legend(loc="best")
        axes[-1, 0].set_xlabel("PC arrival time [s]")
        axes[-1, 1].set_xlabel("PC arrival time [s]")
        figure.suptitle("Target vs real arm vs MuJoCo", fontsize=15)
        figure.tight_layout()
        png_path = stem.with_suffix(".png")
        figure.savefig(png_path, dpi=150)
        plt.close(figure)

        self.get_logger().info(
            f"Trial saved: {csv_path}, {png_path}, {metrics_path}"
        )
        self.get_logger().info(
            "Response delay gap = real - simulation; "
            "positive means real is slower"
        )
        for name in self._active_joints:
            joint_metrics = metrics["joints"][name]
            gap = joint_metrics["real_minus_sim_response_delay_ms"]
            gap_text = "N/A" if gap is None else f"{gap:.1f} ms"
            real_delay = self._delay_text(
                joint_metrics["real_response_delay_s"]
            )
            sim_delay = self._delay_text(
                joint_metrics["sim_response_delay_s"]
            )
            self.get_logger().info(
                f"{name}: "
                f"real={real_delay}, simulation={sim_delay}, "
                f"gap={gap_text}, "
                f"RMSE={joint_metrics['real_vs_sim_rmse_rad']:.6f} rad"
            )


def main(args=None) -> None:
    """Run the automatic comparison recorder."""
    rclpy.init(args=args)
    node = RealSimComparator()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # 중복 SIGINT가 Viewer·ROS·시리얼 정리를 중단하지 않도록 한다.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
