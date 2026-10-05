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

FSD needs one box per sprite on a key frame. --auto finds them: it boxes
every element that enters or leaves during the clip (lyrics), grouping by
when pixels settle on, so touching words that arrive at different times get
separate boxes. Elements present for the whole clip are left to FSD's
background layer. Always check preview.jpg before a GPU run.

FSD was tuned on ~228x128 clips of 50 frames; larger inputs are slower
and less tested.

Requirements:
    pip install opencv-python Pillow

Examples:

    # Step 1: cut a 2 s clip and inspect the preview
    python src/prepare_fsd.py --name lyric-was --start 52.0 --end 54.0

    # Step 2a: boxes found automatically
    python src/prepare_fsd.py --name lyric-was --start 52.0 --end 54.0 --auto

    # Step 2b: or by hand, in source pixels at a source time
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


@dataclass
class AutoSprite:
    """An element that appears (or disappears) during the clip."""

    box: list[float]  # [y0, y1, x0, x1] normalized
    key_index: int
    onset: int  # clip frame where it settles on (or, if leaving, off)
    leaving: bool
    area: int


def _brightness(frames: list[np.ndarray]) -> np.ndarray:
    """Per-pixel max channel in [0, 1], median-filtered against grain and stars."""

    return np.stack([
        cv2.medianBlur(f.max(axis=-1), 3) for f in frames
    ]).astype(np.float32) / 255


def _settle_onsets(v: np.ndarray, threshold: float) -> tuple[np.ndarray, np.ndarray]:
    """
    For each pixel bright in the last frames: the frame after which it stays
    at >= 50% of its final brightness (0 if it was already there at frame 0).

    Uses the *last* off->on transition, so a pixel briefly lit by something
    else early on (a fading glow) is still timed by when its element arrives.
    """

    t = len(v)
    final = np.median(v[-3:], axis=0)
    on = v >= 0.5 * final

    # Temporal majority over 3 frames, against flicker.
    smooth = on.copy()
    smooth[1:-1] = (on[:-2].astype(np.uint8) + on[1:-1] + on[2:]) >= 2

    off = ~smooth
    ever_off = off.any(axis=0)
    last_off = t - 1 - off[::-1].argmax(axis=0)
    onset = np.where(ever_off, last_off + 1, 0)

    candidate = (final > threshold) & smooth[-1] & (onset >= 1)
    return onset, candidate


def _onset_bursts(onsets: np.ndarray, frames: int, max_gap: int) -> list[tuple[int, int]]:
    """
    Frame ranges where many pixels settle at once.

    An element arriving (fade, pop, write-on) lights its pixels within a few
    frames: a burst in the onset histogram. A slow camera zoom or drift makes
    static edges settle at a steady trickle across the whole clip: the
    baseline. Bursts are frames well above that baseline, merged across
    small gaps, then widened while still clearly above it.
    """

    hist = np.bincount(onsets, minlength=frames)[:frames].astype(float)
    hist[0] = 0
    baseline = max(1.0, float(np.median(hist[1:])))
    peaks = np.nonzero(hist > 2.0 * baseline)[0]

    if peaks.size == 0:
        return []

    runs = []
    start = prev = int(peaks[0])

    for frame in peaks[1:]:
        if frame - prev > max_gap:
            runs.append([start, prev])
            start = int(frame)
        prev = int(frame)

    runs.append([start, prev])

    for run in runs:
        while run[0] > 1 and hist[run[0] - 1] > 1.25 * baseline:
            run[0] -= 1
        while run[1] < frames - 1 and hist[run[1] + 1] > 1.25 * baseline:
            run[1] += 1

    return [(a, b) for a, b in runs]


def _grow_locally(
    core: np.ndarray,
    mask: np.ndarray,
    onset: np.ndarray,
    run: tuple[int, int],
    max_gap: int,
    kernel: np.ndarray,
) -> np.ndarray:
    """
    Extend a burst core to the rest of its element.

    A write-on settles letter by letter, too thinly to stand out against the
    whole frame's zoom trickle, but clearly against its own neighbourhood.
    Repeatedly: look at the onsets around the core, widen the time window
    while frames there are still busy, and take the window's pixels that
    connect to the core.
    """

    h, w = mask.shape
    first, last = run

    for _ in range(6):
        ys, xs = np.nonzero(core)
        margin = max(4, (ys.max() - ys.min()) // 2)
        y0, y1 = max(0, ys.min() - margin), min(h, ys.max() + 1 + margin)
        x0, x1 = max(0, xs.min() - margin), min(w, xs.max() + 1 + margin)

        local_mask = mask[y0:y1, x0:x1]
        local_onset = onset[y0:y1, x0:x1]
        hist = np.bincount(local_onset[local_mask], minlength=int(onset.max()) + 1)
        floor = max(2.0 * float(np.median(hist[1:])), 0.03 * core.sum() / max(1, last - first + 1))

        def busy(frame: int) -> bool:
            return 0 < frame < len(hist) and hist[frame] > floor

        new_first, new_last = first, last
        while any(busy(new_first - d) for d in range(1, max_gap + 1)):
            new_first -= next(d for d in range(1, max_gap + 1) if busy(new_first - d))
        while any(busy(new_last + d) for d in range(1, max_gap + 1)):
            new_last += next(d for d in range(1, max_gap + 1) if busy(new_last + d))

        window = np.zeros_like(mask)
        window[y0:y1, x0:x1] = local_mask & (local_onset >= new_first) & (local_onset <= new_last)
        joined = cv2.morphologyEx(window.astype(np.uint8), cv2.MORPH_CLOSE, kernel, iterations=3)
        count, labels = cv2.connectedComponents(joined)
        touching = set(np.unique(labels[core & (joined > 0)])) - {0}
        grown = np.isin(labels, list(touching)) & window

        if grown.sum() <= core.sum() and (new_first, new_last) == (first, last):
            break

        core = grown | core
        first, last = new_first, new_last

    return core


def _detect(
    v: np.ndarray,
    threshold: float,
    max_gap: int,
    min_area: int,
    leaving: bool,
) -> list[AutoSprite]:
    t, h, w = v.shape
    onset, candidate = _settle_onsets(v, threshold)

    # Opening drops stars/grain and the thinnest zoom fringes;
    # closing joins the letters of a word.
    k = max(3, round(h * 0.012)) | 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(candidate.astype(np.uint8), cv2.MORPH_OPEN, kernel) > 0

    sprites = []

    # Elements that touch but arrive at different times land in different
    # bursts, so they get separate boxes; a write-on stays in one burst.
    for first, last in _onset_bursts(onset[mask], t, max_gap):
        part = (mask & (onset >= first) & (onset <= last)).astype(np.uint8)
        part = cv2.morphologyEx(part, cv2.MORPH_OPEN, kernel)
        joined = cv2.morphologyEx(part, cv2.MORPH_CLOSE, kernel, iterations=3)
        count, labels = cv2.connectedComponents(joined)

        for label in range(1, count):
            pixels = (labels == label) & (part > 0)

            if pixels.sum() < min_area:
                continue

            pixels = _grow_locally(pixels, mask, onset, (first, last), max_gap, kernel)
            area = int(pixels.sum())

            ys, xs = np.nonzero(pixels)
            pad = 2
            box = [
                max(0, ys.min() - pad) / h,
                min(h, ys.max() + 1 + pad) / h,
                max(0, xs.min() - pad) / w,
                min(w, xs.max() + 1 + pad) / w,
            ]
            on_frame = int(np.median(onset[pixels]))

            # Key frame: where the element is fully settled (last frame, or
            # first frame for one that leaves), in original time order.
            sprites.append(AutoSprite(
                box=box,
                key_index=0 if leaving else t - 1,
                onset=t - on_frame if leaving else on_frame,
                leaving=leaving,
                area=area,
            ))

    return sprites


def _iou(a: list[float], b: list[float]) -> float:
    y0, y1 = max(a[0], b[0]), min(a[1], b[1])
    x0, x1 = max(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, y1 - y0) * max(0.0, x1 - x0)
    union = (a[1] - a[0]) * (a[3] - a[2]) + (b[1] - b[0]) * (b[3] - b[2]) - inter
    return inter / union if union > 0 else 0.0


def auto_boxes(
    frames: list[np.ndarray],
    threshold: float = 0.45,
    max_gap: int = 3,
    max_sprites: int = 6,
) -> tuple[list[AutoSprite], list[AutoSprite]]:
    """
    Find elements that enter or leave during the clip, one box per element.

    Elements present for the whole clip (static shapes) are left to FSD's
    background layer: FSD tries every layer order, which grows factorially
    with the sprite count. Returns (kept, dropped).
    """

    v = _brightness(frames)
    h, w = v.shape[1:]
    min_area = round(h * w * 0.002)

    found = []
    for sprite in sorted(
        _detect(v, threshold, max_gap, min_area, leaving=False),
        key=lambda s: s.area,
        reverse=True,
    ):
        if all(_iou(sprite.box, f.box) < 0.5 for f in found):
            found.append(sprite)
    found += [
        s for s in _detect(v[::-1], threshold, max_gap, min_area, leaving=True)
        if all(_iou(s.box, f.box) < 0.5 for f in found)
    ]
    found.sort(key=lambda s: s.area, reverse=True)

    kept = sorted(found[:max_sprites], key=lambda s: (s.onset, s.box[2]))
    return kept, found[max_sprites:]


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
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Box elements that enter or leave during the clip automatically.",
    )
    parser.add_argument(
        "--max-sprites",
        type=int,
        default=6,
        help="--auto cap; FSD's layer-order search is factorial (default: 6).",
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

    if args.auto:
        kept, dropped = auto_boxes(frames, max_sprites=args.max_sprites)
        prompt = prompt or {"key_box": [], "key_index": []}
        first = len(prompt["key_box"])

        for n, sprite in enumerate(kept, start=first + 1):
            prompt["key_box"].append(sprite.box)
            prompt["key_index"].append(sprite.key_index)
            y0, y1, x0, x1 = sprite.box
            print(
                f"L{n}: {'leaves' if sprite.leaving else 'enters'} at "
                f"{meta['source_times'][min(sprite.onset, len(indices) - 1)]:.2f}s  "
                f"box x {x0 * info.width:.0f}-{x1 * info.width:.0f}, "
                f"y {y0 * info.height:.0f}-{y1 * info.height:.0f} (source px)"
            )

        if dropped:
            print(f"Dropped {len(dropped)} smaller element(s) over --max-sprites.")

        if not prompt["key_box"]:
            print("No entering/leaving elements found.")
            prompt = None

    if prompt is not None:
        (out_dir / f"{args.name}.json").write_text(
            json.dumps(prompt), encoding="utf-8"
        )

    save_preview(frames, indices, info.fps, prompt, out_dir / "preview.jpg")

    print(f"Clip    : {len(frames)} frames, {width}x{args.height}, "
          f"{meta['source_times'][0]:.2f}s-{meta['source_times'][-1]:.2f}s")
    print(f"Output  : {out_dir.resolve()}")

    if prompt is None:
        print("No boxes: inspect preview.jpg, then rerun with --auto or --box.")
    else:
        print(f"Prompts : {len(prompt['key_box'])} sprite(s), key frames {prompt['key_index']}")


if __name__ == "__main__":
    main()
