#!/usr/bin/env python3
"""Board JSON column → JavaScript for the FigJam renderer (`use_figma` through the Figma MCP).

Pure and local: fills renderers/figjam/build_column.js with one column of the board JSON and its
x position. The agent passes the printed code to `use_figma`; the call returns slot ids and FNV-1a
hashes for `board_hashcheck.py`.

Usage:
    python scripts/figjam_code.py out/board_<ID>.json --column web --index 2 > out/col_web.js
    (x = index × stride; default stride 1848 = 1648 px column + 200 px gap)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "renderers" / "figjam" / "build_column.js"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--column", required=True, help="column id from the board draft (=== COLUMN <id> | …)")
    ap.add_argument("--index", type=int, required=True, help="column position, left to right, from 0")
    ap.add_argument("--stride", type=int, default=1848)
    ap.add_argument("--template", default=str(TEMPLATE))
    a = ap.parse_args()
    cols = {c["id"]: c for c in json.load(open(a.board, encoding="utf-8"))}
    if a.column not in cols:
        raise SystemExit(f"no column {a.column!r}; have {sorted(cols)}")
    code = Path(a.template).read_text(encoding="utf-8")
    slots = {"const SPEC = __SPEC__;": f"const SPEC = {json.dumps(cols[a.column], ensure_ascii=False)};",
             "const X = __X__;": f"const X = {a.index * a.stride};"}
    for token, value in slots.items():
        if code.count(token) != 1:
            raise SystemExit(f"template must contain {token!r} exactly once")
        code = code.replace(token, value)
    if len(code) > 50000:
        raise SystemExit(f"code is {len(code)} chars; use_figma accepts 50 000 — split the column")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
