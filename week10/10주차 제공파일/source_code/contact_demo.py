"""Verify that the robot physically moves each free cube using fixed actions.

This optional demonstration uses the original Week 9 cube placement.
Only reset restores the cubes; subsequent motion comes from robot contact.
"""

import argparse
import time

import numpy as np

from .gymnasium_lab_env import GymnasiumLabEnv


CONTACT_CASES = (
    ("green", "cube_position", ((0.275, 0.030), (0.355, 0.030)), 0.8),
    ("blue", "blue_cube_position", (
        (0.200, -0.060), (0.335, -0.060), (0.335, 0.000), (0.400, 0.000)
    ), 1.0),
)


def run_contact_case(environment, case, render=False):
    """Reset, approach one cube and push it with the modeled robot mesh."""
    color, position_key, waypoints, speed = case
    _, info = environment.reset(seed=10)
    if render:
        _show_current_state(environment, 1.0)
    before = info[position_key].copy()
    push_z = float(info["eef_position"][2])
    touched = False
    viewer_closed = False
    for waypoint in waypoints:
        target = np.asarray([*waypoint, push_z])
        for _ in range(60):
            if render and not environment.simulation.viewer_is_running():
                viewer_closed = True
                break
            eef_xyz = info["eef_position"]
            action = np.clip(
                (target - eef_xyz) / environment.simulation.action_scale,
                -speed, speed,
            ).astype(np.float32)
            _, _, terminated, truncated, info = environment.step(action)
            touched |= color in info["robot_cube_contacts"]
            if render:
                time.sleep(1.0 / environment.metadata["render_fps"])
            if (terminated or truncated
                    or np.linalg.norm(target - info["eef_position"]) < 0.006):
                break
        if viewer_closed or terminated or truncated:
            break
    if viewer_closed:
        return None
    displacement = float(np.linalg.norm(info[position_key][:2] - before[:2]))
    return {
        "color": color,
        "before": before,
        "after": info[position_key].copy(),
        "displacement_m": displacement,
        "robot_contact": touched,
    }


def _show_current_state(environment, duration):
    """Keep the initial/final pose visible without advancing physics."""
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline and environment.simulation.viewer_is_running():
        environment.render()
        time.sleep(0.02)


def main():
    parser = argparse.ArgumentParser(description="두 25 mm 큐브의 실제 로봇 접촉 확인")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    environment = GymnasiumLabEnv(render_mode="human" if args.render else None)
    try:
        for case in CONTACT_CASES:
            print(f"=== {case[0]} cube: reset, then robot contact ===", flush=True)
            result = run_contact_case(environment, case, args.render)
            if result is None:
                print("Viewer를 닫아 접촉 확인을 중단했습니다.")
                return
            print(
                f"{result['color']}: contact={result['robot_contact']}, "
                f"XY displacement={result['displacement_m'] * 1000:.2f} mm"
            )
            print(f"  before={np.round(result['before'], 5)}")
            print(f"  after ={np.round(result['after'], 5)}")
            if not (result["robot_contact"] and result["displacement_m"] > 0.005):
                raise RuntimeError(f"{result['color']} 큐브 접촉·이동 확인에 실패했습니다.")
            if args.render:
                _show_current_state(environment, 2.0)
        print("Both cubes move through robot contact.")
    finally:
        environment.close()


if __name__ == "__main__":
    main()
