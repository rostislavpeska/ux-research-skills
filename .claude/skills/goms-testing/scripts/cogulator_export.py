#!/usr/bin/env python3
"""Export a goms-testing model.yaml to Cogulator (CMN-GOMS) text.

Usage:
    python scripts/cogulator_export.py MODEL.yaml [--variant low|high]
        [--out-dir DIR] [--table FILE|K=..] [--scroll-operator Point]

Prints Markdown: one fenced code block per method plus, for every task
with two or more methods, a selection-rule block (CreateState / If /
EndIf). Cogulator has no documented comment syntax, so every note is
written OUTSIDE the code blocks. --out-dir also writes each block to
<task>_<method>.txt / <task>_selection.txt for pasting into Cogulator.

Every operator line carries an explicit time modifier so Cogulator uses
OUR table (its defaults differ, e.g. Point 950 ms):
    M -> Think (1350 ms)     P -> Point to (1100 ms)   BB -> Click (200 ms)
    B -> Click press/release (100 ms)                   H -> Hands to (400 ms)
    K -> Keystroke (280 ms)  nK -> Type (n x 280 ms)
    S -> <scroll-operator> scroll (1000 ms nominal; ASSUMPTION)
    R -> omitted (system/LLM time is always excluded)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import klm  # noqa: E402

CLICK_NAMES = {1: "", 2: "double-click ", 3: "triple-click "}


def clean(text: str) -> str:
    """Make a label safe for a Cogulator line.

    <..> would create working-memory chunks, (..) could parse as a time
    modifier, and leading dots would change the nesting level.
    """
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = text.replace("<", "'").replace(">", "'").replace("(", "[").replace(")", "]")
    return text.lstrip(". ").strip() or "step"


def ms(seconds: float) -> int:
    return int(round(seconds * 1000))


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(text)).strip("_") or "x"


def step_lines(step: dict, ops, table: dict, s_key: str, state: dict,
               depth: int, scroll_op: str) -> list[str]:
    """Operator lines for one step. `state` tracks hands + mouse button.

    s_key selects the S time: "nominal" for the low export, "high" for high.
    """
    dots = ". " * depth
    target = clean(step.get("target") or step["label"])
    chunks = " ".join(f"<{clean(c)}>" for c in step.get("chunks") or [])
    lines: list[str] = []
    for op, n in ops:
        if op == "M":
            for _ in range(n):
                lines.append(f"{dots}Think {target} ({ms(table['M'])} ms)")
        elif op == "P":
            drag = " [dragging]" if state["button_down"] else ""
            for _ in range(n):
                lines.append(f"{dots}Point to {target}{drag} ({ms(table['P'])} ms)")
        elif op == "H":
            for _ in range(n):
                state["hands"] = "keyboard" if state["hands"] == "mouse" else "mouse"
                lines.append(f"{dots}Hands to {state['hands']} ({ms(table['H'])} ms)")
        elif op == "K":
            if n == 1:
                lines.append(f"{dots}Keystroke {target} ({ms(table['K'])} ms)")
            else:
                lines.append(f"{dots}Type {target} [{n} keys] ({ms(n * table['K'])} ms)")
        elif op == "S":
            lines.append(
                f"{dots}{scroll_op} scroll {target} [S, assumption] "
                f"({ms(table['S'][s_key])} ms)"
            )
        elif op == "B":
            remaining = n
            if state["button_down"]:
                lines.append(f"{dots}Click release on {target} ({ms(table['B'])} ms)")
                state["button_down"] = False
                remaining -= 1
            clicks, odd = divmod(remaining, 2)
            if clicks:
                name = CLICK_NAMES.get(clicks, f"{clicks}x click ")
                lines.append(f"{dots}Click {name}{target} ({ms(clicks * 2 * table['B'])} ms)")
            if odd:
                lines.append(f"{dots}Click press on {target} ({ms(table['B'])} ms)")
                state["button_down"] = True
        # R: system/LLM time is excluded from the model by design.
    if chunks and lines:
        # Chunks ride on the step's Think line (the "read a value" M) if any,
        # else on its first line, so Cogulator's working-memory tracker sees them.
        idx = next((i for i, ln in enumerate(lines) if ln.startswith(f"{dots}Think ")), 0)
        head, _, tail = lines[idx].rpartition(" (")
        lines[idx] = f"{head} {chunks} ({tail}"
    return lines


def method_body(method: dict, table: dict, variant: str, depth: int, scroll_op: str) -> list[str]:
    state = {"hands": "mouse", "button_down": False}
    s_key = "high" if variant == "high" else "nominal"
    out: list[str] = []
    for step in method["steps"]:
        ops = klm.parse_ops(step.get("ops_low"))
        if variant == "high":
            ops = ops + klm.parse_ops(step.get("ops_extra"))
        out += step_lines(step, ops, table, s_key, state, depth, scroll_op)
    return out


def method_goal(task: dict, method: dict) -> str:
    name = method.get("name") or method["id"]
    return clean(f"{task['id']} {method['id']} {name}")


def export_method(task: dict, method: dict, table: dict, variant: str, scroll_op: str) -> str:
    lines = [f"Goal: {method_goal(task, method)}"]
    lines += method_body(method, table, variant, 1, scroll_op)
    return "\n".join(lines)


def export_selection(task: dict, table: dict, variant: str, scroll_op: str) -> str:
    methods = task["methods"]
    default = next((m for m in methods if m.get("default")), methods[0])
    lines = [f"CreateState method {slug(default['id'])}"]
    for m in methods:
        lines.append(f"If method {slug(m['id'])}")
        lines.append(f". Goal: {method_goal(task, m)}")
        lines += method_body(m, table, variant, 2, scroll_op)
        lines.append("EndIf")
    return "\n".join(lines)


def build(model: dict, table: dict, variant: str, scroll_op: str) -> tuple[str, dict]:
    """Return (markdown, {filename: code})."""
    md = [
        f"# Cogulator models — {model.get('app', '')}".rstrip(" —"),
        "",
        f"Variant: **{variant}** (`low` = ops_low; `high` = ops_low + ops_extra, S high). "
        "Every line carries an explicit time modifier, so Cogulator uses our "
        f"table ({klm.table_line(table)}), not its defaults.",
        "",
        "Chunks in `<angle brackets>` feed Cogulator's working-memory estimate. "
        "R (system/LLM time) is omitted. S is a non-standard scroll operator "
        f"exported as `{scroll_op}` with an explicit time — an assumption.",
        "",
        f"> {klm.DISCLAIMER}",
        "",
    ]
    files: dict[str, str] = {}
    for task in model["tasks"]:
        methods = task.get("methods") or []
        if not methods:
            continue
        md += [f"## {task['id']} — {task.get('title', '')}".rstrip(" —"), ""]
        for m in methods:
            code = export_method(task, m, table, variant, scroll_op)
            files[f"{slug(task['id'])}_{slug(m['id'])}.txt"] = code
            md += [f"### Method {m['id']} — {m.get('name', '')}".rstrip(" —"), ""]
            if m.get("selection_rule"):
                md += [f"Selection rule: {m['selection_rule']}", ""]
            chunks = sorted({str(c) for s in m["steps"] for c in s.get("chunks") or []})
            md += [f"Working-memory chunks: {', '.join(chunks) if chunks else 'none declared'}", ""]
            md += ["```", code, "```", ""]
            skipped = [s["label"] for s in m["steps"]
                       if "R" in (s.get("ops_low") or "").split()]
            if skipped:
                md += [f"R omitted in: {'; '.join(skipped)}.", ""]
        if len(methods) > 1:
            code = export_selection(task, table, variant, scroll_op)
            files[f"{slug(task['id'])}_selection.txt"] = code
            default = next((m for m in methods if m.get("default")), methods[0])
            md += [
                "### Selection rule block",
                "",
                f"`CreateState` picks **{default['id']}**; change its value to "
                "evaluate another method. Rules as stated in the model:",
                "",
            ]
            md += [f"- **{m['id']}**: {m.get('selection_rule') or '(not stated)'}" for m in methods]
            md += ["", "```", code, "```", ""]
    return "\n".join(md), files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="model.yaml -> Cogulator text")
    ap.add_argument("model")
    ap.add_argument("--variant", choices=("low", "high"), default="low")
    ap.add_argument("--out-dir", help="also write one .txt per method/selection block")
    ap.add_argument("--table", help="operator overrides (same as klm.py --table)")
    ap.add_argument("--scroll-operator", default="Point",
                    help="Cogulator operator used for S (default Point; use a custom one if defined)")
    args = ap.parse_args(argv)
    try:
        table = klm.load_table(args.table)
        model = klm.load_model(args.model)
    except klm.ModelError as exc:
        print(f"cogulator_export.py: error: {exc}", file=sys.stderr)
        return 2
    md, files = build(model, table, args.variant, args.scroll_operator)
    if args.out_dir:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        for name, code in files.items():
            (out / name).write_text(code + "\n", encoding="utf-8")
    sys.stdout.buffer.write((md + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
