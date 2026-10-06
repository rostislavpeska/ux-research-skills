# Agent guidance

This repository is the authoring source for these skills — edit them here, nowhere else.
Published skills live in `.claude/skills/` — one physical source. Create the ignored `.agents/skills`
discovery link for Codex, Cursor, Gemini CLI and VS Code Copilot with
`python scripts/setup_repo_skill_links.py`; never duplicate packages under other folders.
`CLAUDE.md` and `GEMINI.md` import this file. See [agent setup](docs/agent-setup.md).
Load only the skills and references relevant to the task.

This repository is shared UX-research method. Keep study-specific material out of it: participant
names, recordings, transcripts, client names, product screenshots, deployment URLs, workflow or
database ids, credentials and keys belong in the consuming project (gitignored `out/` or private
configuration), never in a package.

Packages:

- `goms-testing` — GOMS/KLM test design before moderated sessions. Output = hypotheses.
- `ux-interview-analysis` — evidence-traced analysis of screen-recorded sessions; bundles its n8n
  templates (`n8n/`) and the FigJam renderer (`renderers/figjam/`).
- `skill-library-audit` — shared companion: checks every package's resource closure.

After changing a skill or helper, run:

```bash
python scripts/validate_skills.py
python -B .claude/skills/skill-library-audit/scripts/audit_library.py --skills-root .claude/skills
python -m pytest .claude/skills/goms-testing/tests -q
```

Every new file in a package must be declared in its `resources.json`; every new external
prerequisite needs an entry with the operations it blocks. Never weaken the evidence rules of
`ux-interview-analysis` (verify on frames, insert quotes by script, prefer false negatives) to make a
run pass.
