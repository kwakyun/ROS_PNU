"""MuJoCo model loading, coordinate conversion and EEF motion helpers.

The Gymnasium environment in ``gymnasium_lab_env.py`` calls this class. Keeping
the MuJoCo details here makes the learning-environment code easier to read.
"""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
import time
from typing import Any, Dict, Optional, Tuple

import mujoco
import numpy as np


ROBOT_JOINT_NAMES = (
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
)
IK_JOINT_COUNT = 4


def _object_id(model: mujoco.MjModel, object_type: Any, name: str) -> int:
    """Return a named MuJoCo object ID or report a clear model error."""
    object_id = int(mujoco.mj_name2id(model, object_type, name))
    if object_id < 0:
        raise ValueError(f"MuJoCo model does not contain {name!r}")
    return object_id


class MujocoArmSimulation:
    """Own the MuJoCo state and move the EEF along base_link XYZ axes."""

    def __init__(
        self,
        model_path: Path,
        config: Dict[str, Any],
        render_mode: Optional[str] = None,
    ) -> None:
        self.config = config
        self.render_mode = render_mode
        self.model = mujoco.MjModel.from_xml_path(str(model_path))
        self.data = mujoco.MjData(self.model)
        self._ik_data = mujoco.MjData(self.model)

        self._base_site_id = _object_id(
            self.model, mujoco.mjtObj.mjOBJ_SITE, "baseframe"
        )
        self._eef_site_id = _object_id(
            self.model, mujoco.mjtObj.mjOBJ_SITE, "gripperframe"
        )
        self._cube_body_id = _object_id(
            self.model, mujoco.mjtObj.mjOBJ_BODY, "object_cube"
        )
        cube_joint_id = _object_id(
            self.model, mujoco.mjtObj.mjOBJ_JOINT, "object_cube_free"
        )
        self._cube_qpos_address = int(self.model.jnt_qposadr[cube_joint_id])
        self._cube_dof_address = int(self.model.jnt_dofadr[cube_joint_id])
        self._blue_cube_body_id = _object_id(
            self.model, mujoco.mjtObj.mjOBJ_BODY, "target_cube"
        )
        blue_joint_id = _object_id(
            self.model, mujoco.mjtObj.mjOBJ_JOINT, "target_cube_free"
        )
        self._blue_cube_qpos_address = int(self.model.jnt_qposadr[blue_joint_id])
        self._blue_cube_dof_address = int(self.model.jnt_dofadr[blue_joint_id])
        self._cube_geom_ids = {
            _object_id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "object_cube_geom"): "green",
            _object_id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "target_cube_geom"): "blue",
        }
        base_body_id = _object_id(self.model, mujoco.mjtObj.mjOBJ_BODY, "base")
        self._robot_body_ids = {base_body_id}
        for body_id in range(base_body_id + 1, self.model.nbody):
            if int(self.model.body_parentid[body_id]) in self._robot_body_ids:
                self._robot_body_ids.add(body_id)

        joint_ids = np.asarray(
            [
                _object_id(self.model, mujoco.mjtObj.mjOBJ_JOINT, name)
                for name in ROBOT_JOINT_NAMES
            ],
            dtype=np.int32,
        )
        self._joint_qpos_addresses = self.model.jnt_qposadr[joint_ids]
        self._ik_joint_ids = joint_ids[:IK_JOINT_COUNT]
        self._ik_qpos_addresses = self.model.jnt_qposadr[self._ik_joint_ids]
        self._ik_dof_addresses = self.model.jnt_dofadr[self._ik_joint_ids]
        self._ik_joint_ranges = self.model.jnt_range[self._ik_joint_ids].copy()
        self._actuator_ids = np.asarray(
            [
                _object_id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, name)
                for name in ROBOT_JOINT_NAMES
            ],
            dtype=np.int32,
        )

        workspace = config["workspace"]
        self.workspace_low = np.asarray(
            [workspace["x"][0], workspace["y"][0]], dtype=np.float64
        )
        self.workspace_high = np.asarray(
            [workspace["x"][1], workspace["y"][1]], dtype=np.float64
        )
        self.eef_workspace_low = np.append(self.workspace_low, workspace["eef_z"][0])
        self.eef_workspace_high = np.append(self.workspace_high, workspace["eef_z"][1])

        control = config["control"]
        self.action_scale = np.asarray(control["action_scale_m"], dtype=np.float64)
        if self.action_scale.shape != (3,) or np.any(self.action_scale <= 0):
            raise ValueError("control.action_scale_m must contain three positive XYZ scales")
        self._frame_skip = int(control["frame_skip"])
        self._ik_iterations = int(control["ik_iterations"])
        self._ik_damping = float(control["ik_damping"])
        self._max_joint_delta = float(control["max_joint_delta_rad"])

        self.last_ik_error = 0.0
        self.last_robot_cube_contacts = set()
        self._viewer = None
        self._renderer = None

    def reset(self) -> None:
        """Restore the robot and the two cubes from the Week 9 scene."""
        with self._viewer_lock():
            self._reset_state()

    def _viewer_lock(self):
        """Protect state changes while the native viewer is open."""
        return self._viewer.lock() if self._viewer is not None else nullcontext()

    def _reset_state(self) -> None:
        """Set initial positions and settle the cube before observation."""
        mujoco.mj_resetData(self.model, self.data)

        robot_qpos = np.asarray(
            self.config["initial"]["robot_qpos"], dtype=np.float64
        )
        if robot_qpos.shape != (len(ROBOT_JOINT_NAMES),):
            raise ValueError("initial.robot_qpos must contain six values")
        self.data.qpos[self._joint_qpos_addresses] = robot_qpos
        self.data.ctrl[self._actuator_ids] = robot_qpos
        mujoco.mj_forward(self.model, self.data)

        # mj_resetData restores both cube poses from scene.xml. No extra site
        # or task-specific cube placement is added during initialization.
        for _ in range(10):
            mujoco.mj_step(self.model, self.data)
        self.data.time = 0.0
        # mj_step integrates qpos after computing site/body transforms.
        # Refresh these transforms so observations describe the final qpos.
        mujoco.mj_forward(self.model, self.data)
        self.last_ik_error = 0.0
        self.last_robot_cube_contacts.clear()

    def move_eef(self, normalized_action: np.ndarray) -> None:
        """Convert a normalized XYZ action into IK targets and step MuJoCo."""
        with self._viewer_lock():
            self._move_eef_state(normalized_action)

    def _move_eef_state(self, normalized_action: np.ndarray) -> None:
        """Apply one action while holding the viewer state lock."""
        current_xyz = self.eef_position()
        target_xyz = np.clip(
            current_xyz + normalized_action * self.action_scale,
            self.eef_workspace_low,
            self.eef_workspace_high,
        )
        joint_target, self.last_ik_error = self._solve_ik(target_xyz)

        current_joints = self.data.qpos[self._ik_qpos_addresses]
        # Limit the whole joint update uniformly to preserve the IK direction.
        joint_delta = joint_target - current_joints
        largest_delta = float(np.max(np.abs(joint_delta)))
        if largest_delta > self._max_joint_delta:
            joint_delta *= self._max_joint_delta / largest_delta
        joint_target = current_joints + joint_delta
        self.data.ctrl[self._actuator_ids[:IK_JOINT_COUNT]] = joint_target

        self.last_robot_cube_contacts.clear()
        for _ in range(self._frame_skip):
            mujoco.mj_step(self.model, self.data)
            self._record_cube_contacts()
        mujoco.mj_forward(self.model, self.data)

    def _record_cube_contacts(self) -> None:
        """Record force-bearing robot/cube contacts over the full action."""
        force = np.zeros(6)
        for contact_id in range(self.data.ncon):
            contact = self.data.contact[contact_id]
            for cube_geom, other_geom in ((contact.geom1, contact.geom2),
                                          (contact.geom2, contact.geom1)):
                color = self._cube_geom_ids.get(int(cube_geom))
                if (color is not None and int(self.model.geom_bodyid[other_geom])
                        in self._robot_body_ids):
                    mujoco.mj_contactForce(self.model, self.data, contact_id, force)
                    if force[0] > 1.0e-6:
                        self.last_robot_cube_contacts.add(color)

    def eef_position(self) -> np.ndarray:
        """Return EEF XYZ in the robot base_link frame."""
        return self.world_to_base(self.data.site_xpos[self._eef_site_id])

    def cube_position(self) -> np.ndarray:
        """Return the green cube XYZ in the base_link frame."""
        return self.world_to_base(self.data.xpos[self._cube_body_id])

    def blue_cube_position(self) -> np.ndarray:
        """Return the free blue cube XYZ in the base_link frame."""
        return self.world_to_base(self.data.xpos[self._blue_cube_body_id])

    def world_to_base(self, world_position: np.ndarray) -> np.ndarray:
        """Transform one MuJoCo World point into base_link coordinates."""
        base_position = self.data.site_xpos[self._base_site_id]
        world_rotation_from_base = self.data.site_xmat[
            self._base_site_id
        ].reshape(3, 3)
        return world_rotation_from_base.T @ (
            np.asarray(world_position, dtype=np.float64) - base_position
        )

    def base_to_world(self, base_position: np.ndarray) -> np.ndarray:
        """Transform one base_link point into MuJoCo World coordinates."""
        world_base_position = self.data.site_xpos[self._base_site_id]
        world_rotation_from_base = self.data.site_xmat[
            self._base_site_id
        ].reshape(3, 3)
        return (
            world_base_position
            + world_rotation_from_base
            @ np.asarray(base_position, dtype=np.float64)
        )

    def render(self) -> Optional[np.ndarray]:
        """Draw the current simulation state."""
        if self.render_mode is None:
            return None
        if self.render_mode == "human":
            if self._viewer is None:
                from mujoco import viewer

                self._viewer = viewer.launch_passive(self.model, self.data)
                self._viewer.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
                self._viewer.cam.lookat[:] = (0.28, 0.0, 0.22)
                self._viewer.cam.distance = 1.15
                self._viewer.cam.azimuth = -40.0
                self._viewer.cam.elevation = -24.0
            if self._viewer.is_running():
                self._viewer.sync()
            return None

        if self._renderer is None:
            self._renderer = mujoco.Renderer(self.model, height=480, width=640)
        self._renderer.update_scene(self.data, camera="top_view")
        return self._renderer.render().copy()

    def viewer_is_running(self) -> bool:
        """Return whether the passive human viewer is still open."""
        return self._viewer is None or self._viewer.is_running()

    def close(self) -> None:
        """Release viewer and off-screen renderer resources."""
        if self._viewer is not None:
            self._viewer.close()
            self._viewer = None
            # Allow WSLg's native viewer thread to finish before Python exits.
            time.sleep(1.0)
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None

    def _solve_ik(self, target_base_xyz: np.ndarray) -> Tuple[np.ndarray, float]:
        """Solve position-only IK with damped least squares."""
        target_world = self.base_to_world(target_base_xyz)
        self._ik_data.qpos[:] = self.data.qpos
        self._ik_data.qvel[:] = 0.0
        mujoco.mj_forward(self.model, self._ik_data)

        jacobian_position = np.zeros((3, self.model.nv), dtype=np.float64)
        jacobian_rotation = np.zeros((3, self.model.nv), dtype=np.float64)
        damping = self._ik_damping**2 * np.eye(3)

        for _ in range(self._ik_iterations):
            error = target_world - self._ik_data.site_xpos[self._eef_site_id]
            if np.linalg.norm(error) < 1.0e-4:
                break
            mujoco.mj_jacSite(
                self.model,
                self._ik_data,
                jacobian_position,
                jacobian_rotation,
                self._eef_site_id,
            )
            jacobian = jacobian_position[:, self._ik_dof_addresses]
            delta = jacobian.T @ np.linalg.solve(
                jacobian @ jacobian.T + damping, error
            )
            if np.linalg.norm(delta) > 0.20:
                delta *= 0.20 / np.linalg.norm(delta)

            next_qpos = self._ik_data.qpos[self._ik_qpos_addresses] + delta
            self._ik_data.qpos[self._ik_qpos_addresses] = np.clip(
                next_qpos,
                self._ik_joint_ranges[:, 0] + 1.0e-3,
                self._ik_joint_ranges[:, 1] - 1.0e-3,
            )
            mujoco.mj_forward(self.model, self._ik_data)

        final_error = float(
            np.linalg.norm(target_world - self._ik_data.site_xpos[self._eef_site_id])
        )
        return self._ik_data.qpos[self._ik_qpos_addresses].copy(), final_error
