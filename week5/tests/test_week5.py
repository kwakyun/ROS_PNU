"""Behavioral tests with ROS doubles and a fake cable; never opens real hardware."""

import csv
import importlib
import math
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("MPLBACKEND", "Agg")
ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "week05_joint_control"
sys.path.insert(0, str(PACKAGE))


class JointState:
    def __init__(self, name=None, position=None):
        self.name = [] if name is None else list(name)
        self.position = [] if position is None else list(position)
        self.header = SimpleNamespace(stamp=None)


class Node:
    def __init__(self, name):
        self.name = name
        self.logger = MagicMock()
        self.create_publisher = MagicMock()
        self.create_subscription = MagicMock()
        self.create_timer = MagicMock()
        self.destroy_node = MagicMock()

    def get_logger(self):
        return self.logger

    def get_clock(self):
        return SimpleNamespace(now=lambda: SimpleNamespace(to_msg=lambda: "stamp"))


def module(name, **kwargs):
    value = ModuleType(name)
    value.__dict__.update(kwargs)
    return value


ROS = module("rclpy", init=MagicMock(), shutdown=MagicMock(),
             ok=MagicMock(return_value=True), spin=MagicMock())
ROS_MODULES = {
    "rclpy": ROS,
    "rclpy.node": module("rclpy.node", Node=Node),
    "rclpy.qos": module("rclpy.qos", QoSProfile=lambda **kwargs: SimpleNamespace(**kwargs)),
    "rclpy.executors": module("rclpy.executors", SingleThreadedExecutor=MagicMock(),
                              ExternalShutdownException=type("ExternalShutdownException", (Exception,), {})),
    "sensor_msgs": module("sensor_msgs"),
    "sensor_msgs.msg": module("sensor_msgs.msg", JointState=JointState),
    "std_msgs": module("std_msgs"),
    "std_msgs.msg": module("std_msgs.msg", Bool=SimpleNamespace),
    "ament_index_python": module("ament_index_python"),
    "ament_index_python.packages": module("ament_index_python.packages",
                                          get_package_share_directory=lambda _: str(PACKAGE)),
}


def setUpModule():
    global patches, hardware, controller, plotter
    patches = patch.dict(sys.modules, ROS_MODULES)
    patches.start()
    hardware = importlib.import_module("week05_joint_control.hardware_interface")
    controller = importlib.import_module("week05_joint_control.joint_controller")
    plotter = importlib.import_module("week05_joint_control.joint_plotter")


def tearDownModule():
    patches.stop()
    sys.path.remove(str(PACKAGE))


def config():
    return hardware.load_joint_config(str(PACKAGE / "config/joints.yaml"))


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.bus = MagicMock()
        self.bus.config = config()
        self.bus.read_positions.return_value = [0.0] * 6
        self.clock = 100.0
        self.timer = patch.object(controller, "time", SimpleNamespace(monotonic=lambda: self.clock))
        self.timer.start()
        self.addCleanup(self.timer.stop)
        self.node = controller.JointPositionController(self.bus)

    def enable(self):
        self.node._read_and_publish_state()
        self.node._on_torque(SimpleNamespace(data=True))
        self.node._control_step()

    def target(self, names, positions):
        self.node._on_target(JointState(names, positions))

    def test_ros_wiring_and_timer_rates(self):
        self.node.create_publisher.assert_called_once_with(JointState, "/joint_states", 10)
        calls = self.node.create_subscription.call_args_list
        self.assertEqual(calls[0].args[1:3], ("/joint_targets", self.node._on_target))
        self.assertEqual(calls[0].args[3].depth, 1)
        self.assertEqual(calls[1].args[1:4], ("/safety/torque_enable", self.node._on_torque, 10))
        self.assertEqual([c.args[0] for c in self.node.create_timer.call_args_list], [1/20, 1/30])

    def test_state_is_measured_and_stamped(self):
        self.bus.read_positions.return_value = [0.1] * 6
        self.node._read_and_publish_state()
        msg = self.node._publisher.publish.call_args.args[0]
        self.assertEqual(msg.position, [0.1] * 6)
        self.assertEqual(msg.name, self.bus.config.joint_names)
        self.assertEqual(msg.header.stamp, "stamp")

    def test_torque_callback_does_not_write_and_waits_for_state(self):
        self.node._on_torque(SimpleNamespace(data=True))
        self.bus.write_positions.assert_not_called()
        self.node._control_step()
        self.bus.write_positions.assert_not_called()
        self.assertFalse(self.node._torque_enabled)

    def test_enable_refreshes_pose_and_holds_without_jump(self):
        self.node._read_and_publish_state()
        self.bus.read_positions.return_value = [0.1] * 6
        self.node._on_torque(SimpleNamespace(data=True))
        self.node._control_step()
        self.bus.write_positions.assert_called_once_with([0.1] * 6, 3000, 30)
        self.assertEqual(self.node._target, [0.1] * 6)
        self.assertEqual(self.node._commanded, [0.1] * 6)

    def test_target_while_off_does_not_persist(self):
        self.target(["shoulder_pan"], [0.5])
        self.assertIsNone(self.node._target)
        self.enable()
        self.assertEqual(self.node._target, [0.0] * 6)

    def test_partial_and_multi_joint_updates(self):
        self.enable()
        self.target(["shoulder_pan"], [0.5])
        self.assertEqual(self.node._target, [0.5, 0, 0, 0, 0, 0])
        self.target(["elbow_flex", "wrist_roll"], [0.4, -0.2])
        self.assertEqual(self.node._target, [0.5, 0, 0.4, 0, -0.2, 0])

    def test_invalid_message_is_atomic(self):
        self.enable()
        self.target(["shoulder_pan"], [0.2])
        old = list(self.node._target)
        cases = [([], []), (["shoulder_pan"], []), (["unknown"], [0.1]),
                 (["shoulder_pan", "shoulder_pan"], [0.3, 0.4]),
                 (["elbow_flex", "shoulder_pan"], [0.4, 3.5]),
                 (["shoulder_pan"], [math.nan]), (["shoulder_pan"], [math.inf]),
                 (["shoulder_pan"], [-math.inf])]
        for names, values in cases:
            with self.subTest(names=names, values=values):
                self.target(names, values)
                self.assertEqual(self.node._target, old)

    def test_each_soft_limit_is_inclusive(self):
        self.enable()
        for name, (lo, hi) in self.bus.config.limit_rad.items():
            index = self.bus.config.joint_names.index(name)
            for boundary in (lo, hi):
                self.target([name], [boundary])
                self.assertEqual(self.node._target[index], boundary)
            before = list(self.node._target)
            for outside in (lo - 1e-6, hi + 1e-6):
                self.target([name], [outside])
                self.assertEqual(self.node._target, before)

    def test_interpolation_limits_each_step_both_directions_and_no_overshoot(self):
        self.enable()
        goals = [0.5, -0.5, 0.4, -0.4, 0.3, 0.6]
        self.target(self.bus.config.joint_names, goals)
        for _ in range(100):
            previous = list(self.node._commanded)
            self.clock += 1/30
            self.node._control_step()
            for i, name in enumerate(self.bus.config.joint_names):
                value = self.node._commanded[i]
                self.assertLessEqual(abs(value-previous[i]), self.bus.config.max_vel_rad_s[name]/30 + 1e-12)
                self.assertLessEqual(abs(goals[i]-value), abs(goals[i]-previous[i]) + 1e-12)
        self.assertEqual(self.node._commanded, goals)
        reached = [c for c in self.node.logger.info.call_args_list if "Target reached" in c.args[0]]
        self.assertEqual(len(reached), 1)

    def test_heartbeat_and_explicit_off(self):
        self.enable()
        self.bus.write_positions.reset_mock()
        self.clock += 0.05
        self.node._control_step()
        self.bus.write_positions.assert_not_called()
        self.clock += 0.06
        self.node._control_step()
        self.bus.write_positions.assert_called_once_with([0.0] * 6, 3000, 30)
        self.node._on_torque(SimpleNamespace(data=False))
        self.bus.disable_torque.assert_not_called()
        self.node._control_step()
        self.bus.disable_torque.assert_called_once()
        self.assertIsNone(self.node._target)
        self.bus.write_positions.reset_mock()
        self.clock += 1
        self.node._control_step()
        self.bus.write_positions.assert_not_called()

    def test_read_failure_requests_release_without_hardware_in_state_callback(self):
        self.enable()
        self.bus.read_positions.side_effect = RuntimeError("lost servo")
        self.node._publisher.publish.reset_mock()
        self.node._read_and_publish_state()
        self.node._publisher.publish.assert_not_called()
        self.bus.disable_torque.assert_not_called()
        self.node._control_step()
        self.bus.disable_torque.assert_called_once()
        self.assertFalse(self.node._torque_requested)

    def test_failed_write_cancels_motion_and_requires_new_enable(self):
        self.enable()
        self.target(["shoulder_pan"], [0.5])
        self.bus.write_positions.side_effect = RuntimeError("send failed")
        self.node._control_step()
        self.bus.disable_torque.assert_called_once()
        self.assertFalse(self.node._torque_enabled)
        self.assertIsNone(self.node._commanded)
        self.bus.write_positions.reset_mock()
        self.node._control_step()
        self.bus.write_positions.assert_not_called()

    def test_failed_release_retries_and_blocks_enable(self):
        self.enable()
        self.bus.disable_torque.side_effect = RuntimeError("OFF unconfirmed")
        self.node._on_torque(SimpleNamespace(data=False))
        self.node._control_step()
        self.assertTrue(self.node._release_pending)
        self.node._on_torque(SimpleNamespace(data=True))
        self.assertFalse(self.node._torque_requested)
        self.bus.disable_torque.side_effect = None
        self.node._control_step()
        self.assertFalse(self.node._release_pending)
        self.assertFalse(self.node._torque_enabled)

    def test_main_disables_on_start_and_shutdown_and_closes(self):
        ROS.shutdown.reset_mock()
        with patch.object(controller, "FeetechBus", return_value=self.bus), patch.object(ROS, "spin", side_effect=KeyboardInterrupt):
            controller.main()
        self.assertEqual(self.bus.disable_torque.call_count, 2)
        self.bus.close.assert_called_once()
        ROS.shutdown.assert_called_once()

    def test_startup_failure_still_closes(self):
        ROS.shutdown.reset_mock()
        self.bus.disable_torque.side_effect = RuntimeError("OFF failed")
        with patch.object(controller, "FeetechBus", return_value=self.bus):
            with self.assertRaisesRegex(RuntimeError, "OFF failed"):
                controller.main()
        self.bus.close.assert_called_once()
        ROS.shutdown.assert_called_once()


class SerialCable:
    """Emulate STS status packets while retaining every transmitted instruction."""

    def __init__(self):
        self.packets = []
        self.buffer = bytearray()
        self.closed = False
        self.present = {i: 2048 + 10*i for i in range(1, 7)}
        self.goal = {i: 1000 for i in range(1, 7)}
        self.torque = {i: 1 for i in range(1, 7)}
        self.mode = {i: 0 for i in range(1, 7)}
        self.fail_off = set()
        self.fail_on = set()
        self.bad_goal = False
        self.fail_sync = False

    def reset_input_buffer(self):
        self.buffer.clear()

    def flush(self):
        pass

    @property
    def in_waiting(self):
        return len(self.buffer)

    def write(self, packet):
        packet = list(packet)
        self.packets.append(packet)
        servo_id, instruction = packet[2], packet[4]
        if instruction == 0x83:
            if self.fail_sync:
                return 0
            assert packet[5:7] == [41, 7]
            for start in range(7, len(packet)-1, 8):
                sid = packet[start]
                self.goal[sid] = packet[start+2] + 256*packet[start+3]
            return len(packet)
        error = 0
        data = []
        address = packet[5]
        if instruction == 2:
            if address == 56:
                value = self.present[servo_id]
            elif address == 42:
                value = self.goal[servo_id] + int(self.bad_goal)
            elif address == 33:
                value = self.mode[servo_id]
            else:
                raise AssertionError(f"Unexpected read register: {address}")
            data = [value & 255] if packet[6] == 1 else [value & 255, value >> 8]
        elif instruction == 3:
            assert address == 40, "No phase, mode, ID or EEPROM writes are allowed"
            value = packet[6]
            if (value == 0 and servo_id in self.fail_off) or (value == 1 and servo_id in self.fail_on):
                error = 32
            else:
                self.torque[servo_id] = value
        else:
            raise AssertionError(f"Unexpected instruction: {instruction}")
        reply = [255, 255, servo_id, len(data)+2, error] + data
        reply.append((~sum(reply[2:])) & 255)
        self.buffer.extend(reply)
        return len(packet)

    def read(self, size):
        output = bytes(self.buffer[:size])
        del self.buffer[:size]
        return output

    def close(self):
        self.closed = True


class HardwareTests(unittest.TestCase):
    def setUp(self):
        import serial
        self.cable = SerialCable()
        self.serial_patch = patch.object(serial, "Serial", return_value=self.cable)
        self.serial_patch.start()
        self.addCleanup(self.serial_patch.stop)
        self.bus = hardware.FeetechBus(config())
        self.addCleanup(self.bus.close)

    def test_open_has_no_servo_writes_and_read_conversion_roundtrip(self):
        self.assertEqual(self.cable.packets, [])
        positions = self.bus.read_positions()
        for name, radians, sid in zip(self.bus.config.joint_names, positions, range(1, 7)):
            self.assertEqual(self.bus.rad_to_tick(name, radians), self.cable.present[sid])
        self.assertTrue(all(p[4] == 2 and p[5] == 56 for p in self.cable.packets))

    def test_write_requires_explicit_confirmed_off(self):
        with self.assertRaisesRegex(RuntimeError, "OFF"):
            self.bus.write_positions([0]*6, 3000, 30)
        self.assertEqual(self.cable.packets, [])

    def test_goal_is_written_and_verified_before_any_torque_on(self):
        self.bus.disable_torque()
        positions = self.bus.read_positions()
        self.bus.write_positions(positions, 3000, 30)
        packets = self.cable.packets
        sync = next(i for i,p in enumerate(packets) if p[4] == 0x83)
        on = [i for i,p in enumerate(packets) if p[4:7] == [3,40,1]]
        readback = [i for i,p in enumerate(packets) if p[4:7] == [2,42,2]]
        self.assertEqual(len(on), 6)
        self.assertEqual(len(readback), 6)
        self.assertLess(sync, min(readback))
        self.assertLess(max(readback), min(on))
        self.assertEqual(self.cable.goal, self.cable.present)
        self.assertTrue(all(v == 1 for v in self.cable.torque.values()))

    def test_bad_goal_readback_never_enables(self):
        self.bus.disable_torque()
        self.cable.bad_goal = True
        with self.assertRaisesRegex(RuntimeError, "readback mismatch"):
            self.bus.write_positions([0]*6, 3000, 30)
        self.assertFalse(any(p[4:7] == [3,40,1] for p in self.cable.packets))
        self.assertTrue(all(v == 0 for v in self.cable.torque.values()))

    def test_partial_enable_failure_releases_all(self):
        self.bus.disable_torque()
        self.cable.fail_on = {3}
        with self.assertRaises(RuntimeError):
            self.bus.write_positions([0]*6, 3000, 30)
        self.assertTrue(all(v == 0 for v in self.cable.torque.values()))
        self.assertFalse(self.bus._torque_enabled)

    def test_disable_attempts_all_and_reports_failure(self):
        self.cable.fail_off = {2}
        with self.assertRaisesRegex(RuntimeError, "OFF not confirmed"):
            self.bus.disable_torque()
        off = [p[2] for p in self.cable.packets if p[4:7] == [3,40,0]]
        self.assertEqual(off, list(range(1,7)))
        self.assertFalse(self.bus._off_confirmed)

    def test_sync_send_failure_is_not_reported_as_success(self):
        self.bus.disable_torque()
        self.cable.fail_sync = True
        with self.assertRaises(RuntimeError):
            self.bus.write_positions([0]*6, 3000, 30)
        self.assertFalse(any(p[4:7] == [3,40,1] for p in self.cable.packets))

    def test_wrong_mode_rejected_without_reprogramming(self):
        self.bus.disable_torque()
        self.cable.mode[2] = 1
        with self.assertRaisesRegex(RuntimeError, "position mode"):
            self.bus.write_positions([0]*6, 3000, 30)
        self.assertFalse(any(p[4] == 0x83 for p in self.cable.packets))

    def test_invalid_vector_never_sends_commands(self):
        self.bus.disable_torque()
        self.cable.packets.clear()
        for values in ([0]*5, [math.nan]*6, [math.inf]*6, [10]*6):
            with self.assertRaises(ValueError):
                self.bus.write_positions(values, 3000, 30)
        self.assertEqual(self.cable.packets, [])

    def test_close_only_closes_and_is_idempotent(self):
        self.bus.close()
        self.bus.close()
        self.assertEqual(self.cable.packets, [])
        self.assertTrue(self.cable.closed)


class PlotterAndPackageTests(unittest.TestCase):
    def test_window_close_saves_then_cleans_up(self):
        node = MagicMock()
        node.snapshot.return_value = []
        executor = MagicMock()
        ROS.shutdown.reset_mock()
        with patch.object(plotter, "JointPlotterNode", return_value=node), \
                patch.object(plotter, "SingleThreadedExecutor", return_value=executor), \
                patch.object(plotter.plt, "show"), \
                patch.object(plotter.plt, "fignum_exists", return_value=False):
            plotter.main()
        node.save_results.assert_called_once()
        executor.shutdown.assert_called_once()
        node.destroy_node.assert_called_once()
        ROS.shutdown.assert_called_once()

    def test_export_error_still_cleans_up(self):
        node = MagicMock()
        node.snapshot.return_value = []
        node.save_results.side_effect = OSError("disk full")
        executor = MagicMock()
        ROS.shutdown.reset_mock()
        with patch.object(plotter, "JointPlotterNode", return_value=node), \
                patch.object(plotter, "SingleThreadedExecutor", return_value=executor), \
                patch.object(plotter.plt, "show"), \
                patch.object(plotter.plt, "fignum_exists", return_value=False):
            with self.assertRaisesRegex(OSError, "disk full"):
                plotter.main()
        executor.shutdown.assert_called_once()
        node.destroy_node.assert_called_once()
        ROS.shutdown.assert_called_once()

    def test_ctrl_c_saves_results(self):
        node = MagicMock()
        node.snapshot.return_value = []
        executor = MagicMock()
        with patch.object(plotter, "JointPlotterNode", return_value=node), \
                patch.object(plotter, "SingleThreadedExecutor", return_value=executor), \
                patch.object(plotter.plt, "show"), \
                patch.object(plotter.plt, "pause", side_effect=KeyboardInterrupt):
            plotter.main()
        node.save_results.assert_called_once()
        executor.shutdown.assert_called_once()

    def test_raw_request_remains_visible_after_controller_rejection(self):
        node = plotter.JointPlotterNode()
        node._on_state(JointState(plotter.JOINT_NAMES, [0]*6))
        self.assertTrue(all(math.isnan(node.rows[0][i]) for i in range(2,13,2)))
        node._on_target(JointState(["shoulder_pan"], [3.5]))
        node._on_state(JointState(plotter.JOINT_NAMES, [0.2]*6))
        self.assertEqual(node.rows[-1][1:3], [0.2, 3.5])
        self.assertTrue(math.isnan(node.rows[-1][4]))

    def test_snapshot_is_independent_and_partial_states_ignored(self):
        node = plotter.JointPlotterNode()
        node._on_state(JointState(["shoulder_pan"], [0.2]))
        self.assertEqual(node.rows, [])
        node._on_state(JointState(plotter.JOINT_NAMES, [0]*6))
        copy = node.snapshot()
        copy[0][1] = 99
        self.assertEqual(node.rows[0][1], 0)

    def test_csv_and_png_export_with_synthetic_tracking_data(self):
        node = plotter.JointPlotterNode()
        for index in range(801):
            elapsed = index / 20
            values = [elapsed]
            for joint in range(6):
                measured = min(max(elapsed-2, 0)*0.1, 0.4)
                requested = math.nan if elapsed < 2 else (3.5 if elapsed >= 28 and joint == 0 else 0.4)
                values.extend([measured, requested])
            node.rows.append(values)
        figure, axes, current, requested = plotter.create_plot()
        self.addCleanup(plotter.plt.close, figure)
        figure.suptitle("SIMULATED DATA - software validation only", y=1.0)
        plotter.update_plot(node.snapshot(), axes, current, requested)
        self.assertEqual(len(axes), 6)
        self.assertEqual(list(current[0].get_xdata())[0], 10.0)
        output = ROOT / ".test-build" / "plot-check"
        with patch.object(plotter, "OUTPUT_DIR", str(output)):
            csv_path = node.save_results(figure)
        with csv_path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(len(rows), 802)
        self.assertEqual(len(rows[0]), 13)
        self.assertEqual(rows[0][1:3], ["shoulder_pan_current", "shoulder_pan_requested"])
        png = csv_path.with_name(csv_path.name.replace("joint_log_", "joint_plot_")).with_suffix(".png")
        self.assertEqual(png.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertGreater(png.stat().st_size, 10000)

    def test_config_rejects_invalid_frequencies_and_limits(self):
        import yaml
        raw = yaml.safe_load((PACKAGE / "config/joints.yaml").read_text())
        cases = [{**raw, "heartbeat_hz": 0}, {**raw, "control_hz": math.nan},
                 {**raw, "max_vel_rad_s": {"shoulder_pan": -1}},
                 {**raw, "sign": {"shoulder_pan": 0}}]
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/"bad.yaml"
            for data in cases:
                p.write_text(yaml.safe_dump(data))
                with self.assertRaises(ValueError):
                    hardware.load_joint_config(str(p))

    def test_assignment_sources_match_package(self):
        for p in (ROOT / "source_code").iterdir():
            if p.suffix not in (".py", ".yaml"):
                continue
            dest = PACKAGE / ("config" if p.suffix == ".yaml" else "week05_joint_control") / p.name
            self.assertEqual(p.read_bytes(), dest.read_bytes(), p.name)


if __name__ == "__main__":
    unittest.main()
