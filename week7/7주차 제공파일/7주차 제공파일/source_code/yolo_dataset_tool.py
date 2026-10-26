#!/usr/bin/env python3
"""Collect one object per configured class using the Week13 annotation workflow."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "week07_vision_control"))
from week07_vision_control.vision_common import (
    check_contract, class_color, load_config, open_source, sample_frame, write_contract,
)

DEFAULT_CONFIG = ROOT / "week07_vision_control/config/vision.yaml"


@dataclass(frozen=True)
class PoseAnnotation:
    class_id: int
    roi: tuple
    keypoint: tuple
    visibility: int = 2


def roi_center(roi):
    x, y, width, height = roi
    return x + width / 2, y + height / 2


def clipped_roi(start, end, shape):
    height, width = shape[:2]
    x1, x2 = sorted((max(0, min(width - 1, start[0])), max(0, min(width - 1, end[0]))))
    y1, y2 = sorted((max(0, min(height - 1, start[1])), max(0, min(height - 1, end[1]))))
    return x1, y1, x2 - x1, y2 - y1


def expand_roi_to_include_point(roi, point, width, height):
    x, y, w, h = roi
    x1, y1 = max(0, min(x, int(point[0]) - 4)), max(0, min(y, int(point[1]) - 4))
    x2, y2 = min(width, max(x + w, int(point[0]) + 4)), min(height, max(y + h, int(point[1]) + 4))
    return x1, y1, x2 - x1, y2 - y1


def validate_label_text(text, config):
    seen = []
    for line in text.splitlines():
        if not line.strip():
            continue
        values = line.split()
        if len(values) != 8:
            raise ValueError("YOLO Pose 라벨은 8개 값이어야 합니다. Detection 라벨과 섞지 마세요.")
        class_id, visibility = int(values[0]), int(values[7])
        numbers = np.asarray([float(v) for v in values[1:7]])
        if class_id not in config.names or visibility not in (0, 1, 2):
            raise ValueError("클래스 ID 또는 visibility가 올바르지 않습니다.")
        if not np.isfinite(numbers).all() or np.any(numbers < 0) or np.any(numbers > 1):
            raise ValueError("라벨 좌표는 [0, 1] 범위의 유한한 값이어야 합니다.")
        cx, cy, w, h, px, py = numbers
        if w <= 0 or h <= 0 or cx - w/2 < -1e-7 or cx + w/2 > 1+1e-7 or cy - h/2 < -1e-7 or cy + h/2 > 1+1e-7:
            raise ValueError("Box 범위가 올바르지 않습니다.")
        if visibility == 0 and (px != 0 or py != 0):
            raise ValueError("위치 미상 Keypoint는 0 0 0으로 저장합니다.")
        seen.append(class_id)
    if seen != sorted(set(seen)):
        raise ValueError("클래스당 객체 한 개를 ID 순서대로 기록해야 합니다.")


def yolo_pose_label(annotation, width, height):
    x, y, w, h = annotation.roi
    px, py = annotation.keypoint
    return (
        f"{annotation.class_id} {(x+w/2)/width:.8f} {(y+h/2)/height:.8f} "
        f"{w/width:.8f} {h/height:.8f} {px/width:.8f} {py/height:.8f} "
        f"{annotation.visibility}\n"
    )


class AnnotationSession:
    """Generate box/click stages from class settings, including absent objects."""

    def __init__(self, config):
        self.config = config
        self.stages = []
        for index, item in enumerate(config.classes):
            self.stages.append((index, "box"))
            if item["point_mode"] == "manual":
                self.stages.append((index, "point"))
        self.step = 0
        self.boxes = [None] * len(config.classes)
        self.points = [None] * len(config.classes)
        self.visibility = [2] * len(config.classes)

    @property
    def done(self):
        return self.step >= len(self.stages)

    def reset_current(self):
        index, kind = self.stages[self.step]
        if kind == "box":
            self.boxes[index] = None
            self.points[index] = None
            self.visibility[index] = 2
        else:
            self.points[index] = None
            self.visibility[index] = 2

    def back(self):
        self.step = max(0, self.step - 1)
        index, kind = self.stages[self.step]
        if kind == "point" and self.boxes[index] is None:
            self.step = max(0, self.step - 1)

    def advance(self, absent=False):
        index, kind = self.stages[self.step]
        if kind == "box":
            if absent:
                self.boxes[index] = None
                self.points[index] = None
                self.step += 2 if self.config.classes[index]["point_mode"] == "manual" else 1
                return True
            if self.boxes[index] is None:
                return False
            if self.config.classes[index]["point_mode"] == "box_center":
                self.points[index] = roi_center(self.boxes[index])
        else:
            if absent:
                self.points[index] = (0.0, 0.0)
                self.visibility[index] = 0
            elif self.points[index] is None:
                return False
        self.step += 1
        return True

    def annotations(self, shape):
        result = []
        height, width = shape[:2]
        for index, box in enumerate(self.boxes):
            if box is None:
                continue
            point = self.points[index]
            if self.config.classes[index]["point_mode"] == "box_center":
                point = roi_center(box)
            visibility = self.visibility[index] if point is not None else 0
            point = point if point is not None else (0.0, 0.0)
            if visibility and self.config.classes[index]["point_mode"] == "manual":
                box = expand_roi_to_include_point(box, point, width, height)
            result.append(PoseAnnotation(index, box, point, visibility))
        return result


@dataclass(frozen=True)
class ViewTransform:
    source_width: int
    source_height: int
    width: int
    height: int

    @property
    def geometry(self):
        scale = min(self.width / self.source_width, self.height / self.source_height)
        w, h = round(self.source_width * scale), round(self.source_height * scale)
        return (self.width - w)//2, (self.height - h)//2, w, h

    def to_source(self, x, y, clamp=False):
        left, top, w, h = self.geometry
        if not clamp and not (left <= x < left+w and top <= y < top+h):
            return None
        return (
            max(0, min(self.source_width-1, int((x-left)*self.source_width/w))),
            max(0, min(self.source_height-1, int((y-top)*self.source_height/h))),
        )

    def render(self, frame):
        canvas = np.zeros((self.height, self.width, 3), np.uint8)
        left, top, w, h = self.geometry
        canvas[top:top+h, left:left+w] = cv2.resize(frame, (w, h))
        return canvas


def desktop_size():
    try:
        result = subprocess.run(["xrandr", "--listmonitors"], capture_output=True, text=True, timeout=3, check=True)
        monitors = sorted(result.stdout.splitlines()[1:], key=lambda line: "*" not in line)
        for line in monitors:
            match = re.search(r"(\d+)/\d+x(\d+)/\d+\+", line)
            if match:
                return tuple(map(int, match.groups()))
    except (OSError, subprocess.SubprocessError):
        pass
    return 1280, 720


def window_closed(window):
    try:
        visible = cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE)
        return visible == 0 if visible >= 0 else cv2.getWindowProperty(window, cv2.WND_PROP_FULLSCREEN) < 0
    except cv2.error:
        return True


class FullscreenView:
    def __init__(self, window="Week 7 Topcam"):
        self.window = window
        width, height = desktop_size()
        cv2.namedWindow(window, cv2.WINDOW_NORMAL | cv2.WINDOW_FREERATIO)
        cv2.resizeWindow(window, width, height)
        cv2.imshow(window, np.zeros((height, width, 3), np.uint8))
        cv2.setWindowProperty(window, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        cv2.waitKey(30)
        self.transform = ViewTransform(640, 480, width, height)

    def show(self, frame, prompt, detail=""):
        self.transform = ViewTransform(frame.shape[1], frame.shape[0], self.transform.width, self.transform.height)
        canvas = self.transform.render(frame)
        for y, text in ((27, prompt), (54, detail)):
            cv2.putText(canvas, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 0, 0), 4)
            cv2.putText(canvas, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 255), 1)
        cv2.imshow(self.window, canvas)


def annotate_frame(frame, view, config):
    session = AnnotationSession(config)
    drag = {"start": None, "end": None}

    def mouse(event, x, y, flags, userdata):
        point = view.transform.to_source(x, y, clamp=drag["start"] is not None)
        if point is None or session.done:
            return
        index, kind = session.stages[session.step]
        if kind == "box":
            if event == cv2.EVENT_LBUTTONDOWN:
                session.reset_current()
                drag["start"] = drag["end"] = point
            elif event == cv2.EVENT_MOUSEMOVE and drag["start"] is not None:
                drag["end"] = point
            elif event == cv2.EVENT_LBUTTONUP and drag["start"] is not None:
                box = clipped_roi(drag["start"], point, frame.shape)
                if box[2] > 2 and box[3] > 2:
                    session.boxes[index] = box
                drag["start"] = drag["end"] = None
        elif event == cv2.EVENT_LBUTTONDOWN:
            session.points[index] = tuple(map(float, point))
            if session.visibility[index] == 0:
                session.visibility[index] = 2

    cv2.setMouseCallback(view.window, mouse)
    try:
        while not session.done:
            display = frame.copy()
            for a in session.annotations(frame.shape):
                x, y, w, h = a.roi
                color = class_color(a.class_id)
                cv2.rectangle(display, (x, y), (x+w, y+h), color, 2)
                if a.visibility:
                    cv2.drawMarker(display, tuple(map(int, a.keypoint)), color, cv2.MARKER_CROSS, 20, 2)
            if drag["start"] is not None:
                cv2.rectangle(display, drag["start"], drag["end"], (0, 255, 255), 2)
            index, kind = session.stages[session.step]
            name = config.names[index]
            view.show(
                display, f"{session.step+1}/{len(session.stages)} {name}: {'drag BOX' if kind == 'box' else 'click POINT'} | SPACE: next/save | N: absent",
                "BACKSPACE: previous | R: redo | ESC: cancel",
            )
            key = cv2.waitKey(20) & 0xff
            if window_closed(view.window) or key in (27, ord("q"), ord("Q")):
                return None
            if key in (8, 127):
                session.back()
                drag["start"] = drag["end"] = None
            elif key in (ord("r"), ord("R")):
                session.reset_current()
                drag["start"] = drag["end"] = None
            elif key in (ord("n"), ord("N")):
                session.advance(absent=True)
                drag["start"] = drag["end"] = None
            elif key == 32 and drag["start"] is None:
                session.advance()
        return session.annotations(frame.shape)
    finally:
        cv2.setMouseCallback(view.window, lambda *args: None)


def ensure_dataset(root, config):
    root.mkdir(parents=True, exist_ok=True)
    metadata = root / "vision.json"
    if metadata.exists():
        check_contract(metadata, config)
    elif any((root / "raw/images").glob("*.jpg")):
        raise ValueError("기존 데이터에 기준점 설정 기록이 없습니다. --dataset-dir로 새 폴더를 지정하세요.")
    else:
        write_contract(metadata, config)


def valid_samples(root):
    images = sorted((root / "raw/images").glob("*.jpg"))
    missing = [p.name for p in images if not (root / "raw/labels" / (p.stem+".txt")).is_file()]
    if missing:
        raise ValueError(f"라벨이 없는 이미지가 있습니다: {missing[:5]}")
    return images


def save_sample(frame, text, root, config):
    validate_label_text(text, config)
    ensure_dataset(root, config)
    for folder in ("raw/images", "raw/labels"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    stem = time.strftime("frame_%Y%m%d_%H%M%S") + f"_{time.time_ns()%1_000_000_000:09d}"
    image, label = root / "raw/images" / (stem+".jpg"), root / "raw/labels" / (stem+".txt")
    if not cv2.imwrite(str(image), sample_frame(frame, config)):
        raise RuntimeError(f"이미지 저장 실패: {image}")
    try:
        label.write_text(text, encoding="utf-8")
    except Exception:
        image.unlink(missing_ok=True)
        raise
    return image


def delete_latest_sample(root):
    samples = valid_samples(root)
    if not samples:
        return None
    latest = max(samples, key=lambda p: p.stat().st_mtime_ns)
    latest.unlink()
    (root / "raw/labels" / (latest.stem+".txt")).unlink()
    return latest


def prepare_dataset(root, config):
    ensure_dataset(root, config)
    samples = valid_samples(root)
    if not samples:
        raise ValueError("학습용 이미지가 없습니다. 먼저 데이터를 수집하세요.")
    for image in samples:
        validate_label_text((root / "raw/labels" / (image.stem+".txt")).read_text(encoding="utf-8"), config)
    shuffled = samples.copy()
    random.Random(config.data["training"]["seed"]).shuffle(shuffled)
    ratio = config.data["training"]["validation_ratio"]
    count = max(1, min(len(samples)-1, round(len(samples)*ratio))) if len(samples)>1 else 0
    val = {p.name for p in shuffled[:count]}
    for kind in ("images", "labels"):
        for split in ("train", "val"):
            directory = root / kind / split
            directory.mkdir(parents=True, exist_ok=True)
            for old in directory.iterdir():
                if old.is_file() and old.suffix in (".jpg", ".txt", ".cache"):
                    old.unlink()
    for image in samples:
        split = "val" if image.name in val else "train"
        shutil.copy2(image, root / "images" / split / image.name)
        label = root / "raw/labels" / (image.stem+".txt")
        shutil.copy2(label, root / "labels" / split / label.name)
    # Ultralytics may cache sibling labels/train.cache and labels/val.cache.
    for split in ("train", "val"):
        (root / "labels" / (split+".cache")).unlink(missing_ok=True)
    data = {"path": root.resolve().as_posix(), "train": "images/train", "val": "images/val",
            "kpt_shape": [1, 3], "flip_idx": [0], "names": config.names}
    (root / "dataset.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return len(samples)-count, count


def collect(args, root, config):
    ensure_dataset(root, config)
    capture = open_source(config, args.source, args.sensor_id)
    try:
        view = FullscreenView()
        while True:
            ok, frame = capture.read()
            if not ok:
                source = str(args.source or config.data["camera"]["source"])
                if source.lower() != "csi" and not source.isdigit():
                    break
                raise RuntimeError("카메라 프레임을 읽을 수 없습니다.")
            view.show(frame, "SPACE: freeze/label | U: delete latest | Q/ESC: finish", f"saved={len(valid_samples(root))}")
            key = cv2.waitKey(20) & 0xff
            if window_closed(view.window) or key in (27, ord("q"), ord("Q")):
                break
            if key in (ord("u"), ord("U")):
                print(f"Deleted: {delete_latest_sample(root)}")
            elif key == 32:
                frozen = frame.copy()
                annotations = annotate_frame(frozen, view, config)
                if annotations is not None:
                    h, w = frozen.shape[:2]
                    text = "".join(yolo_pose_label(a, w, h) for a in annotations)
                    print(f"Saved: {save_sample(frozen, text, root, config).name}")
    finally:
        capture.release()
        cv2.destroyAllWindows()


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dataset-dir", type=Path)
    parser.add_argument("--source")
    parser.add_argument("--sensor-id", type=int)
    parser.add_argument("--prepare-only", action="store_true")
    return parser.parse_args()


def main():
    args = parse_arguments()
    config = load_config(args.config, ROOT)
    root = args.dataset_dir.expanduser().resolve() if args.dataset_dir else config.path_for("dataset")
    if not args.prepare_only:
        collect(args, root, config)
        if not valid_samples(root):
            print("저장한 이미지가 없어 정상 종료합니다.")
            return
    train, val = prepare_dataset(root, config)
    print(f"Dataset: {root / 'dataset.yaml'} | train={train}, val={val}")


if __name__ == "__main__":
    main()
