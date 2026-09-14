#!/usr/bin/env python3
"""Return the latest measured joint positions through Trigger."""

import math
from typing import Optional

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger

class JointStateServiceServer(Node):
    """Cache /joint_states and answer one-shot Trigger requests."""

    def __init__(self) -> None:
        super().__init__("joint_state_service_server")
        self._latest: Optional[JointState] = None
        
        # TODO: "joint_states" topic을 subscribe해서, _latest를 업데이트 하시오. (hint callback function 추가로 정의해서 활용)
        self._subscription = self.create_subscription(
            JointState,
            "/joint_states",
            self._on_joint_state,
            10,
        )

        # TODO: create_service()를 사용하여 Trigger 서비스 타입으로 "/get_joint_state" 서비스를 오픈하고, self._on_request 콜백을 연결하시오.
        self._service = self.create_service(
            Trigger,
            "/get_joint_state",
            self._on_request,
        )

    def _on_joint_state(self, message: JointState) -> None:
        """Cache the latest JointState message."""
        self._latest = message

    def _on_request(
        self,
        request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        del request
        
        # TODO: 서비스 요청 처리가 성공/실패 했을 때 response.success 및 response.message 값을 설정하여 반환하시오.
        if self._latest is None:
            response.success = False
            response.message = "아직 관절 상태를 수신하지 못했습니다."
            return response

        response.success = True
        values = [
            f"{name}={position:+.3f} rad ({math.degrees(position):+.1f} deg)"
            for name, position in zip(self._latest.name, self._latest.position)
        ]
        response.message = " | ".join(values)
        return response


def main(args=None) -> None:
    """Run the local Trigger service server."""
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
