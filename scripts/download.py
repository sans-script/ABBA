from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SOURCE_URL = "https://www.youtube.com/watch?v=ulZQTrV8QlQ"
OUTPUT = Path(__file__).resolve().parents[1] / "media" / "ABBA - Lay All Your Love On Me.mp4"


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "-f",
        "bestvideo",
        "--recode-video",
        "mp4",
        "-o",
        str(OUTPUT),
        SOURCE_URL,
    ]

    print(f"Downloading video without audio to: {OUTPUT}")
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError:
        print("Python was not found.", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"Download failed with exit code {exc.returncode}.", file=sys.stderr)
        return exc.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
