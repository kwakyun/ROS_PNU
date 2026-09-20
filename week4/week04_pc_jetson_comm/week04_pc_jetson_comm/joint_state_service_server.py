#!/usr/bin/env python3
"""Serve the latest Jetson joint positions through Trigger."""

import math
from typing import Optional

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger

from .qos import joint_state_qos


def format_joint_state(message: JointState) -> str:
    """Convert measured positions into a readable response string."""
    if not message.name or len(message.name) != len(message.position):
        return ""
    return " | ".join(
        f"{name}={float(position):+.4f} rad "
        f"({math.degrees(float(position)):+.2f} deg)"
        for name, position in zip(message.name, message.position)
    )


class JointStateServiceServer(Node):
    """Cache /joint_states and answer remote Trigger requests."""

    def __init__(self) -> None:
        super().__init__("joint_state_service_server")
        self._latest: Optional[JointState] = None

        self.declare_parameter("reliability", "best_effort")
        reliability = str(self.get_parameter("reliability").value)
        self._subscription = self.create_subscription(
            JointState, "/joint_states", self._on_state,
            joint_state_qos(reliability),
        )

        self._service = self.create_service(
            Trigger,
            "/get_joint_state",
            self._on_request,
        )

    def _on_state(self, message: JointState) -> None:
        self._latest = message

    def _on_request(
        self,
        _request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        latest = self._latest
        if latest is None:
            response.success = False
            response.message = "Jetson이 아직 /joint_states를 수신하지 못했습니다."
            return response

        formatted = format_joint_state(latest)
        if not formatted:
            response.success = False
            response.message = "수신한 JointState의 이름과 위치 배열이 올바르지 않습니다."
            return response
        response.success = True
        response.message = formatted
        return response


def main(args=None) -> None:
    """Run the Jetson Trigger service server."""
    rclpy.init(args=args)
    node = JointStateServiceServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
