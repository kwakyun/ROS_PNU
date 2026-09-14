#!/usr/bin/env python3
"""Call the local Trigger service and print its response."""

import sys

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger


SERVICE_NAME = "/get_joint_state"
WAIT_TIMEOUT_SEC = 5.0


class JointStateServiceClient(Node):
    """Request the latest joint positions from /get_joint_state."""

    def __init__(self) -> None:
        super().__init__("joint_state_service_client")

        # TODO: create_client()를 사용하여 Trigger 서비스 타입으로 "/get_joint_state" 서비스 클라이언트를 생성하시오.
        self._client = self.create_client(Trigger, SERVICE_NAME)
        if not self._client.wait_for_service(timeout_sec=WAIT_TIMEOUT_SEC):
            raise RuntimeError(
                f"{SERVICE_NAME} 서비스를 {WAIT_TIMEOUT_SEC:.1f}초 안에 "
                "찾지 못했습니다."
            )

    def request_once(self) -> bool:
        """Send an empty Trigger request and print the returned string."""
        # TODO: call_async(Trigger.Request())를 사용하여 서비스를 비동기 1회 호출하시오.
        future = self._client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future)
        response = future.result()
        if response is None:
            self.get_logger().error(f"서비스 호출 실패: {future.exception()}")
            return False
        if not response.success:
            self.get_logger().error(response.message)
            return False

        print("[Service response]")
        print(response.message)
        return True


def main(args=None) -> None:
    """Run one local service request."""
    rclpy.init(args=args)
    node = None
    exit_code = 1
    try:
        node = JointStateServiceClient()
        exit_code = 0 if node.request_once() else 1
    except (KeyboardInterrupt, RuntimeError) as exc:
        if node is not None:
            node.get_logger().error(str(exc))
        else:
            print(str(exc), file=sys.stderr)
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
