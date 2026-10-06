#!/usr/bin/env python3
"""Observer recording sheet (Markdown) from a goms-testing model.yaml.

Usage:
    python scripts/sheet.py MODEL.yaml [--lang en|cs] [--table FILE|K=..] [-o OUT.md]

One table per method: step, predicted cumulative (nominal), observed
timestamp, path deviation, note. Each task ends with: success (yes / with
hint / no), SEQ 1–7, attempt #, method chosen, measured R to subtract.
Discovery / QA-only tasks get the end block only (observe, no prediction).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import klm  # noqa: E402

TEXT = {
    "en": {
        "title": "Observer recording sheet",
        "header": "Participant: ______ · Date: ______ · Session: ______ · "
                  "Moderator: ______ · Observer: ______",
        "setup": "Viewport: {viewport} · Build / URL: ______ · Recording start (00:00) = ______",
        "rules": [
            "Predicted times are KLM hypotheses for an expert, error-free user with system/LLM "
            "time (R) excluded — not targets. Log what happens; never steer toward the modelled path.",
            "Timestamps are mm:ss from the recording start. Path deviation = what the participant "
            "did instead (other method, wrong tab, back-tracking, asked for help).",
            "After the session: (observed − R) − predicted = search / comprehension cost marker.",
        ],
        "routine": "⚙ routine — modelled",
        "discovery": "👁 discovery / comprehension — observe only, no prediction",
        "qa_only": "QA only — not a participant task",
        "skip": "skipped",
        "task_start": "Task start (mm:ss): ______",
        "method": "Method {id} — {name} · predicted {nominal} s nominal, range {lo}–{hi} s",
        "cols": ["#", "Step", "Predicted cum. (s)", "Observed (mm:ss)", "Path deviation", "Note"],
        "end": "Task end (mm:ss): ______",
        "end_cols": ["Success", "SEQ (1–7)", "Attempt #", "Method chosen", "Measured R to subtract (s)"],
        "success": "☐ yes ☐ with hint ☐ no",
        "other": "☐ other: ____",
        "marker": "Search-cost marker: (observed − R) − predicted = ______ s",
        "tags": {"not_executed": " [NOT EXECUTED]", "not_verified": " [NOT VERIFIED]",
                 "documented": " [DOCUMENTED]", "verified": ""},
    },
    "cs": {
        "title": "Záznamový arch pozorovatele",
        "header": "Účastník: ______ · Datum: ______ · Sezení: ______ · "
                  "Moderátor: ______ · Pozorovatel: ______",
        "setup": "Viewport: {viewport} · Build / URL: ______ · Start nahrávání (00:00) = ______",
        "rules": [
            "Predikované časy jsou KLM hypotézy pro zkušeného uživatele bez chyb, bez času "
            "systému/LLM (R) — nejsou to cíle. Zapisujte, co se děje; nenavádějte k modelované cestě.",
            "Časy zapisujte jako mm:ss od startu nahrávání. Odchylka = co účastník udělal místo "
            "toho (jiná metoda, špatná záložka, návrat, prosba o pomoc).",
            "Po sezení: (pozorováno − R) − predikce = ukazatel nákladů na hledání / porozumění.",
        ],
        "routine": "⚙ rutina — modelováno",
        "discovery": "👁 objevování / porozumění — jen pozorovat, bez predikce",
        "qa_only": "jen QA — není úkol pro účastníka",
        "skip": "vynecháno",
        "task_start": "Začátek úkolu (mm:ss): ______",
        "method": "Metoda {id} — {name} · predikce {nominal} s nominálně, rozsah {lo}–{hi} s",
        "cols": ["#", "Krok", "Predikce kum. (s)", "Pozorováno (mm:ss)", "Odchylka cesty", "Poznámka"],
        "end": "Konec úkolu (mm:ss): ______",
        "end_cols": ["Úspěch", "SEQ (1–7)", "Pokus č.", "Zvolená metoda", "Změřené R k odečtení (s)"],
        "success": "☐ ano ☐ s nápovědou ☐ ne",
        "other": "☐ jiná: ____",
        "marker": "Ukazatel nákladů na hledání: (pozorováno − R) − predikce = ______ s",
        "tags": {"not_executed": " [NEPROVEDENO]", "not_verified": " [NEOVĚŘENO]",
                 "documented": " [DLE DOKUMENTACE]", "verified": ""},
    },
}


def cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render(model: dict, result: dict, lang: str = "en") -> str:
    t = TEXT[lang]
    app = model.get("app", "")
    out = [f"# {t['title']}" + (f" — {app}" if app else ""), ""]
    out += [t["header"], "", t["setup"].format(viewport=model.get("viewport") or "______"), ""]
    out += [f"> - {rule}" for rule in t["rules"]] + [""]
    evaluated = {task["id"]: task for task in result["tasks"]}
    for task in model["tasks"]:
        tid = str(task["id"])
        triage = task.get("triage", "routine")
        title = task.get("title", "")
        out += [f"## {tid}" + (f" — {cell(title)}" if title else ""), "", f"_{t[triage]}_", ""]
        out += [t["task_start"], ""]
        methods = evaluated[tid]["methods"]
        for m in methods:
            out += [
                "### " + t["method"].format(
                    id=m["id"], name=cell(m["name"] or m["id"]), nominal=klm.fmt(m["nominal"]),
                    lo=m["range"][0], hi=m["range"][1]),
                "",
                "| " + " | ".join(t["cols"]) + " |",
                "|---:|---|---:|---|---|---|",
            ]
            for st in m["steps"]:
                label = cell(st["label"]) + t["tags"][st["status"]]
                out.append(f"| {st['n']} | {label} | {klm.fmt(st['cum_nominal'])} |  |  |  |")
            out.append("")
        choices = " ".join(f"☐ {m['id']}" for m in methods) + (" " if methods else "") + t["other"]
        out += [
            t["end"], "",
            "| " + " | ".join(t["end_cols"]) + " |",
            "|---|---|---|---|---|",
            f"| {t['success']} | 1 2 3 4 5 6 7 |  | {choices} |  |",
            "",
        ]
        if methods:
            out += [t["marker"], ""]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="model.yaml -> observer recording sheet (Markdown)")
    ap.add_argument("model")
    ap.add_argument("--lang", choices=sorted(TEXT), default="en")
    ap.add_argument("--table", help="operator overrides (same as klm.py --table)")
    ap.add_argument("-o", "--output", help="write to this file instead of stdout")
    args = ap.parse_args(argv)
    try:
        model = klm.load_model(args.model)
        result = klm.evaluate_model(model, klm.load_table(args.table))
    except klm.ModelError as exc:
        print(f"sheet.py: error: {exc}", file=sys.stderr)
        return 2
    md = render(model, result, args.lang) + "\n"
    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
    else:
        sys.stdout.buffer.write(md.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
