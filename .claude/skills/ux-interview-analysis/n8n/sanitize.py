#!/usr/bin/env python3
"""Turn n8n workflow exports into shareable templates — no credentials, IDs or account data.

Pure and local. Input: workflow JSON files downloaded from the n8n editor (… → Download) or fetched
through an n8n MCP server ({"success":…, "data":{…}} is unwrapped). Output: one sanitized
template per workflow.

What is removed or replaced:
- everything at the top level except name, nodes, connections and settings.executionOrder
  (ids, versions, sharing/owner/project data, tags, pinned data, static data)
- node credentials (the importer selects their own) and webhook ids (replaced by fresh UUIDs)
- the API key compared in any IF condition whose left side reads the x-api-key header
- NocoDB node workspace / base / table ids
- every literal listed in a private mapping file (`--map private_map.json`, NEVER committed):
  {"<literal found in your exports>": "<PLACEHOLDER>", …} — use it for table ids inside Code
  nodes, base URLs, folder ids, emails …

Leak check: the script refuses to write if any mapped literal, any e-mail address, or any
`--forbid` substring is still present after sanitizing.

Usage:
    python n8n/sanitize.py exports/*.json --map ../private_map.json --out n8n/workflows \
        --forbid mycompany --forbid my-n8n.example.com
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
API_KEY_PLACEHOLDER = "REPLACE_WITH_YOUR_API_KEY"
NOCODB_PARAMS = {"workspaceId": "REPLACE_NOCODB_WORKSPACE_ID", "projectId": "REPLACE_NOCODB_BASE_ID",
                 "table": "REPLACE_NOCODB_TABLE_ID"}


def slug(name: str) -> str:
    s = re.sub(r"\(.*?\)", "", name)
    s = s.split(":", 1)[-1] if ":" in s else s
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def replace_literals(obj, mapping):
    if isinstance(obj, str):
        for k in sorted(mapping, key=len, reverse=True):
            obj = obj.replace(k, mapping[k])
        return obj
    if isinstance(obj, list):
        return [replace_literals(x, mapping) for x in obj]
    if isinstance(obj, dict):
        return {k: replace_literals(v, mapping) for k, v in obj.items()}
    return obj


def scrub_api_key(node) -> int:
    hits = 0
    conds = node.get("parameters", {}).get("conditions", {}).get("conditions", [])
    for c in conds if isinstance(conds, list) else []:
        if "x-api-key" in str(c.get("leftValue", "")).lower() and c.get("rightValue"):
            c["rightValue"] = API_KEY_PLACEHOLDER
            hits += 1
    return hits


def sanitize(wf: dict, mapping: dict) -> tuple[dict, list[str]]:
    if "data" in wf and "nodes" not in wf:
        wf = wf["data"]
    notes = []
    nodes = []
    for n in wf["nodes"]:
        n = json.loads(json.dumps(n))
        if n.pop("credentials", None) is not None:
            notes.append(f"{n['name']}: credentials removed")
        if "webhookId" in n:
            n["webhookId"] = str(uuid.uuid4())
        if n.get("type", "").endswith(".if") and scrub_api_key(n):
            notes.append(f"{n['name']}: API key → {API_KEY_PLACEHOLDER}")
        if n.get("type", "").endswith(".nocoDb"):
            p = n.get("parameters", {})
            for k, ph in NOCODB_PARAMS.items():
                if k in p:
                    raw = str(p[k]).lstrip("=")
                    p[k] = mapping.get(raw, ph)  # keep which table it was, when the map knows it
            notes.append(f"{n['name']}: NocoDB ids → placeholders")
        nodes.append(n)
    out = {"name": wf["name"], "nodes": nodes, "connections": wf["connections"],
           "settings": {"executionOrder": (wf.get("settings") or {}).get("executionOrder", "v1")}}
    return replace_literals(out, mapping), notes


def leaks(text: str, mapping: dict, forbid: list[str]) -> list[str]:
    found = [f"mapped literal {k[:6]}…" for k in mapping if k in text]
    found += [f"forbidden '{f}'" for f in forbid if f.lower() in text.lower()]
    found += [f"e-mail {m}" for m in EMAIL.findall(text)]
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exports", nargs="+")
    ap.add_argument("--map", help="private JSON {literal: placeholder}; never commit it")
    ap.add_argument("--out", required=True)
    ap.add_argument("--forbid", action="append", default=[], help="substring that must not survive")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    mapping = json.load(open(a.map, encoding="utf-8")) if a.map else {}
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    bad = 0
    for path in a.exports:
        wf, notes = sanitize(json.load(open(path, encoding="utf-8")), mapping)
        text = json.dumps(wf, ensure_ascii=False, indent=2)
        problems = leaks(text, mapping, a.forbid)
        name = slug(wf["name"]) + ".json"
        if problems:
            bad += 1
            print(f"REFUSED {path}: {', '.join(problems)}")
            continue
        (out_dir / name).write_text(text + "\n", encoding="utf-8")
        print(f"{name}: {len(wf['nodes'])} nodes · " + "; ".join(notes))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
