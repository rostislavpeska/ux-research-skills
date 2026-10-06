#!/usr/bin/env python3
"""Check that every second a client surface is on screen belongs to a reported session block.

Pure and local: reads the exported timeline runs (ux_runs rows, stage "timeline") and the session
map written by the analyst; prints a report; exit 0 = fully covered, 1 = uncovered client time.

Usage:
    python scripts/coverage.py out/timeline_runs_<ID>.json out/session_map_<ID>.json \
        [--client client_web,client_app,client_docs] [--tolerance 0]

session_map.json:
{
  "interview_id": "S1-U01",
  "corrections": [{"t_start": "24:01", "t_end": "24:03", "surface": "file_storage",
                   "reason": "frame 24:02 shows Drive"}],
  "blocks": [{"id": "4", "name": "Web", "type": "first_impression",
              "start": "13:36", "end": "17:22", "section": "Web"}]
}
- Blocks are half-open [start, end). A block with an empty "section" is not reported on the
  board (e.g. intro, screen-share setup) and does not cover client time.
- Corrections override the timeline for seconds verified against frames (the reason is printed).
- --tolerance: allowed uncovered seconds per gap (timeline boundaries are ±1–2 s).
"""
from __future__ import annotations

import argparse
import json
import sys


def sec(ts: str) -> int:
    total = 0
    for p in str(ts).split(":"):
        total = total * 60 + int(float(p))
    return total


def mmss(s: int) -> str:
    return f"{s // 60:02d}:{s % 60:02d}"


def window_of(row: dict) -> tuple[int, int]:
    vm = json.loads(row["params_json"])["contents"][0]["parts"][0]["videoMetadata"]
    return int(float(vm["startOffset"].rstrip("s"))), int(float(vm["endOffset"].rstrip("s")))


def surfaces_per_second(rows: list[dict]) -> dict[int, tuple[str, str]]:
    """second -> (surface, view); newest run wins per window, later intervals win on overlap."""
    newest: dict[tuple[int, int], dict] = {}
    for r in rows:
        if r.get("status") != "ok":
            continue
        w = window_of(r)
        if w not in newest or r.get("Id", 0) > newest[w].get("Id", 0):
            newest[w] = r
    out: dict[int, tuple[str, str]] = {}
    for w in sorted(newest):
        for iv in json.loads(newest[w]["output_json"])["intervals"]:
            for s in range(sec(iv["t_start"]), sec(iv["t_end"])):
                out[s] = (iv["surface"], iv.get("view", ""))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs")
    ap.add_argument("session_map")
    ap.add_argument("--client", default="client_web,client_app,client_docs")
    ap.add_argument("--tolerance", type=int, default=0)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    rows = json.load(open(a.runs, encoding="utf-8"))["rows"]
    smap = json.load(open(a.session_map, encoding="utf-8"))
    client = set(a.client.split(","))

    per_s = surfaces_per_second(rows)
    for c in smap.get("corrections", []):
        for s in range(sec(c["t_start"]), sec(c["t_end"])):
            per_s[s] = (c["surface"], "corrected")
        print(f"correction {c['t_start']}–{c['t_end']} → {c['surface']}: {c['reason']}")

    blocks = smap["blocks"]
    owner: dict[int, dict] = {}
    problems = []
    for b in blocks:
        for s in range(sec(b["start"]), sec(b["end"])):
            if s in owner:
                problems.append(f"overlap at {mmss(s)}: {owner[s]['id']} and {b['id']}")
                break
            owner[s] = b

    client_s = sorted(s for s, (surf, _) in per_s.items() if surf in client)
    uncovered = [s for s in client_s if s not in owner or not owner[s].get("section")]

    gaps, start = [], None
    for i, s in enumerate(uncovered):
        if start is None:
            start = s
        if i + 1 == len(uncovered) or uncovered[i + 1] != s + 1:
            gaps.append((start, s + 1))
            start = None
    hard = [(g0, g1) for g0, g1 in gaps if g1 - g0 > a.tolerance]

    print(f"\n{smap['interview_id']} — client surfaces on screen: {len(client_s)} s")
    print(f"{'block':<34}{'time':<14}{'client s':>9}  section")
    for b in blocks:
        n = sum(1 for s in client_s if owner.get(s) is b)
        print(f"{b['id'] + ' ' + b['name']:<34}{b['start'] + '–' + b['end']:<14}{n:>9}  {b.get('section') or '—'}")
    covered = len(client_s) - len(uncovered)
    print(f"\ncovered: {covered} of {len(client_s)} s")
    for g0, g1 in gaps:
        surf = per_s[g0][0]
        print(f"UNCOVERED {mmss(g0)}–{mmss(g1)} ({g1 - g0} s, {surf})")
    for p in problems:
        print("MAP ERROR", p)
    return 1 if hard or problems else 0


if __name__ == "__main__":
    sys.exit(main())
