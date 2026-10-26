"""Shared settings, image geometry, and prediction selection (no ROS imports)."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re

import cv2
import numpy as np
import yaml


@dataclass
class VisionConfig:
    path: Path
    root: Path
    data: dict

    @property
    def classes(self):
        return self.data["classes"]

    @property
    def names(self):
        return {index: item["name"] for index, item in enumerate(self.classes)}

    @property
    def size(self):
        camera = self.data["camera"]
        return int(camera["output_width"]), int(camera["output_height"])

    def resolve(self, value):
        path = Path(value).expanduser()
        return (path if path.is_absolute() else self.root / path).resolve()

    def path_for(self, key):
        return self.resolve(self.data["paths"][key])

    def contract(self):
        return {
            "classes": self.classes,
            "kpt_shape": [1, 3],
            "image_size": list(self.size),
        }


def load_config(path, root=None):
    path = Path(path).expanduser().resolve()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("classes"):
        raise ValueError("vision.yaml에 classes 목록이 필요합니다.")
    names = []
    for item in data["classes"]:
        name = item.get("name", "")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise ValueError("클래스 이름은 영문 소문자로 시작하는 소문자/숫자/_ 문자열이어야 합니다.")
        if item.get("point_mode") not in ("box_center", "manual"):
            raise ValueError(f"{name}: point_mode는 box_center 또는 manual이어야 합니다.")
        names.append(name)
    if len(names) != len(set(names)):
        raise ValueError("클래스 이름이 중복되었습니다.")
    for key in ("capture_width", "capture_height", "output_width", "output_height", "framerate", "publish_hz"):
        if float(data["camera"][key]) <= 0:
            raise ValueError(f"camera.{key}는 양수여야 합니다.")
    if not 0 < float(data["training"]["validation_ratio"]) < 1:
        raise ValueError("validation_ratio는 0과 1 사이여야 합니다.")
    for key in ("confidence", "keypoint_confidence", "iou"):
        if not 0 <= float(data["inference"][key]) <= 1:
            raise ValueError(f"inference.{key}는 [0, 1] 범위여야 합니다.")
    # Installed ROS nodes pass their share directory explicitly; scripts pass week7/.
    return VisionConfig(path, Path(root).resolve() if root else path.parents[2], data)


def write_contract(path, config):
    Path(path).write_text(
        json.dumps(config.contract(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def check_contract(path, config):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"설정 기록이 없습니다: {path}. 새 데이터셋을 수집하거나 학습을 먼저 수행하세요.")
    if json.loads(path.read_text(encoding="utf-8")) != config.contract():
        raise ValueError("클래스 순서/이름/점 기준/영상 규격이 다릅니다. 별도의 데이터셋과 모델을 사용하세요.")


def model_contract_path(model_path):
    return Path(model_path).with_suffix(".vision.json")


def validate_model(model, config):
    names = model.names
    names = {int(k): str(v) for k, v in names.items()} if isinstance(names, dict) else dict(enumerate(names))
    if names != config.names or model.task != "pose":
        raise ValueError(f"모델 클래스/Pose 유형이 설정과 다릅니다: {names}; expected={config.names}")
    backend = model.model
    if isinstance(backend, (str, Path)):
        backend = getattr(getattr(model, "predictor", None), "model", None)
    shape = getattr(backend, "kpt_shape", None)
    if shape is None:
        shape = getattr(backend, "yaml", {}).get("kpt_shape", [])
    if list(shape) != [1, 3]:
        raise ValueError("모델은 객체당 Keypoint 한 개(kpt_shape=[1, 3])여야 합니다.")


def load_model(path, config):
    import os
    os.environ["YOLO_AUTOINSTALL"] = "false"
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"학습 모델이 없습니다: {path}. yolo_finetune.py를 먼저 실행하세요.")
    check_contract(model_contract_path(path), config)
    from ultralytics import YOLO
    model = YOLO(str(path), task="pose")
    # Exported models expose metadata only after predict() initializes the backend.
    if path.suffix == ".pt":
        validate_model(model, config)
    return model


def sample_frame(frame, config):
    """Use exactly the same stretched image geometry for labels and inference."""
    return cv2.resize(frame, config.size, interpolation=cv2.INTER_AREA)


def csi_pipeline(config, sensor_id=None):
    c = config.data["camera"]
    sensor_id = c["sensor_id"] if sensor_id is None else sensor_id
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        "video/x-raw(memory:NVMM), "
        f"width={c['capture_width']}, height={c['capture_height']}, "
        f"framerate={c['framerate']}/1, format=NV12 ! "
        "nvvidconv flip-method=0 ! video/x-raw, format=BGRx ! "
        "videoconvert ! video/x-raw, format=BGR ! "
        "appsink max-buffers=1 drop=true sync=false"
    )


def open_source(config, source=None, sensor_id=None):
    source = str(source if source is not None else config.data["camera"]["source"])
    if source.lower() == "csi":
        capture = cv2.VideoCapture(csi_pipeline(config, sensor_id), cv2.CAP_GSTREAMER)
    elif source.isdigit():
        capture = cv2.VideoCapture(int(source))
        for prop, key in ((cv2.CAP_PROP_FRAME_WIDTH, "capture_width"),
                          (cv2.CAP_PROP_FRAME_HEIGHT, "capture_height"),
                          (cv2.CAP_PROP_FPS, "framerate")):
            capture.set(prop, config.data["camera"][key])
    else:
        capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"영상 입력을 열 수 없습니다: {source}. CSI/GStreamer와 장치 점유를 확인하세요.")
    return capture


def as_numpy(value):
    if value is None:
        return np.empty((0,))
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    return np.asarray(value)


def extract_detections(result, config):
    """One instance per class; manual points must pass their own confidence."""
    if result.boxes is None or len(result.boxes) == 0:
        return {}
    boxes = as_numpy(result.boxes.xyxy)
    confidence = as_numpy(result.boxes.conf)
    classes = as_numpy(result.boxes.cls).astype(int)
    keypoints = getattr(result, "keypoints", None)
    points = as_numpy(keypoints.xy) if keypoints is not None else np.empty((0, 1, 2))
    point_conf = as_numpy(keypoints.conf) if keypoints is not None else np.empty((0, 1))
    settings = config.data["inference"]
    detections = {}
    width, height = config.size
    for class_id, item in enumerate(config.classes):
        candidates = sorted(np.flatnonzero(classes == class_id), key=lambda i: confidence[i], reverse=True)
        for index in candidates:
            bbox = boxes[index].astype(float)
            if not np.isfinite(bbox).all() or not math.isfinite(float(confidence[index])):
                continue
            if confidence[index] < settings["confidence"] or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                continue
            point = (bbox[:2] + bbox[2:]) / 2
            keypoint_confidence = None
            if item["point_mode"] == "manual":
                if points.ndim != 3 or point_conf.ndim != 2 or index >= len(points) or index >= len(point_conf):
                    continue
                if points.shape[1] < 1 or point_conf.shape[1] < 1:
                    continue
                point = points[index, 0].astype(float)
                keypoint_confidence = float(point_conf[index, 0])
                if not math.isfinite(keypoint_confidence) or keypoint_confidence < settings["keypoint_confidence"]:
                    continue
            if not np.isfinite(point).all() or not (0 <= point[0] < width and 0 <= point[1] < height):
                continue
            detections[item["name"]] = {
                "bbox": bbox, "point": point,
                "confidence": float(confidence[index]),
                "keypoint_confidence": keypoint_confidence,
            }
            break
    return detections


def predict(model, frame, config):
    s = config.data["inference"]
    result = model.predict(
        source=frame, imgsz=config.data["training"]["imgsz"],
        conf=s["confidence"], iou=s["iou"], device=s["device"],
        max_det=s["max_detections"], verbose=False,
    )[0]
    validate_model(model, config)
    return extract_detections(result, config)


def class_color(index):
    return ((0, 220, 0), (255, 120, 0), (0, 210, 255), (220, 0, 220))[index % 4]


def draw_detections(frame, detections, config):
    display = frame.copy()
    sx, sy = frame.shape[1] / config.size[0], frame.shape[0] / config.size[1]
    for index, item in enumerate(config.classes):
        detection = detections.get(item["name"])
        if detection is None:
            continue
        bbox = detection["bbox"] * np.array([sx, sy, sx, sy])
        x1, y1, x2, y2 = np.rint(bbox).astype(int)
        u, v = np.rint(detection["point"] * [sx, sy]).astype(int)
        color = class_color(index)
        cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
        cv2.drawMarker(display, (u, v), color, cv2.MARKER_CROSS, 22, 2)
    return display
