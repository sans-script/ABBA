#!/usr/bin/env python3
"""
FSD Input Preparation
=====================

Cuts a short clip out of the source video and writes it in the layout
FSD's sample-level optimization expects:

    analysis/fsd/inputs/<name>/
    ├── <name>.png    # APNG of the downscaled clip (FSD input)
    ├── <name>.json   # box prompts: key_box [y0, y1, x0, x1] normalized, key_index
    ├── meta.json     # source timestamps per clip frame (to map motion back to time)
    └── preview.jpg   # labeled frame grid with prompt boxes drawn

FSD is not fully automatic: it needs one box per sprite on a key frame.
Run once without --box to get preview.jpg, pick boxes, then run again.

FSD was tuned on ~228x128 clips of 50 frames; larger inputs are slower
and less tested.

Requirements:
    pip install opencv-python Pillow

Examples:

    # Step 1: cut a 2 s clip and inspect the preview
    python src/prepare_fsd.py --name lyric-was --start 52.0 --end 54.0

    # Step 2: same clip, one box per sprite, in source pixels at a source time
    python src/prepare_fsd.py --name lyric-was --start 52.0 --end 54.0 \\
        --box 240,500,620,780@53.6 --box 1200,80,1500,330@52.4
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from extractor import (
    DEFAULT_VIDEO,
    get_video_info,
    timestamp_to_frame,
    validate_range,
)


DEFAULT_OUTPUT = "analysis/fsd/inputs"


@dataclass
class BoxPrompt:
    """A sprite box in source pixel coordinates at a source timestamp."""

    x0: int
    y0: int
    x1: int
    y1: int
    time: float


def parse_box(spec: str) -> BoxPrompt:
    """Parse 'x0,y0,x1,y1@seconds'."""

    try:
        coords, time = spec.split("@")
        x0, y0, x1, y1 = (int(v) for v in coords.split(","))
        return BoxPrompt(x0, y0, x1, y1, float(time))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Invalid box '{spec}', expected x0,y0,x1,y1@seconds."
        ) from error


def sample_frame_indices(
    start_frame: int,
    end_frame: int,
    max_frames: int,
) -> list[int]:
    """Every frame in range, or an even subsample if there are too many."""

    indices = list(range(start_frame, end_frame + 1))

    if len(indices) <= max_frames:
        return indices

    picks = np.linspace(0, len(indices) - 1, max_frames)

    return [indices[int(round(p))] for p in picks]


def read_frames(
    cap: cv2.VideoCapture,
    indices: list[int],
) -> list[np.ndarray]:
    """Read frames (RGB) sequentially from the first index."""

    cap.set(cv2.CAP_PROP_POS_FRAMES, indices[0])

    wanted = set(indices)
    frames = []
    current = indices[0]

    while current <= indices[-1]:
        ok, frame = cap.read()

        if not ok:
            raise RuntimeError(f"Could not read frame {current}.")

        if current in wanted:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        current += 1

    return frames


def nearest_clip_index(source_frame: int, indices: list[int]) -> int:
    return int(np.argmin([abs(i - source_frame) for i in indices]))


def build_prompt(
    boxes: list[BoxPrompt],
    indices: list[int],
    fps: float,
    total_frames: int,
    width: int,
    height: int,
) -> dict:
    key_box = []
    key_index = []

    for box in boxes:
        x0, x1 = sorted((box.x0, box.x1))
        y0, y1 = sorted((box.y0, box.y1))

        key_box.append([
            max(0.0, y0 / height),
            min(1.0, y1 / height),
            max(0.0, x0 / width),
            min(1.0, x1 / width),
        ])

        source_frame = timestamp_to_frame(box.time, fps, total_frames)
        key_index.append(nearest_clip_index(source_frame, indices))

    return {"key_box": key_box, "key_index": key_index}


def save_apng(frames: list[np.ndarray], path: Path, fps: float) -> None:
    images = [Image.fromarray(f).convert("RGBA") for f in frames]

    images[0].save(
        path,
        format="PNG",
        save_all=True,
        append_images=images[1:],
        duration=round(1000 / fps),
        loop=0,
    )


def save_preview(
    frames: list[np.ndarray],
    indices: list[int],
    fps: float,
    prompt: dict | None,
    path: Path,
    columns: int = 10,
    scale: int = 2,
) -> None:
    """Grid of clip frames labeled 'index / source time', boxes drawn on key frames."""

    tiles = []

    for i, (frame, source_frame) in enumerate(zip(frames, indices)):
        h, w = frame.shape[:2]
        tile = cv2.resize(
            cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
            (w * scale, h * scale),
            interpolation=cv2.INTER_NEAREST,
        )

        if prompt is not None:
            for layer, (box, key) in enumerate(
                zip(prompt["key_box"], prompt["key_index"])
            ):
                if key != i:
                    continue

                y0, y1, x0, x1 = box
                th, tw = tile.shape[:2]
                cv2.rectangle(
                    tile,
                    (int(x0 * tw), int(y0 * th)),
                    (int(x1 * tw), int(y1 * th)),
                    (0, 255, 255),
                    1,
                )
                cv2.putText(
                    tile,
                    f"L{layer + 1}",
                    (int(x0 * tw) + 2, int(y0 * th) + 12),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (0, 255, 255),
                    1,
                    cv2.LINE_AA,
                )

        label = f"{i:02d}  {source_frame / fps:.2f}s"
        tile = cv2.copyMakeBorder(
            tile, 0, 18, 0, 0, cv2.BORDER_CONSTANT, value=(20, 20, 20)
        )
        cv2.putText(
            tile,
            label,
            (4, tile.shape[0] - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        tiles.append(tile)

    rows = []

    for i in range(0, len(tiles), columns):
        row = tiles[i:i + columns]

        while len(row) < columns:
            row.append(np.zeros_like(tiles[0]))

        rows.append(cv2.hconcat(row))

    cv2.imwrite(str(path), cv2.vconcat(rows), [cv2.IMWRITE_JPEG_QUALITY, 90])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare a clip and box prompts for FSD."
    )

    parser.add_argument("--video", default=DEFAULT_VIDEO)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--name",
        required=True,
        help="Clip id; used as folder and file name (no spaces).",
    )
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument(
        "--height",
        type=int,
        default=128,
        help="Clip height in pixels (default: 128, FSD's tuned scale).",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=50,
        help="Subsample evenly above this count (default: 50).",
    )
    parser.add_argument(
        "--box",
        type=parse_box,
        action="append",
        default=[],
        help="Sprite box 'x0,y0,x1,y1@seconds' in source pixels. Repeatable.",
    )

    return parser


def main() -> None:
    args = build_parser().parse_args()

    if any(c in args.name for c in " /\\"):
        sys.exit("Error: --name must not contain spaces or slashes.")

    cap = cv2.VideoCapture(args.video)

    if not cap.isOpened():
        sys.exit(f"Error: could not open video: {args.video}")

    info = get_video_info(cap)

    try:
        start, end = validate_range(info, args.start, args.end)
    except ValueError as error:
        cap.release()
        sys.exit(f"Error: {error}")

    indices = sample_frame_indices(
        timestamp_to_frame(start, info.fps, info.total_frames),
        timestamp_to_frame(end, info.fps, info.total_frames),
        args.max_frames,
    )

    try:
        frames = read_frames(cap, indices)
    finally:
        cap.release()

    width = round(info.width * args.height / info.height)
    frames = [
        cv2.resize(f, (width, args.height), interpolation=cv2.INTER_AREA)
        for f in frames
    ]

    out_dir = Path(args.output) / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    clip_fps = info.fps * (len(indices) - 1) / max(1, indices[-1] - indices[0])
    save_apng(frames, out_dir / f"{args.name}.png", clip_fps)

    meta = {
        "source_video": Path(args.video).name,
        "source_size": [info.width, info.height],
        "clip_size": [width, args.height],
        "source_fps": info.fps,
        "source_frames": indices,
        "source_times": [round(i / info.fps, 4) for i in indices],
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    prompt = None

    if args.box:
        prompt = build_prompt(
            args.box, indices, info.fps, info.total_frames, info.width, info.height
        )
        (out_dir / f"{args.name}.json").write_text(
            json.dumps(prompt), encoding="utf-8"
        )

    save_preview(frames, indices, info.fps, prompt, out_dir / "preview.jpg")

    print(f"Clip    : {len(frames)} frames, {width}x{args.height}, "
          f"{meta['source_times'][0]:.2f}s-{meta['source_times'][-1]:.2f}s")
    print(f"Output  : {out_dir.resolve()}")

    if prompt is None:
        print("No --box given: inspect preview.jpg, then rerun with one --box per sprite.")
    else:
        print(f"Prompts : {len(prompt['key_box'])} sprite(s), key frames {prompt['key_index']}")


if __name__ == "__main__":
    main()
