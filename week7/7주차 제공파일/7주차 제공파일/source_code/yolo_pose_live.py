#!/usr/bin/env python3
"""Monitor configured cube/tip pixels without ROS or robot motion."""

from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
import time
import cv2

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "week07_vision_control"))
from week07_vision_control.vision_common import (
    draw_detections, load_config, load_model, open_source, predict, sample_frame,
)
from yolo_dataset_tool import DEFAULT_CONFIG, FullscreenView, window_closed


def parse_arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--model", type=Path)
    p.add_argument("--source")
    p.add_argument("--sensor-id", type=int)
    p.add_argument("--device")
    p.add_argument("--confidence", type=float)
    p.add_argument("--keypoint-confidence", type=float)
    p.add_argument("--max-frames", type=int, default=0, help="0: until Q/ESC")
    return p.parse_args()


def format_console_line(detections, config, fps):
    fields = [f"FPS={fps:.1f}"]
    for item in config.classes:
        d = detections.get(item["name"])
        if d is None:
            fields.append(f"{item['name']}=NOT_DETECTED")
        else:
            u, v = d["point"]
            text = f"{item['name']}=({u:.1f},{v:.1f}) box_conf={d['confidence']:.2f}"
            if d["keypoint_confidence"] is not None:
                text += f" kpt_conf={d['keypoint_confidence']:.2f}"
            fields.append(text)
    return " | ".join(fields)


def main():
    os.environ["YOLO_AUTOINSTALL"] = "false"
    args = parse_arguments()
    config = load_config(args.config, ROOT)
    if args.device:
        config.data["inference"]["device"] = args.device
    for name, key in (("confidence", "confidence"), ("keypoint_confidence", "keypoint_confidence")):
        value = getattr(args, name)
        if value is not None:
            if not 0 <= value <= 1:
                raise ValueError("Confidence는 [0, 1] 범위여야 합니다.")
            config.data["inference"][key] = value
    if args.max_frames < 0:
        raise ValueError("--max-frames는 0 이상이어야 합니다.")
    model = load_model(args.model.expanduser().resolve() if args.model else config.path_for("model"), config)
    capture = open_source(config, args.source, args.sensor_id)
    count, last_print = 0, 0.0
    try:
        view = FullscreenView("Week 7 YOLO monitor")
        while True:
            started = time.monotonic()
            ok, frame = capture.read()
            if not ok:
                source = args.source or str(config.data["camera"]["source"])
                if source != "csi" and not source.isdigit():
                    break
                raise RuntimeError("카메라 프레임을 읽을 수 없습니다.")
            detections = predict(model, sample_frame(frame, config), config)
            fps = 1 / max(time.monotonic()-started, 1e-6)
            status = format_console_line(detections, config, fps)
            view.show(draw_detections(frame, detections, config), "Q/ESC: finish | coordinates: saved image pixels", status)
            if time.monotonic() - last_print >= .5:
                print("\r"+status+" "*15, end="", flush=True)
                last_print = time.monotonic()
            count += 1
            key = cv2.waitKey(1) & 0xff
            if key in (27, ord("q"), ord("Q")) or window_closed(view.window) or (args.max_frames and count >= args.max_frames):
                break
    finally:
        print()
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
