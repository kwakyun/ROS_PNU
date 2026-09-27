#!/usr/bin/env python3
"""Plot and save measured and requested joint positions."""

import csv
from datetime import datetime
import math
from pathlib import Path
import threading
import time
from typing import Dict, List

import matplotlib.pyplot as plt
import rclpy
from rclpy.executors import ExternalShutdownException, SingleThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import JointState


JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]
JOINT_STATES_TOPIC = "/joint_states"
JOINT_TARGETS_TOPIC = "/joint_targets"
WINDOW_SECONDS = 30.0
OUTPUT_DIR = "results"


class JointPlotterNode(Node):
    """Collect current and raw requested samples for the GUI thread."""

    def __init__(self) -> None:
        super().__init__("joint_plotter")
        self.lock = threading.RLock()
        self.start_time = time.monotonic()
        self.requested: Dict[str, float] = {}
        self.rows: List[List[float]] = []
        self.create_subscription(
            JointState,
            JOINT_STATES_TOPIC,
            self._on_state,
            50,
        )
        self.create_subscription(
            JointState,
            JOINT_TARGETS_TOPIC,
            self._on_target,
            50,
        )

    def _on_target(self, message: JointState) -> None:
        """Store raw requests without applying the controller's validation."""
        if len(message.name) != len(message.position):
            return
        with self.lock:
            for name, position in zip(message.name, message.position):
                if name in JOINT_NAMES and math.isfinite(float(position)):
                    self.requested[name] = float(position)

    def _on_state(self, message: JointState) -> None:
        measured = {
            name: float(position)
            for name, position in zip(message.name, message.position)
        }
        if not all(name in measured for name in JOINT_NAMES):
            return
        elapsed = time.monotonic() - self.start_time
        with self.lock:
            row = [elapsed]
            for name in JOINT_NAMES:
                row.extend(
                    [
                        measured[name],
                        self.requested.get(name, math.nan),
                    ]
                )
            self.rows.append(row)

    def snapshot(self) -> List[List[float]]:
        """Return a copy safe for plotting."""
        with self.lock:
            return [list(row) for row in self.rows]

    def save_results(self, figure) -> Path:
        """Save every collected sample and the final figure."""
        output_dir = Path(OUTPUT_DIR).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        csv_path = output_dir / f"joint_log_{stamp}.csv"
        png_path = output_dir / f"joint_plot_{stamp}.png"
        header = ["time_s"]
        for name in JOINT_NAMES:
            header.extend([f"{name}_current", f"{name}_requested"])
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(self.snapshot())
        figure.savefig(png_path, dpi=160)
        self.get_logger().info(f"Saved {csv_path}")
        self.get_logger().info(f"Saved {png_path}")
        return csv_path


def create_plot():
    """Create the six axes and both traces for each joint."""
    figure, axes = plt.subplots(3, 2, figsize=(12, 9), sharex=True)
    axes = list(axes.flat)
    current_lines = []
    requested_lines = []
    for axis, name in zip(axes, JOINT_NAMES):
        current_line, = axis.plot(
            [],
            [],
            label="current",
            color="tab:blue",
            linewidth=1.8,
            zorder=2,
        )
        requested_line, = axis.plot(
            [],
            [],
            "--",
            label="requested",
            color="tab:orange",
            linewidth=2.0,
            zorder=3,
        )
        axis.set_title(name)
        axis.set_ylabel("rad")
        axis.grid(True)
        axis.legend(loc="upper right")
        current_lines.append(current_line)
        requested_lines.append(requested_line)
    axes[-1].set_xlabel("time [s]")
    axes[-2].set_xlabel("time [s]")
    figure.tight_layout()
    return figure, axes, current_lines, requested_lines


def update_plot(rows, axes, current_lines, requested_lines) -> None:
    """Refresh the last 30 seconds while keeping all rows for CSV export."""
    if not rows:
        return
    latest = rows[-1][0]
    visible = [row for row in rows if row[0] >= latest - WINDOW_SECONDS]
    times = [row[0] for row in visible]
    for index, axis in enumerate(axes):
        current_lines[index].set_data(times, [row[1 + index * 2] for row in visible])
        requested_lines[index].set_data(times, [row[2 + index * 2] for row in visible])
        axis.relim()
        axis.autoscale_view()
        axis.set_xlim(max(0.0, latest - WINDOW_SECONDS), max(WINDOW_SECONDS, latest + 0.1))


def main(args=None) -> None:
    """Run ROS callbacks in a worker and Matplotlib in the main thread."""
    rclpy.init(args=args)
    node = None
    executor = None
    ros_thread = None
    figure = None

    def spin_worker():
        try:
            executor.spin()
        except ExternalShutdownException:
            pass

    try:
        node = JointPlotterNode()
        figure, axes, current_lines, requested_lines = create_plot()
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        ros_thread = threading.Thread(target=spin_worker, daemon=True)
        ros_thread.start()
        plt.show(block=False)
        while rclpy.ok() and plt.fignum_exists(figure.number):
            update_plot(node.snapshot(), axes, current_lines, requested_lines)
            figure.canvas.draw_idle()
            plt.pause(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if executor is not None:
                executor.shutdown()
            if ros_thread is not None:
                ros_thread.join(timeout=1.0)
            if node is not None and figure is not None:
                update_plot(node.snapshot(), axes, current_lines, requested_lines)
                node.save_results(figure)
        finally:
            if node is not None:
                node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
            if figure is not None:
                plt.close(figure)


if __name__ == "__main__":
    main()
