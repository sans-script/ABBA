#!/usr/bin/env python3
"""
Render the site's sequence to an MP4.

Serves site/ locally, opens it in headless Chrome in capture mode
(?capture), steps the timeline frame by frame with window.seek(t) over the
DevTools protocol, screenshots each frame and encodes them with ffmpeg.
Frame-accurate regardless of how fast the machine renders.

Requirements:
    pip install websocket-client imageio-ffmpeg
    Google Chrome (or Edge) installed

Usage:
    python tools/render_video.py                       # renders/no-bugs-just-vibes.mp4
    python tools/render_video.py --fps 30 --out renders/take.mp4
"""

from __future__ import annotations

import argparse
import base64
import functools
import http.server
import json
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import imageio_ffmpeg
import websocket


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DEFAULT_OUT = ROOT / "renders" / "no-bugs-just-vibes.mp4"

BROWSERS = [
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/usr/bin/google-chrome"),
    Path("/usr/bin/chromium"),
]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve_site() -> int:
    port = free_port()
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(SITE)
    )
    handler.log_message = lambda *args: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return port


class DevTools:
    """Minimal synchronous Chrome DevTools protocol client."""

    def __init__(self, url: str):
        self.ws = websocket.create_connection(url, timeout=120, suppress_origin=True)
        self.next_id = 0

    def call(self, method: str, **params) -> dict:
        self.next_id += 1
        self.ws.send(json.dumps({"id": self.next_id, "method": method, "params": params}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") == self.next_id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})

    def evaluate(self, expression: str):
        result = self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return result["result"].get("value")


def open_page(browser: Path, url: str, width: int, height: int, profile: Path):
    port = free_port()
    process = subprocess.Popen([
        str(browser),
        "--headless=new",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        f"--window-size={width},{height}",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for _ in range(100):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json") as response:
                pages = [t for t in json.load(response) if t["type"] == "page"]
            if pages:
                return process, DevTools(pages[0]["webSocketDebuggerUrl"])
        except OSError:
            pass
        time.sleep(0.1)

    process.kill()
    raise RuntimeError("Browser did not start")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the site sequence to MP4.")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--crf", type=int, default=18, help="x264 quality (lower = better)")
    args = parser.parse_args()

    browser = next((b for b in BROWSERS if b.exists()), None)
    if browser is None:
        raise SystemExit("Chrome or Edge not found.")

    port = serve_site()
    work = Path(tempfile.mkdtemp(prefix="render-"))
    frames = work / "frames"
    frames.mkdir()

    process, page = open_page(
        browser, f"http://127.0.0.1:{port}/?capture", args.width, args.height, work / "profile"
    )

    try:
        page.call("Emulation.setDeviceMetricsOverride", width=args.width, height=args.height,
                  deviceScaleFactor=1, mobile=False)

        for _ in range(200):
            if page.evaluate("typeof window.seek === 'function'"):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Page never exposed window.seek")

        duration = page.evaluate("window.videoDuration")
        count = round(duration * args.fps)
        print(f"Rendering {duration:.1f}s at {args.fps} fps: {count} frames")

        started = time.time()
        for i in range(count):
            page.evaluate(f"window.seek({i / args.fps})")
            shot = page.call("Page.captureScreenshot", format="jpeg", quality=95)
            (frames / f"{i:05d}.jpg").write_bytes(base64.b64decode(shot["data"]))
            if i % args.fps == 0:
                rate = (i + 1) / max(0.001, time.time() - started)
                print(f"  {i}/{count} frames ({rate:.1f} frames/s)")
    finally:
        process.kill()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
        "-framerate", str(args.fps), "-i", str(frames / "%05d.jpg"),
        "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(args.out),
    ], check=True)

    shutil.rmtree(work, ignore_errors=True)
    size = args.out.stat().st_size / 1e6
    print(f"Wrote {args.out} ({size:.1f} MB)")


if __name__ == "__main__":
    main()
