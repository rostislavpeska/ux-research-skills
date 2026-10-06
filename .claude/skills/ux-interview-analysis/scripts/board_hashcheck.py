#!/usr/bin/env python3
"""Compare text hashes returned by the Figma build with the board JSON (pure, local).

FNV-1a 32-bit over Unicode code points — the same function the Figma build script runs:
    h = 0x811c9dc5; for each code point: h ^= cp; h = (h * 0x01000193) mod 2^32

Usage: python scripts/board_hashcheck.py out/board_<ID>.json out/board_<ID>_hashes.json
board_<ID>_hashes.json = merged {"<column>/<key>": hash} maps returned by the build calls.
Exit 0 only when every expected text is present on the board with an identical hash.
"""
from __future__ import annotations

import argparse
import json
import sys


def fnv(s: str) -> int:
    h = 0x811C9DC5
    for ch in s:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def expected(cols: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in cols:
        p = c["id"] + "/"
        out[p + "title"] = fnv(c["title"])
        out[p + "context"] = fnv(c["context"])
        for i, card in enumerate(c["cards"]):
            out[f"{p}card{i}/heading"] = fnv(card["heading"])
            out[f"{p}card{i}/body"] = fnv(card["body"])
        if c.get("note"):
            out[p + "note"] = fnv(c["note"])
        for s in c["steps"]:
            for k in ("status", "title", "body"):
                out[f"{p}step:{s['key']}/{k}"] = fnv(s[k])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Board JSON vs FNV-1a hashes returned by the renderer.")
    ap.add_argument("board", help="out/board_<ID>.json")
    ap.add_argument("hashes", help="merged {column/key: hash} returned by the render calls")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    cols = json.load(open(a.board, encoding="utf-8"))
    actual = json.load(open(a.hashes, encoding="utf-8"))
    exp = expected(cols)
    built = {k.split("/")[0] for k in actual}
    bad = 0
    for k, v in exp.items():
        if k.split("/")[0] not in built:
            continue
        if k not in actual:
            print("MISSING", k); bad += 1
        elif actual[k] != v:
            print("MISMATCH", k); bad += 1
    extra = [k for k in actual if k not in exp]
    for k in extra:
        print("UNEXPECTED", k); bad += 1
    n = sum(1 for k in exp if k.split("/")[0] in built)
    print(f"columns built: {sorted(built)} · texts checked: {n} · problems: {bad}")
    pending = sorted({c['id'] for c in cols} - built)
    if pending:
        print("not built yet:", pending)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
