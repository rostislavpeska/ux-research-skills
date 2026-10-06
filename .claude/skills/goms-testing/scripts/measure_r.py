#!/usr/bin/env python3
"""Measure system response time (R) by replaying READ-ONLY navigation steps.

Optional helper — needs Python Playwright:
    pip install playwright && python -m playwright install chromium

Usage:
    python scripts/measure_r.py MODEL.yaml --profile app-profile.yaml
        [--task M1.2] [--method G] [--runs 3] [--dry-run] [--json] [--headed]

A step is replayable only if it carries a `replay` block:

    replay:
      action: goto | click | fill | press | hover
      url: /path                       # goto — resolved against profile base_url
      selector: "role=button[name='Search']"   # click / fill / press / hover
      text: "AAPL"                     # fill (never personal data)
      key: Enter                       # press
      until: {selector: "text=Apple Inc.", state: visible}   # or load |
                                       # domcontentloaded | networkidle
      timeout_ms: 15000

HARD GATE (checked for every step with a replay block BEFORE a browser
starts; one violation refuses the whole run, exit 3):
  * status must be `verified` (observed live as safe);
  * label / target / selector / text / url must not match a forbidden
    action (built-in EN + CS list + the profile's forbidden_actions);
  * fill never enters personal data; goto never leaves base_url's origin;
  * typing into an in-app AI assistant needs `ai_assistant:
    messages_approved: true` in the profile (explicit operator approval).
Replay per method stops at the first step without a replay block (later
state cannot be reached faithfully). Each run uses a fresh browser context
(clean profile) at the profile viewport. The clock starts after the target
is visible and scrolled into view; the end condition is polled tightly
(~5–20 ms) because Playwright's own wait_for backs off to 500 ms polls.
Subtract R from observed times; never add it to the KLM prediction.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import klm  # noqa: E402

ALLOWED_ACTIONS = ("goto", "click", "fill", "press", "hover")
LOAD_STATES = ("load", "domcontentloaded", "networkidle")
UNTIL_STATES = ("visible", "hidden", "attached", "detached")

# State-changing verbs, EN + CS (case-insensitive, word-bounded).
DEFAULT_FORBIDDEN = [
    r"\bsave[sd]?\b", r"\bsubmit", r"\bsend\b", r"\bimport(s|ed|ing)?\b", r"\bstar(red|s)?\b",
    r"\bfavou?rit", r"\badd\b", r"\bcreate\b", r"\bsign[\s_-]?up\b", r"\bregister",
    r"\blog[\s_-]?in\b", r"\bsign[\s_-]?in\b", r"\bdelete", r"\bremove", r"\bpay\b",
    r"\bbuy\b", r"\bpurchase", r"\bsubscribe", r"\bpublish", r"\bupload", r"\bconfirm",
    r"\bcheckout\b",
    r"\bulož", r"\bodesl", r"\bpošl", r"\bposlat\b", r"\bimportov", r"\bpřid(at|ejte|ej|ání)\b",
    r"\bvytvoř", r"\bregistr", r"\bpřihl(ásit|aste|ášení)", r"\bsmaz", r"\bodstran",
    r"\bzaplat", r"\bkoup", r"\bobjedn", r"\bpublik", r"\bnahr(át|ajte|ání)\b", r"\bpotvr",
    r"\boblíben",
]
PERSONAL_FIELD = re.compile(
    r"password|passwd|heslo|e-?mail|phone|\btel\b|telefon|iban|card|karta|birth|narozen|"
    r"address|adresa|rodn[ée]",
    re.I,
)
PERSONAL_VALUE = re.compile(r"@|\d{7,}|\+\d{3}")
AI_TARGET = re.compile(r"\b(chat|assistant|asistent|prompt|ai|copilot)\b", re.I)


class GateViolation(Exception):
    pass


def compile_forbidden(profile_items) -> list[re.Pattern]:
    patterns = [re.compile(p, re.I) for p in DEFAULT_FORBIDDEN]
    for item in profile_items or []:
        item = str(item)
        if item.startswith("re:"):
            patterns.append(re.compile(item[3:], re.I))
        else:
            patterns.append(re.compile(r"\b" + re.escape(item) + r"\b", re.I))
    return patterns


def gate_step(step: dict, forbidden: list[re.Pattern], base_url: str,
              ai_approved: bool = False) -> list[str]:
    """Return every reason this step must NOT be replayed (empty = allowed)."""
    replay = step.get("replay")
    if not replay:
        return []
    reasons = []
    label = step.get("label", "?")
    if step.get("status") != "verified":
        reasons.append(f"status is {step.get('status')!r}, only 'verified' steps may be replayed")
    if not isinstance(replay, dict):
        return reasons + ["replay must be a mapping"]
    action = replay.get("action")
    if action not in ALLOWED_ACTIONS:
        reasons.append(f"action {action!r} not in read-only set {ALLOWED_ACTIONS}")
    haystack = {
        "label": label, "target": step.get("target", ""),
        "selector": replay.get("selector", ""), "text": replay.get("text", ""),
        "url": replay.get("url", ""),
    }
    for field, value in haystack.items():
        for pat in forbidden:
            if value and pat.search(str(value)):
                reasons.append(f"{field} {value!r} matches forbidden action /{pat.pattern}/")
                break
    if action == "fill":
        if PERSONAL_FIELD.search(f"{replay.get('selector', '')} {label} {step.get('target', '')}"):
            reasons.append("fill targets a personal-data field")
        if PERSONAL_VALUE.search(str(replay.get("text", ""))):
            reasons.append("fill text looks like personal data (email / phone / id number)")
    if action in ("fill", "press") and not ai_approved:
        if AI_TARGET.search(f"{replay.get('selector', '')} {label} {step.get('target', '')}"):
            reasons.append("typing into an in-app AI assistant needs ai_assistant.messages_approved: true")
    until = replay.get("until", "load")
    if isinstance(until, dict):
        if not until.get("selector") or until.get("state", "visible") not in UNTIL_STATES:
            reasons.append(f"until needs a selector and a state in {UNTIL_STATES}")
    elif until not in LOAD_STATES:
        reasons.append(f"until {until!r} must be a {{selector, state}} mapping or one of {LOAD_STATES}")
    if action != "goto" and not replay.get("selector"):
        reasons.append(f"action {action!r} needs a selector")
    if action == "goto":
        url = urljoin(base_url or "", str(replay.get("url", "")))
        if base_url and urlparse(url).netloc != urlparse(base_url).netloc:
            reasons.append(f"goto {url!r} leaves the base_url origin")
    return reasons


def plan(model: dict, task_id=None, method_id=None) -> list[tuple[dict, dict, list[dict]]]:
    """[(task, method, replayable-prefix steps)] for the selected methods."""
    out = []
    for task in model["tasks"]:
        if task_id and str(task["id"]) != task_id:
            continue
        for method in task.get("methods") or []:
            if method_id and str(method["id"]) != method_id:
                continue
            prefix = []
            for step in method["steps"]:
                if not step.get("replay"):
                    break
                prefix.append(step)
            out.append((task, method, prefix))
    return out


def gate_model(model: dict, profile: dict, task_id=None, method_id=None) -> list[str]:
    """Check EVERY step that has a replay block in the selected methods."""
    forbidden = compile_forbidden(profile.get("forbidden_actions"))
    base = profile.get("base_url", "")
    ai_ok = bool((profile.get("ai_assistant") or {}).get("messages_approved", False))
    violations = []
    for task, method, _ in plan(model, task_id, method_id):
        for i, step in enumerate(method["steps"], 1):
            for reason in gate_step(step, forbidden, base, ai_ok):
                violations.append(f"{task['id']} · {method['id']} · step {i} "
                                  f"({step.get('label', '?')}): {reason}")
    return violations


def viewport(profile: dict) -> dict:
    raw = str(profile.get("viewport") or "1440x900").lower().replace("×", "x")
    w, _, h = raw.partition("x")
    return {"width": int(w), "height": int(h)}


def run(model: dict, profile: dict, selected, runs: int, headed: bool) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("measure_r.py: error: Python Playwright is not installed "
              "(pip install playwright && python -m playwright install chromium)", file=sys.stderr)
        sys.exit(4)
    base = profile.get("base_url", "")
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        try:
            for task, method, steps in selected:
                if not steps:
                    continue
                samples: dict[int, list[float]] = {i: [] for i in range(len(steps))}
                for _ in range(runs):
                    ctx = browser.new_context(viewport=viewport(profile))  # fresh = clean profile
                    page = ctx.new_page()
                    try:
                        for i, step in enumerate(steps):
                            samples[i].append(replay_step(page, step["replay"], base))
                    finally:
                        ctx.close()
                for i, step in enumerate(steps):
                    vals = samples[i]
                    results.append({
                        "task": str(task["id"]), "method": str(method["id"]), "step": i + 1,
                        "label": step["label"], "action": step["replay"]["action"],
                        "median_s": statistics.median(vals), "min_s": min(vals),
                        "max_s": max(vals), "runs": len(vals),
                    })
        finally:
            browser.close()
    return results


def poll_state(locator, state: str, timeout_s: float) -> float:
    """Tight poll (one CDP round trip, ~5–20 ms) until the locator reaches state.

    Playwright's own wait_for backs off to 500 ms polls, which over-reports
    a 0.4 s response as ~0.9 s — too coarse for R.
    """
    checks = {
        "visible": lambda: locator.is_visible(),
        "hidden": lambda: not locator.is_visible(),
        "attached": lambda: locator.count() > 0,
        "detached": lambda: locator.count() == 0,
    }
    if state not in checks:
        raise ValueError(f"until.state {state!r} not in {sorted(checks)}")
    deadline = time.perf_counter() + timeout_s
    while True:
        try:
            if checks[state]():
                return time.perf_counter()
        except Exception:  # context destroyed mid-navigation — keep polling
            pass
        if time.perf_counter() > deadline:
            raise TimeoutError(f"until {state!r} not reached within {timeout_s:.1f} s")


def replay_step(page, replay: dict, base: str) -> float:
    timeout = int(replay.get("timeout_ms", 15000))
    action = replay["action"]
    target = page.locator(replay["selector"]).first if action != "goto" else None
    if target is not None:
        # Actionability work happens BEFORE the clock starts, so R is the app's
        # response, not Playwright's element checks.
        target.wait_for(state="visible", timeout=timeout)
        target.scroll_into_view_if_needed(timeout=timeout)
    t0 = time.perf_counter()
    if action == "goto":
        page.goto(urljoin(base, str(replay.get("url", ""))), timeout=timeout, wait_until="commit")
    elif action == "click":
        target.click(timeout=timeout)
    elif action == "fill":
        target.fill(str(replay.get("text", "")), timeout=timeout)
    elif action == "press":
        target.press(str(replay.get("key", "Enter")), timeout=timeout)
    elif action == "hover":
        target.hover(timeout=timeout)
    until = replay.get("until", "load")
    if isinstance(until, dict):
        t1 = poll_state(page.locator(until["selector"]).first, until.get("state", "visible"),
                        timeout / 1000)
    elif until in LOAD_STATES:
        page.wait_for_load_state(until, timeout=timeout)
        t1 = time.perf_counter()
    else:
        raise ValueError(f"until {until!r}: use a {{selector, state}} mapping or one of {LOAD_STATES}")
    return t1 - t0


def render_md(results: list[dict]) -> str:
    lines = [
        "## Measured system response (R)", "",
        "> R is subtracted from observed times; it is never added to KLM predictions. "
        "The clock starts after the target is visible and scrolled into view, so values "
        "include only Playwright's action dispatch (tens of ms) plus ~5–20 ms poll resolution.", "",
        "| Task | Method | # | Step | Action | Median R (s) | Min | Max | Runs |",
        "|---|---|---:|---|---|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(f"| {r['task']} | {r['method']} | {r['step']} | {r['label']} | {r['action']} | "
                     f"{r['median_s']:.2f} | {r['min_s']:.2f} | {r['max_s']:.2f} | {r['runs']} |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Replay verified read-only steps to measure R")
    ap.add_argument("model")
    ap.add_argument("--profile", required=True, help="app-profile.yaml (base_url, viewport, forbidden_actions)")
    ap.add_argument("--task")
    ap.add_argument("--method")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true", help="gate + plan only; no browser")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args(argv)
    try:
        model = klm.load_model(args.model)
    except klm.ModelError as exc:
        print(f"measure_r.py: error: {exc}", file=sys.stderr)
        return 2
    import yaml
    profile = yaml.safe_load(Path(args.profile).read_text(encoding="utf-8")) or {}
    violations = gate_model(model, profile, args.task, args.method)
    if violations:
        print("measure_r.py: REFUSED — nothing was replayed:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 3
    selected = plan(model, args.task, args.method)
    if args.dry_run or not any(steps for _, _, steps in selected):
        for task, method, steps in selected:
            names = ", ".join(s["label"] for s in steps) or "(no replayable prefix)"
            print(f"{task['id']} · {method['id']}: {names}")
        return 0
    results = run(model, profile, selected, max(1, args.runs), args.headed)
    out = json.dumps(results, ensure_ascii=False, indent=2) if args.json else render_md(results)
    sys.stdout.buffer.write((out + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
