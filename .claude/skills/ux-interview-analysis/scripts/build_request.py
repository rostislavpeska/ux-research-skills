#!/usr/bin/env python3
"""Build the body for the n8n "UX Harness: Gemini Call" webhook.

Pure: reads the versioned prompt + schema files, writes JSON. No network, no credentials.

Usage:
    python scripts/build_request.py --stage transcript \
        --prompt prompts/transcript.v1.md --schema schemas/transcript.v1.json \
        --interview S1-U01 --file-uri URI --mime video/mp4 \
        --start 0 --end 600 --model gemini-3.8-flash --lang cs \
        --var glossary=@examples/demo/glossary.txt [-o request.json]

Placeholders in the prompt: {{window_start}}, {{window_end}} (MM:SS, from --start/--end),
the `prompt:` keys of locales/<lang>.yaml (with --lang), plus any --var key=value
(value "@path" reads a file). An unfilled placeholder is an error.
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
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--stage", required=True)
    ap.add_argument("--prompt", required=True, type=Path)
    ap.add_argument("--schema", required=True, type=Path)
    ap.add_argument("--interview", required=True)
    ap.add_argument("--file-uri", required=True)
    ap.add_argument("--mime", default="video/mp4")
    ap.add_argument("--model", required=True)
    ap.add_argument("--start", type=float, default=None, help="clip start, seconds")
    ap.add_argument("--end", type=float, default=None, help="clip end, seconds")
    ap.add_argument("--fps", type=float, default=None)
    ap.add_argument("--media-resolution", default="MEDIA_RESOLUTION_LOW")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-output-tokens", type=int, default=32768)
    ap.add_argument("--var", action="append", default=[], help="key=value or key=@file")
    ap.add_argument("--lang", help="locale code (locales/<lang>.yaml): fills the prompt's language hints")
    ap.add_argument("-o", "--out", type=Path)
    a = ap.parse_args()

    variables = {
        "window_start": mmss(a.start or 0),
        "window_end": mmss(a.end) if a.end is not None else "end",
    }
    if a.lang:
        import yaml  # lazy: only needed with --lang
        locale_file = Path(__file__).resolve().parent.parent / "locales" / f"{a.lang}.yaml"
        if not locale_file.exists():
            sys.exit(f"no locale {locale_file} - add one (see locales/README.md)")
        variables.update(yaml.safe_load(locale_file.read_text(encoding="utf-8"))["prompt"])
    for item in a.var:
        key, _, value = item.partition("=")
        if value.startswith("@"):
            value = Path(value[1:]).read_text(encoding="utf-8").strip()
        variables[key] = value

    def fill(m: re.Match) -> str:
        key = m.group(1)
        if key not in variables:
            sys.exit(f"unfilled placeholder {{{{{key}}}}} in {a.prompt}")
        return variables[key]

    prompt = re.sub(r"\{\{(\w+)\}\}", fill, a.prompt.read_text(encoding="utf-8"))
    schema = json.loads(a.schema.read_text(encoding="utf-8"))

    media = {"fileData": {"fileUri": a.file_uri, "mimeType": a.mime}}
    clip = {}
    if a.start is not None:
        clip["startOffset"] = f"{a.start:g}s"
    if a.end is not None:
        clip["endOffset"] = f"{a.end:g}s"
    if a.fps is not None:
        clip["fps"] = a.fps
    if clip:
        media["videoMetadata"] = clip

    generation = {
        "responseMimeType": "application/json",
        "responseJsonSchema": schema,
        "temperature": a.temperature,
        "maxOutputTokens": a.max_output_tokens,
    }
    if a.media_resolution:
        generation["mediaResolution"] = a.media_resolution

    body = {
        "interview_id": a.interview,
        "stage": a.stage,
        "prompt_version": a.prompt.stem,  # e.g. transcript.v1
        "model": a.model,
        "request": {
            "contents": [{"role": "user", "parts": [media, {"text": prompt}]}],
            "generationConfig": generation,
        },
    }
    text = json.dumps(body, ensure_ascii=False, indent=2)
    if a.out:
        a.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
