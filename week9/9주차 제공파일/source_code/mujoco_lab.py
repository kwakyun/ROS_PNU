#!/usr/bin/env python3
"""MuJoCo basics for the PhysicAI-Arm Lite Week 9 lab."""

import argparse
from contextlib import contextmanager
import math
from pathlib import Path
import time
from typing import Optional

import mujoco
import mujoco.viewer
import numpy as np
import yaml


JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]



def default_model_path() -> Path:
    """Return the scene.xml installed beside this script."""
    return (
        Path(__file__).resolve().parent
        / "models"
        / "scene.xml"
    )


def load_model(path: Path) -> tuple[mujoco.MjModel, mujoco.MjData]:
    """Load one MJCF model and allocate its runtime state."""
    if not path.is_file():
        raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {path}")
    model = mujoco.MjModel.from_xml_path(str(path))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data


def object_name(
    model: mujoco.MjModel,
    object_type: mujoco.mjtObj,
    object_id: int,
) -> str:
    """Return a readable MuJoCo object name."""
    return mujoco.mj_id2name(model, object_type, object_id) or "(unnamed)"


def inspect_model(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    """Print joints, actuators, and their qpos/qvel/ctrl indices."""
    print("=== MODEL SUMMARY ===")
    print(
        f"nbody={model.nbody}, njnt={model.njnt}, "
        f"nq={model.nq}, nv={model.nv}, nu={model.nu}"
    )
    print(f"timestep={model.opt.timestep:.4f} s")

    print("\n=== JOINTS ===")
    for joint_id in range(model.njnt):
        name = object_name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id)
        qpos_index = int(model.jnt_qposadr[joint_id])
        qvel_index = int(model.jnt_dofadr[joint_id])
        if model.jnt_type[joint_id] == mujoco.mjtJoint.mjJNT_FREE:
            # 자유 물체는 각도 하나가 아니라 XYZ+Quaternion과 선속도+각속도를 갖는다.
            pose = np.array2string(data.qpos[qpos_index:qpos_index + 7], precision=3)
            velocity = np.array2string(data.qvel[qvel_index:qvel_index + 6], precision=3)
            print(
                f"{joint_id}: {name:18s} type=free "
                f"qpos[{qpos_index}:{qpos_index + 7}]={pose}, "
                f"qvel[{qvel_index}:{qvel_index + 6}]={velocity}"
            )
            continue
        lower, upper = model.jnt_range[joint_id]
        print(
            f"{joint_id}: {name:18s} type=hinge "
            f"qpos[{qpos_index}]={data.qpos[qpos_index]:+.3f}, "
            f"qvel[{qvel_index}]={data.qvel[qvel_index]:+.3f}, "
            f"range=[{lower:+.3f}, {upper:+.3f}]"
        )

    print("\n=== ACTUATORS ===")
    for actuator_id in range(model.nu):
        name = object_name(
            model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_id
        )
        joint_id = int(model.actuator_trnid[actuator_id, 0])
        joint_name = object_name(
            model, mujoco.mjtObj.mjOBJ_JOINT, joint_id
        )
        lower, upper = model.actuator_ctrlrange[actuator_id]
        print(
            f"{actuator_id}: {name:15s} -> {joint_name:15s} "
            f"ctrl[{actuator_id}]={data.ctrl[actuator_id]:+.3f}, "
            f"range=[{lower:+.3f}, {upper:+.3f}]"
        )


def initial_control(
    model: mujoco.MjModel,
    data: mujoco.MjData,
) -> np.ndarray:
    """Build Actuator targets from the model's current joint positions."""
    target = np.zeros(model.nu, dtype=float)
    for actuator_id in range(model.nu):
        joint_id = int(model.actuator_trnid[actuator_id, 0])
        qpos_index = int(model.jnt_qposadr[joint_id])
        target[actuator_id] = data.qpos[qpos_index]
    return target


def actuator_id(model: mujoco.MjModel, name: str) -> int:
    """Return an Actuator index from its model name."""
    index = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_ACTUATOR, name
    )
    if index < 0:
        raise ValueError(f"Actuator를 찾을 수 없습니다: {name}")
    return int(index)


def check_target(
    model: mujoco.MjModel,
    actuator_index: int,
    value: float,
) -> None:
    """Reject a target outside the MJCF Actuator ctrlrange."""
    lower, upper = model.actuator_ctrlrange[actuator_index]
    if not np.isfinite(value) or not lower <= value <= upper:
        name = object_name(
            model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_index
        )
        raise ValueError(
            f"{name}={value:.4f} rad는 허용 범위 "
            f"[{lower:.4f}, {upper:.4f}] 밖입니다."
        )


def run_segment(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    target: np.ndarray,
    duration: float,
    label: str,
    viewer: Optional[mujoco.viewer.Handle],
) -> bool:
    """Apply one ctrl vector and repeatedly call mj_step()."""
    end_time = data.time + duration
    next_print = data.time
    while data.time < end_time:
        if viewer is not None and not viewer.is_running():
            return False

        wall_start = time.perf_counter()
        # TODO 1: data.ctrl[:]에 이번 구간의 목표 배열 target을 대입한다.
        data.ctrl[:] = (
            ### TODO ###
        )
        # TODO 2: mujoco.mj_step()에 model, data를 전달하여 물리 상태를 한 스텝 진행한다.
        mujoco.mj_step(
            ### TODO ###  모델 객체
            ### TODO ###  상태 객체
        )

        if data.time >= next_print:
            robot_positions = [
                data.qpos[int(model.jnt_qposadr[int(model.actuator_trnid[i, 0])])]
                for i in range(model.nu)
            ]
            positions = ", ".join(f"{value:+.3f}" for value in robot_positions)
            print(f"[{label}] t={data.time:5.2f}s robot_qpos=[{positions}]")
            next_print += 0.5
        if viewer is not None:
            viewer.sync()

        elapsed = time.perf_counter() - wall_start
        time.sleep(max(0.0, model.opt.timestep - elapsed))
    return True


@contextmanager
def viewer_context(model, data, no_viewer):
    """Let the native passive-viewer thread finish before Python exits."""
    if no_viewer:
        yield None
        return
    try:
        with mujoco.viewer.launch_passive(model, data) as viewer:
            yield viewer
    finally:
        # WSLg에서 창 종료 요청 직후 Python이 끝나는 경합을 피한다.
        time.sleep(1.0)


def run_single_joint(args: argparse.Namespace) -> None:
    """Move one Actuator while all other targets stay unchanged."""
    model, data = load_model(args.model)
    target = initial_control(model, data)
    index = actuator_id(model, args.joint)
    check_target(model, index, args.target)
    target[index] = args.target
    print(
        f"{args.joint} 목표={args.target:.3f} rad, "
        f"실행 시간={args.duration:.1f} s"
    )

    with viewer_context(model, data, args.no_viewer) as viewer:
        run_segment(
            model, data, target, args.duration, args.joint, viewer
        )


def run_sequence(args: argparse.Namespace) -> None:
    """Preview the same A-B-A poses used by the ROS comparison goal."""
    model, data = load_model(args.model)
    pose_file = args.model.parent.parent / "config/comparison_poses.yaml"
    raw = yaml.safe_load(pose_file.read_text())
    if raw["joint_names"] != JOINT_NAMES:
        raise ValueError("comparison_poses.yaml의 관절 순서를 확인하세요.")
    poses = {}
    for label in ("A", "B"):
        values = raw["poses"][label]
        if len(values) != len(JOINT_NAMES):
            raise ValueError("자세의 관절값 개수를 확인하세요.")
        target = initial_control(model, data)
        for name, value in zip(JOINT_NAMES, values):
            index = actuator_id(model, name)
            check_target(model, index, float(value))
            target[index] = value
        poses[label] = target
    # This is a PC-only preview: initialize the robot in A before showing it.
    for name in JOINT_NAMES:
        joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        data.qpos[model.jnt_qposadr[joint]] = raw["poses"]["A"][JOINT_NAMES.index(name)]
    data.ctrl[:] = poses["A"]
    mujoco.mj_forward(model, data)
    with viewer_context(model, data, args.no_viewer) as viewer:
        for label in ("A", "B", "A"):
            values = raw["poses"][label]
            target = poses[label]
            print(f"\n--- {label}: {values} ---")
            if not run_segment(
                model,
                data,
                target,
                args.segment_duration,
                label,
                viewer,
            ):
                break


def positive_float(raw_value: str) -> float:
    value = float(raw_value)
    if not math.isfinite(value) or value <= 0.0:
        raise argparse.ArgumentTypeError("0보다 큰 값을 입력하세요.")
    return value


def build_parser() -> argparse.ArgumentParser:
    """Create the inspect, run, and sequence commands."""
    parser = argparse.ArgumentParser(
        description="PhysicAI-Arm Lite MuJoCo 기초 실습"
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=default_model_path(),
        help="실행할 MJCF scene.xml 경로",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect", help="Joint와 Actuator 구조 확인")

    run_parser = commands.add_parser("run", help="관절 하나 제어")
    run_parser.add_argument("--joint", choices=JOINT_NAMES, required=True)
    run_parser.add_argument("--target", type=float, required=True)
    run_parser.add_argument("--duration", type=positive_float, default=5.0)
    run_parser.add_argument("--no-viewer", action="store_true")

    sequence_parser = commands.add_parser(
        "sequence", help="실습 2 자세 A-B-A 시뮬레이션 미리보기"
    )
    sequence_parser.add_argument(
        "--segment-duration", type=positive_float, default=2.0
    )
    sequence_parser.add_argument("--no-viewer", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "inspect":
            model, data = load_model(args.model)
            inspect_model(model, data)
        elif args.command == "run":
            run_single_joint(args)
        else:
            run_sequence(args)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"오류: {exc}") from exc


if __name__ == "__main__":
    main()
