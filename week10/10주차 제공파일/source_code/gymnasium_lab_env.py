"""A Gymnasium interface lab using the unchanged Week 9 scene."""

from pathlib import Path

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import yaml

from .mujoco_simulation import MujocoArmSimulation


def project_directory() -> Path:
    return Path(__file__).resolve().parents[1]


class GymnasiumLabEnv(gym.Env):
    """Observe EEF/cube XY positions and run XYZ actions without a task goal."""

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 20}

    def __init__(self, render_mode=None, model_path=None, config_path=None):
        super().__init__()
        if render_mode not in (None, "human", "rgb_array"):
            raise ValueError("render_mode must be None, 'human' or 'rgb_array'")
        self.render_mode = render_mode
        root = project_directory()
        self.model_path = Path(model_path or root / "models/scene.xml").resolve()
        self.config_path = Path(config_path or root / "config/task.yaml").resolve()
        with self.config_path.open(encoding="utf-8") as stream:
            self.config = yaml.safe_load(stream)
        self.simulation = MujocoArmSimulation(self.model_path, self.config, render_mode)
        self.model = self.simulation.model
        self.data = self.simulation.data

        # TODO 1: Observation과 Action의 범위·모양을 선언한다.
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(6,),
            dtype=np.float32,
        )
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(3,),
            dtype=np.float32,
        )
        self._max_steps = int(self.config["episode"]["max_steps"])
        self._action_cost_scale = float(self.config["reward"]["action_cost_scale"])
        self._elapsed_steps = 0

    def reset(self, *, seed=None, options=None):
        """Restore the same scene and return its first observation and info."""
        super().reset(seed=seed)
        del options  # Initial randomization is outside the Week 10 lab.
        self.simulation.reset()
        self._elapsed_steps = 0
        if self.render_mode == "human":
            self.render()
        # TODO 3: reset()의 두 반환값을 순서대로 작성한다.
        return (
            self._observation(),
            self._info(),
        )

    def step(self, action):
        """Run one action and return Gymnasium's five transition values."""
        action = np.asarray(action, dtype=np.float64)
        if action.shape != (3,):
            raise ValueError(f"action must have shape (3,), got {action.shape}")
        if not np.all(np.isfinite(action)):
            raise ValueError("action contains NaN or infinity")
        action = np.clip(action, -1.0, 1.0)

        # 1. Action -> IK -> actuator targets -> 25 physics substeps.
        self.simulation.move_eef(action)
        self._elapsed_steps += 1
        # 2. Supplied reward example; no goal or success bonus.
        reward = -self._action_cost_scale * float(np.dot(action, action))
        outside = self._cubes_outside_workspace()
        # TODO 5: 작업영역 이탈과 시간 제한을 구분한다.
        terminated = bool(
            len(outside) > 0
        )
        truncated = bool(
            (self._elapsed_steps >= self._max_steps) and not terminated
        )

        if self.render_mode == "human":
            self.render()
        # TODO 4: Action 이후의 상태와 함께 다섯 값을 반환한다.
        return (
            self._observation(),
            reward,
            terminated,
            truncated,
            self._info(outside, {"action_cost": reward}),  # info는 제공
        )

    def _observation(self):
        # TODO 2: EEF, 초록, 파랑의 XY를 순서대로 연결한다.
        return np.concatenate((
            self.simulation.eef_position()[:2],
            self.simulation.cube_position()[:2],
            self.simulation.blue_cube_position()[:2],
        )).astype(np.float32)

    def _cubes_outside_workspace(self):
        outside = []
        for color, position in (
            ("green", self.simulation.cube_position()),
            ("blue", self.simulation.blue_cube_position()),
        ):
            if (np.any(position[:2] < self.simulation.workspace_low)
                    or np.any(position[:2] > self.simulation.workspace_high)):
                outside.append(color)
        return outside

    def _info(self, outside=None, reward_terms=None):
        outside = self._cubes_outside_workspace() if outside is None else outside
        return {
            "eef_position": self.simulation.eef_position(),
            "cube_position": self.simulation.cube_position(),
            "blue_cube_position": self.simulation.blue_cube_position(),
            "elapsed_steps": self._elapsed_steps,
            "out_of_bounds": bool(outside),
            "outside_cubes": list(outside),
            "reward_terms": {} if reward_terms is None else reward_terms,
            "ik_error": self.simulation.last_ik_error,
            "robot_cube_contacts": sorted(self.simulation.last_robot_cube_contacts),
            "coordinate_frame": "base_link",
        }

    def render(self):
        return self.simulation.render()

    def close(self):
        self.simulation.close()
