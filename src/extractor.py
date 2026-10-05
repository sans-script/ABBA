#!/usr/bin/env python3
"""
ABBA Video Frame Extractor
==========================

A frame extraction and visual analysis utility for studying video
transitions, typography, assets, composition, and animation.

Designed for reverse-engineering music videos and motion graphics.

Requirements:
    pip install opencv-python

Examples:

    # Extract 100 evenly spaced frames from the entire video
    python src/extractor.py --count 100

    # Extract 5 frames per second from the entire video
    python src/extractor.py --fps 5

    # Extract 60 consecutive frames from a transition
    python src/extractor.py --start 12.5 --end 14.0 --fps 60

    # Extract every frame from a short transition
    python src/extractor.py --start 12.5 --end 14.0 --all

    # Detect likely scene changes
    python src/extractor.py --scenes

    # Generate a contact sheet from extracted frames
    python src/extractor.py --count 100 --contact-sheet

Output structure:

    analysis/
    ├── metadata.txt
    ├── frames/
    │   ├── 000001__frame-00000000__t-00h00m00s000ms.png
    │   ├── 000002__frame-00000009__t-00h00m00s360ms.png
    │   └── ...
    └── contact_sheet.jpg
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2


DEFAULT_VIDEO = "media/ABBA - Lay All Your Love On Me.mp4"
DEFAULT_OUTPUT = "analysis"


@dataclass
class VideoInfo:
    fps: float
    total_frames: int
    duration: float
    width: int
    height: int
    codec: str


def get_video_info(cap: cv2.VideoCapture) -> VideoInfo:
    """Read basic metadata from an opened video."""

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    duration = total_frames / fps if fps > 0 else 0.0

    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    codec = "".join(
        chr((fourcc >> (8 * i)) & 0xFF)
        for i in range(4)
    ).strip()

    return VideoInfo(
        fps=fps,
        total_frames=total_frames,
        duration=duration,
        width=width,
        height=height,
        codec=codec or "unknown",
    )


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm."""

    milliseconds = int(round((seconds % 1) * 1000))
    total_seconds = int(seconds)

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def validate_range(
    info: VideoInfo,
    start: float,
    end: float | None,
) -> tuple[float, float]:
    """Validate and clamp the requested time range."""

    start = max(0.0, start)

    if end is None:
        end = info.duration
    else:
        end = min(info.duration, end)

    if start >= info.duration:
        raise ValueError(
            f"Start time ({start:.3f}s) is outside the video duration "
            f"({info.duration:.3f}s)."
        )

    if end <= start:
        raise ValueError(
            "End time must be greater than start time."
        )

    return start, end


def timestamp_to_frame(
    timestamp: float,
    fps: float,
    total_frames: int,
) -> int:
    """Convert a timestamp to the nearest valid frame index."""

    frame = int(round(timestamp * fps))

    return max(
        0,
        min(frame, total_frames - 1),
    )


def frame_to_timestamp(frame_index: int, fps: float) -> float:
    """Convert a frame index to seconds."""

    return frame_index / fps if fps > 0 else 0.0

def build_frame_filename(
    sequence_number: int,
    frame_number: int,
    timestamp: float,
    extension: str,
) -> str:
    """Create a filename that sorts chronologically in any file browser."""

    total_milliseconds = int(round(timestamp * 1000))

    hours = total_milliseconds // 3_600_000
    remaining = total_milliseconds % 3_600_000

    minutes = remaining // 60_000
    remaining %= 60_000

    seconds = remaining // 1_000
    milliseconds = remaining % 1_000

    return (
        f"{sequence_number:06d}"
        f"__frame-{frame_number:08d}"
        f"__t-{hours:02d}h{minutes:02d}m"
        f"{seconds:02d}s{milliseconds:03d}ms"
        f".{extension}"
    )

def extract_frames_by_indices(
    cap: cv2.VideoCapture,
    frame_indices: list[int],
    info: VideoInfo,
    output_dir: Path,
    prefix: str,
    extension: str = "png",
    jpeg_quality: int = 95,
) -> int:
    """
    Extract specific frames sequentially.

    Unlike repeatedly calling cap.set(), this seeks only when necessary
    and reads frames in increasing order.
    """

    if not frame_indices:
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)

    frame_indices = sorted(set(frame_indices))

    saved = 0
    target_index = 0

    for frame_index in frame_indices:
        if not cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index):
            print(
                f"[warning] Could not seek to frame "
                f"{frame_index}."
            )
            continue

        ok, frame = cap.read()

        if not ok:
            print(
                f"[warning] Could not read frame "
                f"{frame_index}."
            )
            continue

        timestamp = frame_to_timestamp(
            frame_index,
            info.fps,
        )

        filename = build_frame_filename(
            sequence_number=saved + 1,
            frame_number=frame_index,
            timestamp=timestamp,
            extension=extension,
        )

        path = output_dir / filename

        if extension == "jpg":
            ok = cv2.imwrite(
                str(path),
                frame,
                [
                    cv2.IMWRITE_JPEG_QUALITY,
                    jpeg_quality,
                ],
            )
        else:
            ok = cv2.imwrite(
                str(path),
                frame,
            )

        if ok:
            saved += 1
            target_index += 1

            print(
                f"[{target_index}/{len(frame_indices)}] "
                f"frame={frame_index:08d} "
                f"time={format_timestamp(timestamp)}"
            )
        else:
            print(
                f"[warning] Failed to save: {path}"
            )

    return saved


def extract_uniform(
    cap: cv2.VideoCapture,
    info: VideoInfo,
    count: int,
    start: float,
    end: float,
    output_dir: Path,
    prefix: str,
    extension: str,
) -> int:
    """Extract a fixed number of evenly distributed frames."""

    if count < 1:
        raise ValueError(
            "--count must be at least 1."
        )

    if count == 1:
        timestamps = [start]
    else:
        step = (end - start) / (count - 1)

        timestamps = [
            start + i * step
            for i in range(count)
        ]

    indices = [
        timestamp_to_frame(
            timestamp,
            info.fps,
            info.total_frames,
        )
        for timestamp in timestamps
    ]

    return extract_frames_by_indices(
        cap,
        indices,
        info,
        output_dir,
        prefix,
        extension,
    )


def extract_by_fps(
    cap: cv2.VideoCapture,
    info: VideoInfo,
    target_fps: float,
    start: float,
    end: float,
    output_dir: Path,
    prefix: str,
    extension: str,
) -> int:
    """Extract frames at a fixed sampling rate."""

    if target_fps <= 0:
        raise ValueError(
            "--fps must be greater than 0."
        )

    interval = 1.0 / target_fps

    timestamps = []
    timestamp = start

    while timestamp <= end:
        timestamps.append(timestamp)
        timestamp += interval

    indices = [
        timestamp_to_frame(
            timestamp,
            info.fps,
            info.total_frames,
        )
        for timestamp in timestamps
    ]

    return extract_frames_by_indices(
        cap,
        indices,
        info,
        output_dir,
        prefix,
        extension,
    )


def extract_all_frames(
    cap: cv2.VideoCapture,
    info: VideoInfo,
    start: float,
    end: float,
    output_dir: Path,
    prefix: str,
    extension: str,
) -> int:
    """Extract every frame within the requested time range."""

    start_frame = timestamp_to_frame(
        start,
        info.fps,
        info.total_frames,
    )

    end_frame = timestamp_to_frame(
        end,
        info.fps,
        info.total_frames,
    )

    indices = list(
        range(
            start_frame,
            end_frame + 1,
        )
    )

    return extract_frames_by_indices(
        cap,
        indices,
        info,
        output_dir,
        prefix,
        extension,
    )


def detect_scene_changes(
    cap: cv2.VideoCapture,
    info: VideoInfo,
    threshold: float,
    min_interval: float,
) -> list[tuple[int, float, float]]:
    """
    Detect major visual changes using frame-to-frame
    grayscale histogram difference.

    Returns:
        (frame_index, timestamp, difference)
    """

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    previous_histogram = None
    detected = []

    last_detection = -float("inf")

    frame_index = 0

    while True:
        ok, frame = cap.read()

        if not ok:
            break

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY,
        )

        histogram = cv2.calcHist(
            [gray],
            [0],
            None,
            [64],
            [0, 256],
        )

        cv2.normalize(
            histogram,
            histogram,
        )

        if previous_histogram is not None:
            difference = cv2.compareHist(
                previous_histogram,
                histogram,
                cv2.HISTCMP_BHATTACHARYYA,
            )

            timestamp = frame_to_timestamp(
                frame_index,
                info.fps,
            )

            if (
                difference >= threshold
                and timestamp - last_detection >= min_interval
            ):
                detected.append(
                    (
                        frame_index,
                        timestamp,
                        difference,
                    )
                )

                last_detection = timestamp

        previous_histogram = histogram
        frame_index += 1

    return detected


def save_scene_frames(
    cap: cv2.VideoCapture,
    info: VideoInfo,
    scenes: list[tuple[int, float, float]],
    output_dir: Path,
    extension: str,
) -> int:
    """Save frames detected as possible scene transitions."""

    indices = [scene[0] for scene in scenes]

    return extract_frames_by_indices(
        cap,
        indices,
        info,
        output_dir,
        prefix="scene",
        extension=extension,
    )


def create_contact_sheet(
    frames_dir: Path,
    output_path: Path,
    columns: int = 5,
    thumbnail_width: int = 320,
) -> None:
    """
    Create a contact sheet from extracted frames.

    This is especially useful for quickly giving an AI or a human
    an overview of the video's visual language.
    """

    image_paths = sorted(
        [
            path
            for path in frames_dir.iterdir()
            if path.suffix.lower() in {
                ".png",
                ".jpg",
                ".jpeg",
            }
        ]
    )

    if not image_paths:
        print(
            "[warning] No frames found for contact sheet."
        )
        return

    thumbnails = []

    for path in image_paths:
        image = cv2.imread(str(path))

        if image is None:
            continue

        height, width = image.shape[:2]

        scale = thumbnail_width / width

        thumbnail_height = int(
            height * scale
        )

        thumbnail = cv2.resize(
            image,
            (
                thumbnail_width,
                thumbnail_height,
            ),
            interpolation=cv2.INTER_AREA,
        )

        # Add filename label.
        label_height = 30

        labeled = cv2.copyMakeBorder(
            thumbnail,
            0,
            label_height,
            0,
            0,
            cv2.BORDER_CONSTANT,
            value=(20, 20, 20),
        )

        cv2.putText(
            labeled,
            path.stem,
            (8, thumbnail_height + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        thumbnails.append(labeled)

    if not thumbnails:
        return

    rows = []

    for i in range(0, len(thumbnails), columns):
        row = thumbnails[i:i + columns]

        while len(row) < columns:
            blank = row[0].copy()
            blank[:] = 0
            row.append(blank)

        rows.append(
            cv2.hconcat(row)
        )

    sheet = cv2.vconcat(rows)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cv2.imwrite(
        str(output_path),
        sheet,
        [
            cv2.IMWRITE_JPEG_QUALITY,
            90,
        ],
    )

    print(
        f"Contact sheet saved to: "
        f"{output_path}"
    )


def save_metadata(
    info: VideoInfo,
    video_path: Path,
    output_path: Path,
) -> None:
    """Save video metadata to a text file."""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    content = f"""Video Analysis
==============

File:
{video_path.name}

Path:
{video_path.resolve()}

Duration:
{info.duration:.3f} seconds
{format_timestamp(info.duration)}

FPS:
{info.fps:.6f}

Total frames:
{info.total_frames}

Resolution:
{info.width} x {info.height}

Codec:
{info.codec}

Aspect ratio:
{info.width / info.height:.4f}

Frame duration:
{1 / info.fps:.6f} seconds
"""

    output_path.write_text(
        content,
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract and analyze video frames for "
            "visual reverse-engineering."
        )
    )

    parser.add_argument(
        "--video",
        default=DEFAULT_VIDEO,
        help=(
            f"Video file "
            f"(default: '{DEFAULT_VIDEO}')."
        ),
    )

    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=(
            "Output directory "
            "(default: ./analysis)."
        ),
    )

    parser.add_argument(
        "--start",
        type=float,
        default=0.0,
        help="Start time in seconds.",
    )

    parser.add_argument(
        "--end",
        type=float,
        default=None,
        help="End time in seconds.",
    )

    mode = parser.add_mutually_exclusive_group()

    mode.add_argument(
        "--count",
        type=int,
        help=(
            "Extract N evenly spaced frames."
        ),
    )

    mode.add_argument(
        "--fps",
        type=float,
        help=(
            "Extract frames at a fixed FPS."
        ),
    )

    mode.add_argument(
        "--all",
        action="store_true",
        help=(
            "Extract every frame in the "
            "selected time range."
        ),
    )

    parser.add_argument(
        "--scenes",
        action="store_true",
        help=(
            "Detect and extract likely scene "
            "transitions."
        ),
    )

    parser.add_argument(
        "--scene-threshold",
        type=float,
        default=0.35,
        help=(
            "Histogram difference threshold "
            "for scene detection "
            "(default: 0.35)."
        ),
    )

    parser.add_argument(
        "--scene-min-interval",
        type=float,
        default=0.5,
        help=(
            "Minimum time between detected "
            "scenes in seconds "
            "(default: 0.5)."
        ),
    )

    parser.add_argument(
        "--contact-sheet",
        action="store_true",
        help="Generate a contact sheet.",
    )

    parser.add_argument(
        "--columns",
        type=int,
        default=5,
        help=(
            "Contact sheet columns "
            "(default: 5)."
        ),
    )

    parser.add_argument(
        "--format",
        choices=["png", "jpg"],
        default="png",
        help=(
            "Output image format "
            "(default: png)."
        ),
    )

    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=95,
        help=(
            "JPEG quality from 1 to 100 "
            "(default: 95)."
        ),
    )

    parser.add_argument(
        "--prefix",
        default="frame",
        help=(
            "Prefix for extracted frame filenames "
            "(default: frame)."
        ),
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    video_path = Path(args.video)

    if not video_path.is_file():
        sys.exit(
            f"Error: video not found:\n"
            f"{video_path.resolve()}"
        )

    if not 1 <= args.jpeg_quality <= 100:
        sys.exit(
            "Error: --jpeg-quality must be "
            "between 1 and 100."
        )

    if args.columns < 1:
        sys.exit(
            "Error: --columns must be at least 1."
        )

    cap = cv2.VideoCapture(
        str(video_path)
    )

    if not cap.isOpened():
        sys.exit(
            "Error: could not open the video. "
            "Check the codec and file format."
        )

    info = get_video_info(cap)

    print()
    print("=" * 60)
    print("VIDEO ANALYSIS")
    print("=" * 60)
    print(f"File       : {video_path.name}")
    print(
        f"Duration   : {info.duration:.3f}s "
        f"({format_timestamp(info.duration)})"
    )
    print(f"FPS        : {info.fps:.3f}")
    print(f"Frames     : {info.total_frames}")
    print(
        f"Resolution : "
        f"{info.width}x{info.height}"
    )
    print(f"Codec      : {info.codec}")
    print("=" * 60)
    print()

    output_dir = Path(args.output)

    frames_dir = output_dir / "frames"

    metadata_path = output_dir / "metadata.txt"

    save_metadata(
        info,
        video_path,
        metadata_path,
    )

    try:
        start, end = validate_range(
            info,
            args.start,
            args.end,
        )
    except ValueError as error:
        cap.release()
        sys.exit(f"Error: {error}")

    saved = 0

    try:
        if args.scenes:
            print(
                "Detecting scene transitions..."
            )

            scenes = detect_scene_changes(
                cap,
                info,
                threshold=args.scene_threshold,
                min_interval=args.scene_min_interval,
            )

            print(
                f"Detected {len(scenes)} "
                f"possible scene transitions."
            )

            scene_dir = output_dir / "scenes"

            saved = save_scene_frames(
                cap,
                info,
                scenes,
                scene_dir,
                args.format,
            )

            scenes_file = (
                output_dir /
                "scene_changes.txt"
            )

            with scenes_file.open(
                "w",
                encoding="utf-8",
            ) as file:
                for (
                    frame_index,
                    timestamp,
                    difference,
                ) in scenes:
                    file.write(
                        f"frame={frame_index} "
                        f"time={format_timestamp(timestamp)} "
                        f"difference={difference:.6f}\n"
                    )

        elif args.all:
            print(
                f"Extracting every frame from "
                f"{start:.3f}s to {end:.3f}s..."
            )

            saved = extract_all_frames(
                cap,
                info,
                start,
                end,
                frames_dir,
                args.prefix,
                args.format,
            )

        elif args.count is not None:
            print(
                f"Extracting {args.count} "
                f"uniformly spaced frames..."
            )

            saved = extract_uniform(
                cap,
                info,
                args.count,
                start,
                end,
                frames_dir,
                args.prefix,
                args.format,
            )

        elif args.fps is not None:
            print(
                f"Extracting at {args.fps:.3f} FPS..."
            )

            saved = extract_by_fps(
                cap,
                info,
                args.fps,
                start,
                end,
                frames_dir,
                args.prefix,
                args.format,
            )

        else:
            parser.error(
                "Specify one of --count, --fps, "
                "--all, or --scenes."
            )

    finally:
        cap.release()

    if args.contact_sheet:
        contact_sheet_path = (
            output_dir /
            "contact_sheet.jpg"
        )

        source_dir = (
            output_dir / "scenes"
            if args.scenes
            else frames_dir
        )

        create_contact_sheet(
            source_dir,
            contact_sheet_path,
            columns=args.columns,
        )

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"Frames saved : {saved}")
    print(
        f"Output       : "
        f"{output_dir.resolve()}"
    )
    print(
        f"Metadata     : "
        f"{metadata_path.resolve()}"
    )

    if args.contact_sheet:
        print(
            f"Contact sheet: "
            f"{(output_dir / 'contact_sheet.jpg').resolve()}"
        )

    print("=" * 60)


if __name__ == "__main__":
    main()