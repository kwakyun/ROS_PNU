"""ROS-free behavioral checks. Run: python -m unittest discover -s week4/tests -v."""

import importlib
import math
from pathlib import Path
import runpy
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "week04_pc_jetson_comm"
NAME = "week04_pc_jetson_comm"


class JointState:
    def __init__(self):
        self.header = SimpleNamespace(stamp=None)
        self.name = []
        self.position = []


class Node:
    overrides = {}

    def __init__(self, name):
        self.name = name
        self.parameters = {}
        self.logger = MagicMock()
        self.create_publisher = MagicMock()
        self.create_subscription = MagicMock()
        self.create_service = MagicMock()
        self.create_client = MagicMock()
        self.create_timer = MagicMock()
        self.destroyed = False

    def declare_parameter(self, name, default):
        self.parameters[name] = self.overrides.get(name, default)

    def get_parameter(self, name):
        return SimpleNamespace(value=self.parameters[name])

    def get_logger(self):
        return self.logger

    def get_clock(self):
        return SimpleNamespace(now=lambda: SimpleNamespace(to_msg=lambda: "stamp"))

    def destroy_node(self):
        self.destroyed = True


def module(name, **attributes):
    result = ModuleType(name)
    result.__dict__.update(attributes)
    return result


class Week4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        trigger = SimpleNamespace(
            Request=type("Request", (), {}),
            Response=lambda: SimpleNamespace(success=False, message=""),
        )
        cls.ros = module("rclpy", spin_until_future_complete=MagicMock())
        cls.modules = patch.dict(sys.modules, {
            "rclpy": cls.ros,
            "rclpy.node": module("rclpy.node", Node=Node),
            "rclpy.qos": module(
                "rclpy.qos", QoSProfile=lambda **kwargs: SimpleNamespace(**kwargs),
                QoSReliabilityPolicy=SimpleNamespace(BEST_EFFORT=1, RELIABLE=2),
            ),
            "sensor_msgs": module("sensor_msgs"),
            "sensor_msgs.msg": module("sensor_msgs.msg", JointState=JointState),
            "std_srvs": module("std_srvs"),
            "std_srvs.srv": module("std_srvs.srv", Trigger=trigger),
            "ament_index_python": module("ament_index_python"),
            "ament_index_python.packages": module(
                "ament_index_python.packages",
                get_package_share_directory=lambda _: str(PACKAGE),
            ),
        })
        cls.modules.start()
        sys.path.insert(0, str(PACKAGE))
        for short, filename in (
            ("pub", "joint_state_topic_publisher"),
            ("server", "joint_state_service_server"),
            ("client", "joint_state_service_client"),
            ("listener", "joint_state_topic_listener"),
            ("hardware", "hardware_interface"),
            ("qos", "qos"),
        ):
            setattr(cls, short, importlib.import_module(f"{NAME}.{filename}"))

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(PACKAGE))
        cls.modules.stop()

    def setUp(self):
        Node.overrides = {}
        self.ros.spin_until_future_complete.reset_mock()

    def state(self, position=math.pi / 2):
        msg = JointState()
        msg.name = ["elbow"]
        msg.position = [position]
        return msg

    def test_qos_modes_and_invalid_input(self):
        for mode, policy in (("best_effort", 1), ("reliable", 2)):
            profile = self.qos.joint_state_qos(mode)
            self.assertEqual((profile.depth, profile.reliability), (10, policy))
        with self.assertRaises(ValueError):
            self.qos.joint_state_qos("typo")

    def test_publisher_rate_stamp_order_and_topic(self):
        with patch.object(self.pub, "FeetechReader") as reader:
            reader.return_value.read_positions.return_value = [0.1] * 6
            node = self.pub.JointStatePublisher()
            self.assertEqual(node.create_timer.call_args.args[0], 0.2)
            self.assertEqual(node.create_publisher.call_args.args[1], "/joint_states")
            node._publish_state()
            msg = node._publisher.publish.call_args.args[0]
            self.assertEqual(msg.header.stamp, "stamp")
            self.assertEqual(msg.name, node._config.joint_names)
            self.assertEqual(msg.position, [0.1] * 6)
            node.destroy_node()
            reader.return_value.close.assert_called_once()
            self.assertTrue(node.destroyed)

    def test_failed_hardware_read_does_not_publish(self):
        with patch.object(self.pub, "FeetechReader") as reader:
            reader.return_value.read_positions.side_effect = RuntimeError("serial lost")
            node = self.pub.JointStatePublisher()
            node._publish_state()
            node._publisher.publish.assert_not_called()
            node.logger.error.assert_called_once()
            node.destroy_node()

    def test_listener_best_effort_and_units(self):
        node = self.listener.JointStateTopicListener()
        args = node.create_subscription.call_args.args
        self.assertEqual(args[1], "/joint_states")
        self.assertEqual((args[3].depth, args[3].reliability), (10, 1))
        args[2](self.state())
        self.assertIn("+90.0deg", node.logger.info.call_args.args[0])

    def test_server_no_data_then_latest_sample(self):
        node = self.server.JointStateServiceServer()
        self.assertEqual(node.create_service.call_args.args[1], "/get_joint_state")
        response = node._on_request(None, SimpleNamespace())
        self.assertFalse(response.success)
        node._on_state(self.state(0.0))
        node._on_state(self.state())
        response = node._on_request(None, SimpleNamespace())
        self.assertTrue(response.success)
        self.assertIn("elbow=+1.5708 rad (+90.00 deg)", response.message)

    def test_server_uses_selected_qos(self):
        for mode, policy in (("best_effort", 1), ("reliable", 2)):
            Node.overrides = {"reliability": mode}
            node = self.server.JointStateServiceServer()
            args = node.create_subscription.call_args.args
            self.assertEqual(args[1], "/joint_states")
            self.assertEqual(args[3].reliability, policy)

    def test_server_rejects_empty_or_mismatched_arrays(self):
        node = self.server.JointStateServiceServer()
        for msg in (JointState(), self.state()):
            msg.position = []
            node._on_state(msg)
            self.assertFalse(node._on_request(None, SimpleNamespace()).success)

    def client_and_future(self):
        node = self.client.JointStateServiceClient()
        node._client.wait_for_service.return_value = True
        future = node._client.call_async.return_value
        future.done.return_value = True
        future.cancelled.return_value = False
        return node, future

    def test_client_discovery_timeout_sends_nothing(self):
        node, _ = self.client_and_future()
        node._client.wait_for_service.return_value = False
        self.assertFalse(node.request_once())
        node._client.wait_for_service.assert_called_once_with(timeout_sec=5.0)
        node._client.call_async.assert_not_called()

    def test_client_one_request_success_and_server_failure(self):
        for success in (True, False):
            node, future = self.client_and_future()
            future.result.return_value = SimpleNamespace(success=success, message="sample")
            self.assertEqual(node.request_once(), success)
            node._client.call_async.assert_called_once()
            self.ros.spin_until_future_complete.assert_called_with(node, future, timeout_sec=5.0)
            logger = node.logger.info if success else node.logger.error
            self.assertIn(f"success={success}: sample", logger.call_args.args[0])

    def test_client_response_timeout_cancels_pending_request(self):
        node, future = self.client_and_future()
        future.done.return_value = False
        self.assertFalse(node.request_once())
        node._client.remove_pending_request.assert_called_once_with(future)
        future.cancel.assert_called_once()
        future.result.assert_not_called()

    def test_client_cancelled_exception_and_missing_response(self):
        node, future = self.client_and_future()
        future.cancelled.return_value = True
        self.assertFalse(node.request_once())
        future.result.assert_not_called()
        for result in (RuntimeError("connection lost"), None):
            node, future = self.client_and_future()
            if isinstance(result, Exception):
                future.result.side_effect = result
            else:
                future.result.return_value = result
            self.assertFalse(node.request_once())

    def test_read_only_sdk_conversion_errors_and_close(self):
        config = self.hardware.load_joint_config(str(PACKAGE / "config/joints.yaml"))
        port = MagicMock(spec=["setBaudRate", "closePort", "is_open"])
        packet = MagicMock(spec=["ReadPos", "getTxRxResult", "getRxPacketError"])
        packet.ReadPos.return_value = (3072, 0, 0)
        with patch.dict(sys.modules, {
            "scservo_sdk": module("scservo_sdk", COMM_SUCCESS=0,
                                  PortHandler=MagicMock(return_value=port),
                                  sms_sts=MagicMock(return_value=packet))
        }):
            reader = self.hardware.FeetechReader(config)
            self.assertEqual(reader.read_positions(), [math.pi / 2] * 6)
            self.assertEqual([call.args[0] for call in packet.ReadPos.call_args_list], list(range(1, 7)))
            config.sign[config.joint_names[0]] = -1
            config.zero_offset_rad[config.joint_names[0]] = 0.25
            self.assertAlmostEqual(reader.read_positions()[0], -math.pi / 2 + 0.25)
            packet.ReadPos.return_value = (0, -6, 0)
            with self.assertRaisesRegex(RuntimeError, "servo 1"):
                reader.read_positions()
            packet.ReadPos.return_value = (0, 0, 32)
            with self.assertRaisesRegex(RuntimeError, "servo 1"):
                reader.read_positions()
            reader.close()
            reader.close()
            port.setBaudRate.assert_called_once_with(1000000)
            port.closePort.assert_called_once()
            with self.assertRaisesRegex(RuntimeError, "closed"):
                reader.read_positions()

    def test_config_rejects_invalid_timing_encoder_and_ids(self):
        import yaml
        raw = yaml.safe_load((PACKAGE / "config/joints.yaml").read_text())
        cases = [
            {**raw, "publish_hz": 0},
            {**raw, "publish_hz": float("nan")},
            {**raw, "feetech": {"ticks_per_rev": 0}},
            {**raw, "servo_id": {name: 254 for name in raw["joint_names"]}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.yaml"
            for data in cases:
                path.write_text(yaml.safe_dump(data))
                with self.assertRaises(ValueError):
                    self.hardware.load_joint_config(str(path))

    def test_real_sdk_emits_only_position_read_packets(self):
        # Exercise the installed SDK with a fake serial cable, including open/close.
        # No SDK method is mocked, so implicit writes would appear in the packets.
        import serial

        class SerialCable:
            def __init__(self, **kwargs):
                self.packets = []
                self.buffer = bytearray()
                self.closed = False

            def reset_input_buffer(self):
                self.buffer.clear()

            def flush(self):
                pass

            @property
            def in_waiting(self):
                return len(self.buffer)

            def write(self, packet):
                self.packets.append(list(packet))
                # STS position 3072, no servo error, valid status checksum.
                reply = [255, 255, packet[2], 4, 0, 0, 12]
                reply.append((~sum(reply[2:])) & 255)
                self.buffer.extend(reply)
                return len(packet)

            def read(self, length):
                data = bytes(self.buffer[:length])
                del self.buffer[:length]
                return data

            def close(self):
                self.closed = True

        cable = SerialCable()
        config = self.hardware.load_joint_config(str(PACKAGE / "config/joints.yaml"))
        with patch.object(serial, "Serial", return_value=cable):
            reader = self.hardware.FeetechReader(config)
            self.assertEqual(cable.packets, [])
            self.assertEqual(reader.read_positions(), [math.pi / 2] * 6)
            reader.close()
        self.assertTrue(cable.closed)
        self.assertEqual(len(cable.packets), 6)
        for servo_id, packet in enumerate(cable.packets, start=1):
            self.assertEqual(packet[:7], [255, 255, servo_id, 4, 2, 56, 2])

    def test_launch_contains_both_nodes_with_same_argument(self):
        fake = {
            "launch": module("launch", LaunchDescription=lambda actions: actions),
            "launch.actions": module("launch.actions", DeclareLaunchArgument=lambda *a, **k: (a, k)),
            "launch.substitutions": module("launch.substitutions", LaunchConfiguration=lambda name: name),
            "launch_ros": module("launch_ros"),
            "launch_ros.actions": module("launch_ros.actions", Node=lambda **kwargs: kwargs),
        }
        with patch.dict(sys.modules, fake):
            actions = runpy.run_path(str(PACKAGE / "launch/jetson_bringup.launch.py"))["generate_launch_description"]()
        self.assertEqual({a["executable"] for a in actions[1:]}, {"joint_state_publisher", "joint_state_server"})
        for node in actions[1:]:
            self.assertEqual(node["parameters"], [{"reliability": "reliability"}])

    def test_completed_sources_match_deployable_package(self):
        for source in (ROOT / "source_code").iterdir():
            if source.suffix == ".yaml":
                destination = PACKAGE / "config" / source.name
            elif source.name.endswith(".launch.py"):
                destination = PACKAGE / "launch" / source.name
            elif source.suffix == ".py":
                destination = PACKAGE / NAME / source.name
            else:
                continue
            self.assertEqual(source.read_bytes(), destination.read_bytes(), source.name)

    def test_manifest_and_console_entry_points(self):
        manifest = ET.parse(PACKAGE / "package.xml").getroot()
        self.assertEqual(manifest.findtext("name"), NAME)
        self.assertEqual(manifest.findtext("export/build_type"), "ament_python")
        self.assertIn("python3-yaml", [e.text for e in manifest.findall("exec_depend")])
        self.assertTrue((PACKAGE / "resource" / NAME).is_file())
        with patch("setuptools.setup") as setup:
            runpy.run_path(str(PACKAGE / "setup.py"))
        entries = setup.call_args.kwargs["entry_points"]["console_scripts"]
        self.assertEqual(len(entries), 4)
        for entry in entries:
            module_name, function = entry.split(" = ")[1].split(":")
            self.assertTrue(callable(getattr(importlib.import_module(module_name), function)))


if __name__ == "__main__":
    unittest.main()
