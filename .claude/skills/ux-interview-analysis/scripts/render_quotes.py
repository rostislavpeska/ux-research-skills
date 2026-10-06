#!/usr/bin/env python3
"""Fill {{q:MM:SS}} placeholders in an analysis draft with verbatim transcript quotes.

Pure: draft + transcript rows (segments.py --rows-out) in, text out. The analyst (Claude) writes
the reasoning and cites moments by timestamp; the quote text is never re-typed by hand.

Usage:
    python scripts/render_quotes.py draft.txt out/rows.json --lang cs -o summary.txt

{{q:12:31}} -> „<segment text>“ [12:31]   (segment whose start rounds to 12:31)
{{q:39:13@participant}} -> pick the speaker when several segments start in the same second.
An unknown or ambiguous timestamp is an error, never a guess.

--translation text_en: board in another language than the session. Each quote stays verbatim and
gets the row's translation on the next line ("    EN: “…”"). The analyst writes text_en into the
rows (never into the draft); a quoted row without it is an error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def mmss(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", type=Path)
    ap.add_argument("rows", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--lang", required=True, help="documentation language: quote marks from locales/<lang>.yaml")
    ap.add_argument("--translation", metavar="FIELD", help="row field with the translation, e.g. text_en")
    a = ap.parse_args()

    import yaml  # lazy
    locale_file = Path(__file__).resolve().parent.parent / "locales" / f"{a.lang}.yaml"
    if not locale_file.exists():
        sys.exit(f"no locale {locale_file} - add one (see locales/README.md)")
    open_q, close_q = yaml.safe_load(locale_file.read_text(encoding="utf-8"))["quotes"]

    rows = json.loads(a.rows.read_text(encoding="utf-8"))["rows"]
    by_start: dict[str, list[dict]] = {}
    for r in rows:
        by_start.setdefault(mmss(r["t_start_s"]), []).append(r)

    missing, ambiguous, untranslated, filled = [], [], [], []

    def fill(m: re.Match) -> str:
        key, role = m.group(1), m.group(2)
        hits = [r for r in by_start.get(key, []) if not role or r["speaker"] == role]
        if not hits:
            missing.append(m.group(0))
            return m.group(0)
        if len(hits) > 1:  # never guess which segment was meant
            ambiguous.append(f"{key} ({', '.join(h['speaker'] for h in hits)})")
            return m.group(0)
        quote = f"{open_q}{hits[0]['text_cs']}{close_q} [{key}]"
        if a.translation:
            tr = hits[0].get(a.translation)
            if not tr:
                untranslated.append(key)
                return m.group(0)
            label = a.translation.removeprefix("text_").upper()
            quote += f"\n    {label}: {open_q}{tr}{close_q}"
        filled.append(key)
        return quote

    text = re.sub(r"\{\{q:(\d{2}:\d{2})(?:@(\w+))?\}\}", fill, a.draft.read_text(encoding="utf-8"))
    if missing or ambiguous or untranslated:
        sys.exit("unresolved quotes — missing: " + ", ".join(missing) +
                 " | ambiguous, add @speaker: " + ", ".join(ambiguous) +
                 f" | no {a.translation}: " + ", ".join(untranslated))
    a.out.write_text(text, encoding="utf-8")
    print(f"filled {len(filled)} quotes", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
