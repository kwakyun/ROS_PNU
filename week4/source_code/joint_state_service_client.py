#!/usr/bin/env python3
"""Call the Jetson Trigger service from the PC."""

import sys

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger


class JointStateServiceClient(Node):
    """Request the Jetson's latest joint positions once."""

    def __init__(self) -> None:
        super().__init__("joint_state_service_client")
        self._client = self.create_client(Trigger, "/get_joint_state")

    def request_once(self) -> bool:
        """Wait at most five seconds for discovery and five for one response."""
        if not self._client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error("/get_joint_state 서비스를 5초 안에 찾지 못했습니다.")
            return False

        future = self._client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        if not future.done():
            self._client.remove_pending_request(future)
            future.cancel()
            self.get_logger().error("서비스 응답 대기 시간(5초)을 초과했습니다.")
            return False
        if future.cancelled():
            self.get_logger().error("서비스 요청이 취소되었습니다.")
            return False
        try:
            response = future.result()
        except Exception as exc:
            self.get_logger().error(f"서비스 호출 실패: {exc}")
            return False
        if response is None:
            self.get_logger().error("서비스 응답이 없습니다.")
            return False

        result = f"success={response.success}: {response.message}"
        if response.success:
            self.get_logger().info(result)
        else:
            self.get_logger().error(result)
        return bool(response.success)


def main(args=None) -> None:
    """Run one remote service request."""
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
