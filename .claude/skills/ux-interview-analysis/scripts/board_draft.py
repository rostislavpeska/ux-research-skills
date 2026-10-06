#!/usr/bin/env python3
"""Parse a rendered board draft (quotes already filled by render_quotes.py) into board JSON.

Pure and local. Draft format — blocks start with "=== ":
    === COLUMN <id> | <section name>      then "title: …" and "context: …" lines
    === CARD <grey|red|blue|green|amber> | <heading>   then body lines
    === NOTE                               then body lines (small grey text)
    === STEP <key> | <OK|Borderline|Problem|Info>  (Czech labels Hraniční/Problém also accepted)        then "title: …" and body lines
Output: [{"id", "name", "title", "context", "cards": [{color, heading, body}], "note",
          "steps": [{key, status, title, body}]}]

Usage: python scripts/board_draft.py out/board_<ID>.txt -o out/board_<ID>.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys

COLORS = {"grey", "red", "blue", "green", "amber"}
STATUSES = {"OK", "Info", "Hraniční", "Problém", "Borderline", "Problem"}  # cs + en labels


def parse(text: str) -> list[dict]:
    cols: list[dict] = []
    cur: dict | None = None
    lines: list[str] = []

    def flush() -> None:
        if cur is None:
            return
        body = "\n".join(lines).strip("\n")
        kind = cur["_kind"]
        if kind == "COLUMN":
            for ln in body.splitlines():
                k, _, v = ln.partition(": ")
                if k in ("title", "context"):
                    cur["col"][k] = v
        elif kind == "CARD":
            cur["col"]["cards"].append({"color": cur["color"], "heading": cur["heading"], "body": body})
        elif kind == "NOTE":
            cur["col"]["note"] = body
        elif kind == "STEP":
            first, _, rest = body.partition("\n")
            if not first.startswith("title: "):
                raise SystemExit(f"step {cur['key']}: first line must be 'title: …'")
            cur["col"]["steps"].append({"key": cur["key"], "status": cur["status"],
                                        "title": first[len("title: "):], "body": rest.strip("\n")})

    for ln in text.splitlines():
        m = re.match(r"^=== (COLUMN|CARD|NOTE|STEP)\s*(.*)$", ln)
        if not m:
            lines.append(ln)
            continue
        flush()
        lines = []
        kind, rest = m.group(1), m.group(2)
        a, _, b = (s.strip() for s in rest.partition("|"))
        if kind == "COLUMN":
            col = {"id": a, "name": b, "title": "", "context": "", "cards": [], "note": "", "steps": []}
            cols.append(col)
            cur = {"_kind": kind, "col": col}
        else:
            if not cols:
                raise SystemExit(f"{kind} before any COLUMN")
            cur = {"_kind": kind, "col": cols[-1]}
            if kind == "CARD":
                if a not in COLORS:
                    raise SystemExit(f"unknown card colour {a!r}")
                cur.update(color=a, heading=b)
            elif kind == "STEP":
                if b not in STATUSES:
                    raise SystemExit(f"step {a}: unknown status {b!r}")
                cur.update(key=a, status=b)
    flush()
    left = [c["name"] for c in cols if not c["title"]]
    if left:
        raise SystemExit(f"columns without title: {left}")
    if "{{" in json.dumps(cols, ensure_ascii=False):
        raise SystemExit("unfilled placeholder left — run render_quotes.py first")
    return cols


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    cols = parse(open(a.draft, encoding="utf-8").read())
    json.dump(cols, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.stdout.reconfigure(encoding="utf-8")
    for c in cols:
        print(f"{c['id']:<10} {len(c['cards'])} cards · {len(c['steps'])} steps · {c['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
