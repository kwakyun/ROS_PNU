"""Run complete episodes using random actions instead of a learned policy."""

import argparse
import time

import numpy as np

from .gymnasium_lab_env import GymnasiumLabEnv


def main() -> None:
    """Sample actions, call step repeatedly and print episode results."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--seed", type=int, default=10)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    if args.episodes <= 0:
        parser.error("--episodes must be positive")

    environment = GymnasiumLabEnv(render_mode="human" if args.render else None)
    completed = 0
    viewer_closed = False
    try:
        for episode_index in range(args.episodes):
            episode_seed = args.seed + episode_index
            observation, info = environment.reset(seed=episode_seed)
            environment.action_space.seed(episode_seed)
            episode_return = 0.0
            terminated = truncated = False

            while not (terminated or truncated):
                if args.render and not environment.simulation.viewer_is_running():
                    viewer_closed = True
                    break
                # TODO 6: 무작위 Action, step 호출, Return 누적을 연결한다.
                action = (
                    environment.action_space.sample()
                )
                observation, reward, terminated, truncated, info = (
                    environment.step(action)
                )
                episode_return += (
                    float(reward)
                )

                # Only the first three transitions are printed in detail.
                if episode_index == 0 and info["elapsed_steps"] <= 3:
                    print(
                        f"step={info['elapsed_steps']:3d} "
                        f"action={np.round(action, 3)} "
                        f"reward={reward:+.6f} "
                        f"terminated/truncated={terminated}/{truncated}"
                    )
                if args.render:
                    time.sleep(1.0 / environment.metadata["render_fps"])

            if viewer_closed:
                print("Viewer를 닫아 실행을 중단했습니다. 진행 중 Episode는 집계하지 않습니다.")
                break
            completed += 1
            reason = "out_of_bounds" if info["out_of_bounds"] else "time_limit"
            print(
                f"episode={episode_index + 1}, steps={info['elapsed_steps']}, "
                f"return={episode_return:+.6f}, end={reason}"
            )
            if not np.all(np.isfinite(observation)):
                raise RuntimeError("Observation contains NaN or infinity")

        print(f"completed episodes: {completed}/{args.episodes}")
        print("10주차는 환경 구조 실습입니다. 정책 학습은 11주차에 진행합니다.")
    finally:
        environment.close()


if __name__ == "__main__":
    main()

