#!/usr/bin/env python3
"""Fine-tune a configurable one-keypoint YOLO Pose model on the Jetson GPU."""

from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "week07_vision_control"))
from week07_vision_control.vision_common import (
    check_contract, load_config, model_contract_path, validate_model, write_contract,
)
DEFAULT_CONFIG = ROOT / "week07_vision_control/config/vision.yaml"


def parse_arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--data", type=Path, help="Prepared dataset.yaml")
    p.add_argument("--weights", type=Path, help="Local pose seed weights")
    p.add_argument("--name", default="week7_pose", help="Unique training run name")
    for name in ("epochs", "batch", "workers", "patience", "imgsz"):
        p.add_argument("--"+name, type=int)
    p.add_argument("--device")
    p.add_argument("--amp", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--export", choices=("onnx", "engine"))
    p.add_argument("--export-only", type=Path)
    return p.parse_args()


def training_options(args, config):
    options = config.data["training"].copy()
    options.pop("validation_ratio")
    for key in ("epochs", "batch", "workers", "patience", "imgsz", "device", "amp"):
        if getattr(args, key) is not None:
            options[key] = getattr(args, key)
    for key in ("epochs", "batch", "patience", "imgsz"):
        if options[key] <= 0:
            raise ValueError(f"{key}는 양수여야 합니다.")
    if options["workers"] < 0:
        raise ValueError("workers는 0 이상이어야 합니다.")
    options.update(
        project=str(config.path_for("runs")), name=args.name, exist_ok=False,
        deterministic=True, fliplr=0.0, degrees=3.0, translate=0.05,
        scale=0.15, mosaic=0.25, close_mosaic=10,
    )
    return options


def fine_tune(args, config):
    from yolo_dataset_tool import validate_label_text
    data = args.data.expanduser().resolve() if args.data else config.path_for("dataset") / "dataset.yaml"
    if not data.is_file():
        raise FileNotFoundError(f"Dataset YAML이 없습니다: {data}. 먼저 수집/--prepare-only를 실행하세요.")
    check_contract(data.parent / "vision.json", config)
    import yaml
    dataset = yaml.safe_load(data.read_text(encoding="utf-8"))
    if dataset.get("names") != config.names or dataset.get("kpt_shape") != [1, 3]:
        raise ValueError("dataset.yaml의 클래스/Keypoint 설정이 vision.yaml과 다릅니다.")
    # Regenerate paths after copying a dataset to another machine.
    if Path(dataset["path"]).resolve() != data.parent:
        raise ValueError("dataset.yaml 경로가 현재 위치와 다릅니다. --prepare-only로 경로를 갱신하세요.")
    for split in ("train", "val"):
        labels = list((data.parent / "labels" / split).glob("*.txt"))
        if not labels:
            raise ValueError("train과 val 모두 이미지/라벨이 필요합니다. 두 장 이상 수집하세요.")
        for label in labels:
            validate_label_text(label.read_text(encoding="utf-8"), config)
    weights = args.weights.expanduser().resolve() if args.weights else config.path_for("weights")
    if not weights.is_file():
        raise FileNotFoundError(f"로컬 Pose 사전학습 가중치가 없습니다: {weights}. 조교에게 확인하세요.")
    options = training_options(args, config)
    import torch
    if str(options["device"]) != "cpu" and not torch.cuda.is_available():
        raise RuntimeError("CUDA를 사용할 수 없습니다. NVIDIA PyTorch 환경을 조교와 확인하세요.")
    from ultralytics import YOLO
    model = YOLO(str(weights))
    if model.task != "pose":
        raise ValueError("사전학습 가중치는 yolo11n-pose.pt 같은 Pose 모델이어야 합니다.")
    model.train(data=str(data), **options)
    # train() returns metrics, not the run directory. Read the actual trainer path.
    best = Path(model.trainer.best)
    if not best.is_file():
        raise RuntimeError(f"best.pt가 생성되지 않았습니다: {best}")
    validate_model(YOLO(str(best)), config)
    output = config.path_for("model")
    output.parent.mkdir(parents=True, exist_ok=True)
    if best.resolve() != output:
        shutil.copy2(best, output)
    write_contract(model_contract_path(output), config)
    print(f"Best checkpoint: {best}\nInstalled model: {output}")
    return output


def main():
    os.environ["YOLO_AUTOINSTALL"] = "false"
    args = parse_arguments()
    config = load_config(args.config, ROOT)
    if args.export_only:
        from week07_vision_control.vision_common import load_model
        model_path = args.export_only.expanduser().resolve()
        if not args.export:
            raise ValueError("--export-only에는 --export onnx 또는 engine이 필요합니다.")
        model = load_model(model_path, config)
    else:
        model_path = fine_tune(args, config)
        model = None
    if args.export:
        from week07_vision_control.vision_common import load_model
        model = model or load_model(model_path, config)
        device = args.device or config.data["training"]["device"]
        exported = Path(model.export(format=args.export, imgsz=args.imgsz or config.data["training"]["imgsz"],
                                     device=device, **({"half": True} if args.export=="engine" else {})))
        write_contract(model_contract_path(exported), config)
        print(f"Exported: {exported}")


if __name__ == "__main__":
    main()
