"""Print the Week 10 spaces and show what happens during one environment step."""

import argparse
import time

import mujoco
import numpy as np

from .gymnasium_lab_env import GymnasiumLabEnv


REQUIRED_OBJECTS = {
    mujoco.mjtObj.mjOBJ_BODY: ("base", "object_cube", "target_cube"),
    mujoco.mjtObj.mjOBJ_GEOM: ("floor", "object_cube_geom", "target_cube_geom"),
    mujoco.mjtObj.mjOBJ_SITE: ("baseframe", "gripperframe"),
}


def _print_observation(observation: np.ndarray) -> None:
    labels = ("eef_x", "eef_y", "green_x", "green_y", "blue_x", "blue_y")
    for index, (label, value) in enumerate(zip(labels, observation)):
        print(f"  observation[{index}] {label:>7s} = {value:+.4f} m")


def main() -> None:
    """Inspect reset, action, observation, reward and episode signals."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--render", action="store_true", help="Open the MuJoCo scene viewer."
    )
    args = parser.parse_args()

    environment = GymnasiumLabEnv(render_mode="human" if args.render else None)
    try:
        observation, info = environment.reset(seed=10)

        print("=== 1. MuJoCo scene ===")
        print(f"  nq={environment.model.nq}, nv={environment.model.nv}, "
              f"nu={environment.model.nu}, dt={environment.model.opt.timestep:.4f} s")
        for object_type, names in REQUIRED_OBJECTS.items():
            for name in names:
                object_id = mujoco.mj_name2id(environment.model, object_type, name)
                if object_id < 0:
                    raise RuntimeError(f"Missing MuJoCo object: {name}")
                print(f"  {name:>16s}: id={object_id}")

        print("\n=== 2. Gymnasium spaces ===")
        print(f"  observation_space: {environment.observation_space}")
        print(f"  action_space:      {environment.action_space}")
        print("\nInitial observation (base_link)")
        _print_observation(observation)

        before_eef = info["eef_position"].copy()
        action = np.asarray([0.50, -0.25, 1.0], dtype=np.float32)
        observation, reward, terminated, truncated, info = environment.step(action)

        print("\n=== 3. One step(action) ===")
        print(f"  action              = {action}")
        print(
            "  requested EEF move  = "
            f"{action * environment.simulation.action_scale} m"
        )
        print(f"  actual EEF move     = {info['eef_position'] - before_eef} m")
        print(f"  actual EEF XYZ      = {info['eef_position']} m")
        print(f"  reward terms        = {info['reward_terms']}")
        print(f"  reward              = {reward:+.6f}")
        print(f"  terminated/truncated= {terminated}/{truncated}")
        print("\nNext observation")
        _print_observation(observation)

        if args.render:
            print("\nViewer를 닫으면 프로그램이 종료됩니다.")
            while environment.simulation.viewer_is_running():
                environment.render()
                time.sleep(0.02)
    finally:
        environment.close()


if __name__ == "__main__":
    main()

