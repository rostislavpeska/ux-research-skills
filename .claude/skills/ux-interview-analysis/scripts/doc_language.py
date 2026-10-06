#!/usr/bin/env python3
"""Decide the documentation language of a study.

Pure: reads the ux_interviews export (JSON from the "UX Harness: Rows" read), prints one line.

Usage:
    python scripts/doc_language.py interviews.json --study S1 [--override en]

Rule:
- --override (an explicit request, e.g. "report in English")  -> that language
- every interview of the study in one language                 -> that language
- several languages                                            -> ASK (exit 2): ask the user
- an interview without a language yet                          -> UNKNOWN (exit 3): transcribe first
The chosen language must have locales/<code>.yaml (exit 4 otherwise).
Quotes are never translated, whatever the documentation language is.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LOCALES = Path(__file__).resolve().parent.parent / "locales"


def need_locale(code: str) -> str:
    if not (LOCALES / f"{code}.yaml").exists():
        print(f"NO_LOCALE {code}: add locales/{code}.yaml (see locales/README.md)")
        raise SystemExit(4)
    return code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("interviews", type=Path)
    ap.add_argument("--study", required=True)
    ap.add_argument("--override", help="explicitly requested documentation language")
    a = ap.parse_args()

    if a.override:
        print(need_locale(a.override))
        return 0

    rows = [r for r in json.loads(a.interviews.read_text(encoding="utf-8")).get("rows", [])
            if r.get("study_id") == a.study]
    if not rows:
        sys.exit(f"no interviews for study {a.study}")
    unknown = [r["interview_id"] for r in rows if not r.get("language")]
    if unknown:
        print("UNKNOWN " + ", ".join(unknown) + ": language not set yet (transcribe first)")
        return 3
    by_lang: dict[str, list[str]] = {}
    for r in rows:
        by_lang.setdefault(r["language"], []).append(r["interview_id"])
    if len(by_lang) > 1:
        detail = "; ".join(f"{lang}: {', '.join(ids)}" for lang, ids in sorted(by_lang.items()))
        print(f"ASK interviews in several languages ({detail}) - ask which documentation language to use")
        return 2
    print(need_locale(next(iter(by_lang))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
