#!/usr/bin/env python3
"""Cut annotated screenshots from the local recording for a list of moments.

Local only: reads the video (ffmpeg) and a steps JSON, writes PNGs. No network, no credentials.

Usage:
    python scripts/frames.py out/S1-U01.mp4 steps.json --outdir out/frames_61 [--width 1280]

steps.json: [{"key": "s05", "t": "23:58", "marks": [{"x": 812, "y": 64, "kind": "click", "label": "1"}],
              "box": [x0, y0, x1, y1]}]
- x / y are normalised 0–1000 (as reported by the observation pass); -1 = no marker.
- kind "click": filled numbered circle · "cursor": ring · box: dashed rectangle (attention).
Markers follow the GOMS board legend. The raw frame is kept next to the annotated one
(<key>_raw.png) so every marker can be checked against the untouched image.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ACCENT = (230, 57, 70)      # click / problem red
CURSOR = (29, 120, 220)     # cursor ring blue


def to_seconds(ts: str) -> float:
    total = 0.0
    for p in str(ts).split(":"):
        total = total * 60 + float(p)
    return total


def grab(video: Path, t: float, out: Path, width: int) -> None:
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video),
           "-frames:v", "1", "-vf", f"scale={width}:-2", str(out)]
    subprocess.run(cmd, check=True)


def dashed_rect(draw: ImageDraw.ImageDraw, box, color, dash=10, width=3) -> None:
    x0, y0, x1, y1 = box
    for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        length = max(abs(bx - ax), abs(by - ay))
        for s in range(0, int(length), dash * 2):
            f0, f1 = s / length, min(s + dash, length) / length
            draw.line((ax + (bx - ax) * f0, ay + (by - ay) * f0, ax + (bx - ax) * f1, ay + (by - ay) * f1),
                      fill=color, width=width)


def annotate(raw: Path, out: Path, marks: list, box, crop) -> None:
    """Markers/box are normalised to the FULL frame; crop (also normalised) keeps only the shared
    screen so participants' webcam tiles (face, name) never reach a deliverable."""
    img = Image.open(raw).convert("RGB")
    fw, fh = img.size
    cx0, cy0, cx1, cy1 = (crop[0] * fw / 1000, crop[1] * fh / 1000, crop[2] * fw / 1000, crop[3] * fh / 1000)
    img = img.crop((int(cx0), int(cy0), int(cx1), int(cy1)))
    draw = ImageDraw.Draw(img)

    def px(nx, ny):
        return nx * fw / 1000 - int(cx0), ny * fh / 1000 - int(cy0)

    try:
        font = ImageFont.truetype("arialbd.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    if box:
        (x0, y0), (x1, y1) = px(box[0], box[1]), px(box[2], box[3])
        dashed_rect(draw, (x0, y0, x1, y1), ACCENT)
    for m in marks:
        if m.get("x", -1) < 0 or m.get("y", -1) < 0:
            continue
        cx, cy = px(m["x"], m["y"])
        if m.get("kind") == "click":
            r = 16
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ACCENT, outline=(255, 255, 255), width=3)
            label = str(m.get("label", ""))
            if label:
                tw = draw.textlength(label, font=font)
                draw.text((cx - tw / 2, cy - 11), label, fill=(255, 255, 255), font=font)
        else:
            r = 22
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=CURSOR, width=4)
    img.save(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("steps", type=Path)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--crop", default="0,0,1000,1000",
                    help="shared-screen area x0,y0,x1,y1 normalised 0-1000 (excludes webcam tiles)")
    a = ap.parse_args()
    crop = [float(v) for v in a.crop.split(",")]
    a.outdir.mkdir(parents=True, exist_ok=True)
    steps = json.loads(a.steps.read_text(encoding="utf-8"))
    for s in steps:
        raw = a.outdir / f"{s['key']}_raw.png"
        grab(a.video, to_seconds(s["t"]), raw, a.width)
        annotate(raw, a.outdir / f"{s['key']}.png", s.get("marks", []), s.get("box"), crop)
        print(f"{s['key']} {s['t']} -> {a.outdir / (s['key'] + '.png')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
