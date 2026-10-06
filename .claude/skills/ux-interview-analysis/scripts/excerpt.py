#!/usr/bin/env python3
"""Transcript excerpt for a time window, as prompt context (pure: rows in, text out).

Usage:
    python scripts/excerpt.py out/rows.json --start 1400 --end 1730 -o out/excerpt.txt

Lines: "[MM:SS] speaker: text" for every segment overlapping [start, end] seconds.
Speaker keys stay as stored (moderator / participant / observer / unclear).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def mmss(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rows", type=Path)
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()
    rows = json.loads(a.rows.read_text(encoding="utf-8"))["rows"]
    lines = [f"[{mmss(r['t_start_s'])}] {r['speaker']}: {r['text_cs']}"
             for r in rows if r["t_end_s"] >= a.start and r["t_start_s"] <= a.end]
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines)} segments", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
