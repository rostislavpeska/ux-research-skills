#!/usr/bin/env python3
"""KLM calculator for goms-testing model.yaml files.

Usage:
    python scripts/klm.py MODEL.yaml [--md | --json] [--table FILE|K=0.2,P=1.1]
                                     [--free-text-min 20]

Tokens (whitespace-separated, uppercase):
    M      mental act of routine thinking / decision        1.35 s
    P      point with the mouse                             1.10 s
    B      mouse button press OR release (click = BB)       0.10 s
    BB…    run of B (BB = click, BBBB = double, BBBBBB = triple)
    H      home hands mouse <-> keyboard                    0.40 s
    K      one keystroke (a Ctrl modifier is 1 K)           0.28 s
    nK     n keystrokes, e.g. 11K
    S      scroll — NOT a standard KLM operator; ASSUMPTION
           nominal 1.0 s, low 0.5 s, high 2.0 s
    R      system / LLM response — accepted, ALWAYS excluded (0 s)

Per method:
    nominal = ops_low with S nominal
    low     = ops_low with S low
    high    = ops_low + ops_extra with S high
    reported range = floor(low x 0.8) – ceil(high x 1.2)
    nominal without free text = nominal minus every K in a run of >= 20 K

GOMS output is a hypothesis about an expert, error-free user — never a
finding about users. Rankings and method ratios matter more than seconds.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    sys.exit("klm.py: error: PyYAML is required (pip install pyyaml)")

DEFAULT_TABLE: dict = {
    "K": 0.28,
    "P": 1.10,
    "B": 0.10,
    "H": 0.40,
    "M": 1.35,
    "S": {"low": 0.5, "nominal": 1.0, "high": 2.0},
    "R": 0.0,
}
OPERATORS = ("M", "P", "B", "H", "K", "S", "R")
STATUSES = ("verified", "not_executed", "not_verified", "documented")
TRIAGE = ("routine", "discovery", "qa_only", "skip")
FREE_TEXT_MIN = 20
ALLOWED_HELP = "M P B BB… H K nK S R"

DISCLAIMER = (
    "GOMS/KLM predictions describe an expert, error-free user and exclude "
    "system/LLM time (R). They are hypotheses to test, never findings about "
    "users. Rankings and method ratios matter more than absolute seconds."
)
S_NOTE = (
    "S (scroll) is not a standard KLM operator: nominal {nominal} s, "
    "low {low} s, high {high} s — an explicit assumption."
)

_TOKEN_RE = re.compile(r"^(?:(?P<single>[MPHSR])|(?P<n>\d*)K|(?P<b>B+))$")


class ModelError(ValueError):
    """Invalid model file or operator table."""


class TokenError(ModelError):
    """An ops string contains a token outside the KLM vocabulary."""


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
def parse_ops(ops, where: str = "ops") -> list[tuple[str, int]]:
    """Parse an ops string into [(operator, count)] preserving order.

    Raises TokenError on anything outside the vocabulary.
    """
    if ops is None:
        return []
    if not isinstance(ops, str):
        raise TokenError(f"{where}: ops must be a string, got {type(ops).__name__}")
    out: list[tuple[str, int]] = []
    for tok in ops.split():
        m = _TOKEN_RE.match(tok)
        if not m:
            raise TokenError(
                f"{where}: unknown token {tok!r} in {ops!r} — allowed tokens: "
                f"{ALLOWED_HELP} (whitespace-separated, uppercase)"
            )
        if m.group("single"):
            out.append((m.group("single"), 1))
        elif m.group("b"):
            out.append(("B", len(m.group("b"))))
        else:
            n = int(m.group("n")) if m.group("n") else 1
            if n < 1:
                raise TokenError(f"{where}: {tok!r} — a keystroke count must be >= 1")
            out.append(("K", n))
    return out


def load_table(spec: str | None) -> dict:
    """Operator table: defaults, overridden by a YAML/JSON file or K=..,P=.. string."""
    table = json.loads(json.dumps(DEFAULT_TABLE))  # deep copy
    if not spec:
        return table
    path = Path(spec)
    if path.is_file():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ModelError(f"--table {spec}: expected a mapping of operator: seconds")
    else:
        data = {}
        for part in spec.split(","):
            if "=" not in part:
                raise ModelError(f"--table: cannot parse {part!r} (expected OP=seconds)")
            key, val = part.split("=", 1)
            data[key.strip()] = val.strip()
    for key, val in data.items():
        op, _, variant = str(key).partition("_")  # S_low / S_high / S_nominal
        op = op.upper()
        if op not in OPERATORS:
            raise ModelError(f"--table: unknown operator {key!r} (allowed {', '.join(OPERATORS)})")
        if op == "R":
            raise ModelError("--table: R is always excluded and cannot be given a time")
        if op == "S":
            if isinstance(val, dict):
                for v_key, v_val in val.items():
                    if v_key not in ("low", "nominal", "high"):
                        raise ModelError(f"--table: S accepts low/nominal/high, got {v_key!r}")
                    table["S"][v_key] = float(v_val)
            elif variant:
                if variant not in ("low", "nominal", "high"):
                    raise ModelError(f"--table: S accepts low/nominal/high, got {variant!r}")
                table["S"][variant] = float(val)
            else:
                table["S"]["nominal"] = float(val)
        else:
            if variant:
                raise ModelError(f"--table: only S has variants, got {key!r}")
            table[op] = float(val)
    return table


def load_model(path) -> dict:
    path = Path(path)
    try:
        model = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ModelError(f"{path}: file not found") from None
    except yaml.YAMLError as exc:
        raise ModelError(f"{path}: invalid YAML — {exc}") from None
    validate_model(model, str(path))
    return model


def validate_model(model, name: str = "model") -> None:
    if not isinstance(model, dict) or not isinstance(model.get("tasks"), list) or not model["tasks"]:
        raise ModelError(f"{name}: expected a mapping with a non-empty 'tasks' list")
    for ti, task in enumerate(model["tasks"]):
        tw = f"tasks[{ti}]"
        if not isinstance(task, dict) or not task.get("id"):
            raise ModelError(f"{name}: {tw} needs an 'id'")
        tw = f"task {task['id']}"
        triage = task.get("triage", "routine")
        if triage not in TRIAGE:
            raise ModelError(f"{name}: {tw}: triage {triage!r} not in {TRIAGE}")
        methods = task.get("methods") or []
        if triage == "routine" and not methods:
            raise ModelError(f"{name}: {tw}: a routine task needs at least one method")
        ids = [str(m.get("id")) for m in methods if isinstance(m, dict)]
        if len(ids) != len(set(ids)):
            raise ModelError(f"{name}: {tw}: duplicate method ids {ids}")
        for mi, method in enumerate(methods):
            mw = f"{tw} method[{mi}]"
            if not isinstance(method, dict) or not method.get("id"):
                raise ModelError(f"{name}: {mw} needs an 'id'")
            mw = f"{tw} method {method['id']}"
            steps = method.get("steps")
            if not isinstance(steps, list) or not steps:
                raise ModelError(f"{name}: {mw}: needs a non-empty 'steps' list")
            for si, step in enumerate(steps, 1):
                sw = f"{mw} step {si}"
                if not isinstance(step, dict) or not step.get("label"):
                    raise ModelError(f"{name}: {sw}: needs a 'label'")
                status = step.get("status")
                if status not in STATUSES:
                    raise ModelError(
                        f"{name}: {sw} ({step['label']!r}): status {status!r} not in {STATUSES}"
                    )
                parse_ops(step.get("ops_low"), f"{name}: {sw} ops_low")
                parse_ops(step.get("ops_extra"), f"{name}: {sw} ops_extra")
                chunks = step.get("chunks") or []
                if not isinstance(chunks, list):
                    raise ModelError(f"{name}: {sw}: chunks must be a list")


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------
def op_seconds(op: str, count: int, table: dict, variant: str) -> float:
    if op == "R":
        return 0.0
    if op == "S":
        return table["S"][variant] * count
    return table[op] * count


def ops_seconds(ops: list[tuple[str, int]], table: dict, variant: str) -> float:
    return sum(op_seconds(op, n, table, variant) for op, n in ops)


def count_ops(ops: list[tuple[str, int]]) -> dict:
    counts = {op: 0 for op in OPERATORS}
    for op, n in ops:
        counts[op] += n
    return counts


def evaluate_method(method: dict, table: dict, free_text_min: int = FREE_TEXT_MIN) -> dict:
    steps_out = []
    all_low: list[tuple[str, int]] = []
    all_extra: list[tuple[str, int]] = []
    cum_nominal = cum_high = 0.0
    for idx, step in enumerate(method["steps"], 1):
        low = parse_ops(step.get("ops_low"))
        extra = parse_ops(step.get("ops_extra"))
        all_low += low
        all_extra += extra
        t_nom = ops_seconds(low, table, "nominal")
        t_high = ops_seconds(low + extra, table, "high")
        cum_nominal += t_nom
        cum_high += t_high
        steps_out.append({
            "n": idx,
            "label": step["label"],
            "status": step["status"],
            "ops_low": " ".join((step.get("ops_low") or "").split()),
            "ops_extra": " ".join((step.get("ops_extra") or "").split()),
            "t_nominal": t_nom,
            "cum_nominal": cum_nominal,
            "t_high": t_high,
            "cum_high": cum_high,
            "chunks": list(step.get("chunks") or []),
        })
    nominal = ops_seconds(all_low, table, "nominal")
    low_t = ops_seconds(all_low, table, "low")
    high_t = ops_seconds(all_low + all_extra, table, "high")
    free_k = sum(n for op, n in all_low if op == "K" and n >= free_text_min)
    no_free = nominal - free_k * table["K"]
    warnings = []
    declared = method.get("free_text_chars")
    if declared is not None and int(declared) != free_k:
        warnings.append(
            f"method {method['id']}: free_text_chars={declared} but ops contain "
            f"{free_k} K in runs of >= {free_text_min}"
        )
    return {
        "id": str(method["id"]),
        "name": method.get("name", ""),
        "selection_rule": method.get("selection_rule", ""),
        "free_text_chars": free_k,
        "nominal": nominal,
        "low": low_t,
        "high": high_t,
        "range": [math.floor(round(low_t * 0.8, 6)), math.ceil(round(high_t * 1.2, 6))],
        "nominal_no_free_text": no_free,
        "counts_low": count_ops(all_low),
        "counts_high": count_ops(all_low + all_extra),
        "r_excluded": count_ops(all_low + all_extra)["R"],
        "statuses": {s: sum(1 for st in steps_out if st["status"] == s) for s in STATUSES},
        "steps": steps_out,
        "warnings": warnings,
    }


def method_ratios(methods: list[dict]) -> list[dict]:
    """Every pair within a task, slower / faster by nominal."""
    out = []
    for a, b in itertools.combinations(methods, 2):
        slow, fast = (a, b) if a["nominal"] >= b["nominal"] else (b, a)
        ratio = slow["nominal"] / fast["nominal"] if fast["nominal"] else float("inf")
        nf = (
            slow["nominal_no_free_text"] / fast["nominal_no_free_text"]
            if fast["nominal_no_free_text"] else float("inf")
        )
        out.append({
            "slower": slow["id"],
            "faster": fast["id"],
            "label": f"{slow['id']} / {fast['id']}",
            "ratio": ratio,
            "ratio_no_free_text": nf,
        })
    return out


def evaluate_model(model: dict, table: dict | None = None,
                   free_text_min: int = FREE_TEXT_MIN) -> dict:
    table = table or load_table(None)
    tasks = []
    for task in model["tasks"]:
        methods = [evaluate_method(m, table, free_text_min) for m in task.get("methods") or []]
        tasks.append({
            "id": str(task["id"]),
            "title": task.get("title", ""),
            "triage": task.get("triage", "routine"),
            "methods": methods,
            "ratios": method_ratios(methods),
        })
    ranked = sorted(
        ((t["id"], m["id"], m["nominal"]) for t in tasks for m in t["methods"]),
        key=lambda r: -r[2],
    )
    return {
        "app": model.get("app", ""),
        "table": table,
        "free_text_min": free_text_min,
        "disclaimer": DISCLAIMER,
        "assumptions": [S_NOTE.format(**table["S"]), "R (system/LLM time) is always excluded."],
        "tasks": tasks,
        "ranking": [{"task": t, "method": m, "nominal": n} for t, m, n in ranked],
        "warnings": [w for t in tasks for m in t["methods"] for w in m["warnings"]],
    }


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
def fmt(x: float, places: str = "0.1") -> str:
    """Round half-up for display (15.45 -> 15.5, never banker's rounding)."""
    return str(Decimal(repr(round(x, 6))).quantize(Decimal(places), rounding=ROUND_HALF_UP))


def table_line(table: dict) -> str:
    s = table["S"]
    return (
        f"K {table['K']:.2f} s · P {table['P']:.2f} s · B {table['B']:.2f} s (click = BB) · "
        f"H {table['H']:.2f} s · M {table['M']:.2f} s · S {s['nominal']} s "
        f"(low {s['low']} / high {s['high']}; ASSUMPTION) · R excluded"
    )


def render_md(result: dict) -> str:
    lines = []
    title = f"KLM results — {result['app']}" if result["app"] else "KLM results"
    lines += [f"## {title}", "", f"> {result['disclaimer']}", ""]
    lines += [f"Operator table: {table_line(result['table'])}.", ""]
    lines += [f"Assumption: {result['assumptions'][0]}", ""]
    lines += [
        f"Free text = runs of ≥ {result['free_text_min']} K. Reported range = "
        "floor(low × 0.8) – ceil(high × 1.2).",
        "",
    ]
    rank = {(r["task"], r["method"]): i for i, r in enumerate(result["ranking"], 1)}
    lines += [
        "| Rank | Task | Method | Nominal (s) | Low (s) | High (s) | Reported range | "
        "Nominal w/o free text (s) | M | P | B | H | K | S | R excl. |",
        "|---:|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for task in result["tasks"]:
        for m in task["methods"]:
            c = m["counts_low"]
            name = f"{m['id']} — {m['name']}" if m["name"] else m["id"]
            lines.append(
                f"| {rank[(task['id'], m['id'])]} | {task['id']} | {name} | {fmt(m['nominal'])} | "
                f"{fmt(m['low'])} | {fmt(m['high'])} | {m['range'][0]}–{m['range'][1]} s | "
                f"{fmt(m['nominal_no_free_text'])} | {c['M']} | {c['P']} | {c['B']} | "
                f"{c['H']} | {c['K']} | {c['S']} | {m['r_excluded']} |"
            )
    lines.append("")
    ratios = [(t, r) for t in result["tasks"] for r in t["ratios"]]
    lines += ["### Method ratios (within task, slower / faster)", ""]
    if ratios:
        lines += ["| Task | Ratio | Nominal | Without free text |", "|---|---|---:|---:|"]
        for task, r in ratios:
            lines.append(
                f"| {task['id']} | {r['label']} | {fmt(r['ratio'], '0.01')} | "
                f"{fmt(r['ratio_no_free_text'], '0.01')} |"
            )
    else:
        lines.append("No task has two or more methods.")
    lines.append("")
    skipped = [t for t in result["tasks"] if not t["methods"]]
    if skipped:
        lines += ["### Not modelled (test only)", ""]
        lines += [f"- {t['id']} {t['title']} — triage: {t['triage']}" for t in skipped]
        lines.append("")
    lines += ["### Cumulative time per step (nominal; high adds ops_extra and S high)", ""]
    for task in result["tasks"]:
        for m in task["methods"]:
            head = f"#### {task['id']} · {m['id']}"
            if task["title"]:
                head += f" — {task['title']}"
            lines += [head, ""]
            if m["selection_rule"]:
                lines += [f"Selection rule: {m['selection_rule']}", ""]
            lines += [
                "| # | Step | Status | ops (low) | ops (extra, high only) | t (s) | cum (s) | cum high (s) |",
                "|---:|---|---|---|---|---:|---:|---:|",
            ]
            for st in m["steps"]:
                lines.append(
                    f"| {st['n']} | {st['label']} | {st['status']} | {st['ops_low'] or '—'} | "
                    f"{st['ops_extra'] or '—'} | {fmt(st['t_nominal'], '0.01')} | "
                    f"{fmt(st['cum_nominal'], '0.01')} | {fmt(st['cum_high'], '0.01')} |"
                )
            lines.append("")
    if result["warnings"]:
        lines += ["### Warnings", ""] + [f"- {w}" for w in result["warnings"]] + [""]
    return "\n".join(lines)


def to_json(result: dict) -> str:
    def rnd(obj):
        if isinstance(obj, float):
            return round(obj, 3) if math.isfinite(obj) else None
        if isinstance(obj, dict):
            return {k: rnd(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [rnd(v) for v in obj]
        return obj
    return json.dumps(rnd(result), ensure_ascii=False, indent=2)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="KLM calculator for goms-testing model.yaml")
    ap.add_argument("model", help="path to model.yaml")
    fmt_group = ap.add_mutually_exclusive_group()
    fmt_group.add_argument("--md", action="store_true", help="markdown tables (default)")
    fmt_group.add_argument("--json", action="store_true", help="JSON")
    ap.add_argument("--table", help="operator overrides: YAML/JSON file or 'K=0.2,P=1.1,S_high=3'")
    ap.add_argument("--free-text-min", type=int, default=FREE_TEXT_MIN,
                    help="K-run length counted as free text (default 20)")
    args = ap.parse_args(argv)
    try:
        table = load_table(args.table)
        result = evaluate_model(load_model(args.model), table, args.free_text_min)
    except ModelError as exc:
        print(f"klm.py: error: {exc}", file=sys.stderr)
        return 2
    for w in result["warnings"]:
        print(f"klm.py: warning: {w}", file=sys.stderr)
    out = to_json(result) if args.json else render_md(result)
    sys.stdout.buffer.write((out + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
