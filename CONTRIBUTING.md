# Contributing

Keep the skills useful across studies, products and teams. Separate what is method (prompts,
schemas, scripts, rules that held in real sessions) from one study's conventions and examples.
When a rule is not universal, state its boundary — model, language, recording source, tool.

Contributions that help most:

- **Evidence from real use** — which step failed, on what kind of recording, with what model —
  without participant data.
- **New locales** (`ux-interview-analysis/locales/<lang>.yaml`) and prompt fixes, with the
  prompt version bumped (`*.v3.md`) rather than edited in place, so earlier runs stay reproducible.
- **New renderers** that read the same board JSON (Miro, tldraw, a document …).
- **Tests that exercise behaviour** (KLM arithmetic, coverage gaps, quote rendering, sanitizer
  refusals) rather than checking prose.

Never commit recordings, transcripts, participant names, screenshots of client products, keys or
deployment ids — not even in tests. Use fictional fixtures.

Before submitting:

```bash
python scripts/validate_skills.py
python -B .claude/skills/skill-library-audit/scripts/audit_library.py --skills-root .claude/skills
python -m pytest .claude/skills/goms-testing/tests -q
python -B -m unittest discover -s scripts -p test_agent_setup.py
```
