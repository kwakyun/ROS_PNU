"""Shared QoS for the joint-state publisher and service subscriber."""

from rclpy.qos import QoSProfile, QoSReliabilityPolicy


def joint_state_qos(reliability: str) -> QoSProfile:
    """Return a volatile, keep-last profile with a depth of ten."""
    policies = {
        "best_effort": QoSReliabilityPolicy.BEST_EFFORT,
        "reliable": QoSReliabilityPolicy.RELIABLE,
    }
    if reliability not in policies:
        raise ValueError("reliability must be 'best_effort' or 'reliable'")
    return QoSProfile(depth=10, reliability=policies[reliability])
