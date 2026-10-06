#!/usr/bin/env python3
"""Print observe runs compactly (pure, read-only).

Usage: python scripts/obs_print.py out/obs_runs.json <job_id> [<job_id> ...]
obs_runs.json = ux_runs rows exported through the Rows webhook (stage "observe"); job_id = the
n8n execution id returned when the observation was fired (the last part of run_id).
"""
from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs")
    ap.add_argument("job_ids", nargs="+")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    rows = json.load(open(a.runs, encoding="utf-8"))["rows"]
    by_job = {r["run_id"].split("-")[-1]: r for r in rows}
    for jid in a.job_ids:
        if jid not in by_job:
            print("MISSING run for job", jid)
            continue
        o = json.loads(by_job[jid]["output_json"])
        print("=====", jid)
        for i, s in enumerate(o["steps"]):
            print(f"{i+1:02d} {s['t']}-{s.get('t_end', '')} [{s['screen']}] {s['action']} «{s['target']}» "
                  f"@({s['cursor_x']},{s['cursor_y']}) -> {s['system_response']} | {s['difficulty_signal']} | {s['confidence']}")
        if o.get("notes"):
            print("NOTES", o["notes"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
