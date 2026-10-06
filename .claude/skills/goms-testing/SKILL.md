---
name: goms-testing
description: GOMS/KLM test design for any web app. Use for GOMS, KLM, Cogulator, predicted task time, a second-analyst walkthrough, or model vs observed; outputs hypotheses for moderated tests.
---

# GOMS testing

Turn "here is an app URL + a task list" into a GOMS/KLM test design that
**complements moderated usability testing**. Works for any web app
(any web app you can open in a browser); nothing here is
app-specific except `examples/`.

**GOMS output is a hypothesis, never a finding about users.** Rankings and
method ratios matter more than absolute seconds, and every report says so.

## Hard rules (these override everything below)

1. **Never** save, submit, send, import, run-and-save, star or favourite,
   Add, create an account, log in, or enter personal data.
2. **Stop before any state-changing click.** Model it and tag it
   **[NOT EXECUTED]** (`status: not_executed`).
3. **Never claim a step works unless you observed it.** Otherwise tag it
   **[NOT VERIFIED]** (`not_verified`). Behaviour taken from product docs is
   **[DOCUMENTED]** (`documented`).
4. **Don't send messages to in-app AI assistants** unless the user
   explicitly approves in chat. If none were sent, the report must say
   *answer relevance was not assessed*.
5. **Write one new report file** at the output location and **modify
   nothing else in the user's folders**. Working files (app-profile.yaml,
   model.yaml, Cogulator .txt) live in the session scratch directory. The
   report embeds the model YAML (§4.5) and the observer sheet (§7), so it
   stands alone.
6. If the user's browser restores a real or non-demo session, **don't
   touch it**. Use another clean browser and say so in the report.

## Files

| Path | Use |
|---|---|
| `references/m-rules.md` | M placement, Rules 0–4 + "read a value", with GUI examples. **Read before modelling.** |
| `references/cogulator-syntax.md` | Cogulator lines, chunks, `@Goal:`, `Also:`, selection rules, forced times |
| `references/goms-debt.md` | Per-task debt checklist (density, Fitts, expert-only, R, WM, search-cost marker) + DS Fitts flag |
| `templates/app-profile.yaml` | Inputs: URL, guest/demo entry, viewport, forbidden actions, languages, output |
| `templates/model.yaml` | tasks → methods → steps schema |
| `templates/report.md` | Report sections 0–10 |
| `scripts/klm.py` | KLM totals, ranges, ratios, per-step cumulative (`--md` / `--json`) |
| `scripts/cogulator_export.py` | model → Cogulator text per method + If/EndIf selection blocks |
| `scripts/sheet.py` | model → observer recording sheet (`--lang en\|cs`) |
| `scripts/measure_r.py` | optional Playwright replay of **verified read-only** steps to measure R |
| `examples/demo/model.yaml` | regression fixture for a fictional app (see tests) |
| `examples/demo/app-profile.yaml` | profile skeleton with TODOs, no flows |

Run the scripts from this skill's directory (`skills/goms-testing/` here, `.claude/skills/goms-testing/` once installed).
They need Python 3.10+ and PyYAML; `measure_r.py` also needs `playwright`.

## Workflow

### 1. Collect inputs: one batched question

Ask once, all together (AskUserQuestion or a single message):
- app **URL**; **guest/demo** entry (never a real account)
- **task list** and the **session script** (what participants will be asked)
- **prior model**, if any. Note its path but **don't open it** until step 7.
- **output location** and format
- **languages**: participant (questions, sheet) and report

Record the answers in an `app-profile.yaml` (from `templates/`, saved in
the scratch directory). The default viewport is 1440×900 unless the user
says otherwise.

### 2. Triage every step

For each task and step, mark:
- **⚙ routine**: a known procedure; model it (`triage: routine`).
- **👁 discovery / comprehension**: finding, reading, understanding. Test
  it only, don't model it (`triage: discovery`, no methods).
- **Skip** learning and recall modules (`skip`). Flag QA-only items
  (`qa_only`); they go to the team, not to participants.

### 3. Walk the live app in a clean profile

- Use a **clean browser profile** at the **fixed viewport** (default
  1440×900). Use the built-in browser pane or a fresh Playwright context,
  never the user's logged-in browser. If a real session appears, stop,
  switch browsers, and note it (Hard rule 6).
- Record **verbatim**: labels, aria-labels, defaults, where dialogs open
  (**first time vs last-used tab**), **staged-Save** behaviour (does
  anything persist before Save?), **target sizes** (DOM box px), **distance
  below the fold**, and **search result lists**.
- Test every search with the **company name, ticker AND full legal name**,
  and record each result list.
- Stop before every state-changing control (Hard rules 1–2).
- For the Fitts flag, detect design tokens as described in
  `references/goms-debt.md` (DS tie-in). Don't hardcode values.

### 4. Use product docs for what must not be executed

Behaviour behind a forbidden click (what Save does, what an import
produces) comes from product docs. Model it with `status: documented` and
cite the doc in `note`.

### 5. Build the model and run the scripts

1. Write `model.yaml` (from `templates/model.yaml`) in the scratch
   directory. Place M with `references/m-rules.md`, and log non-obvious
   calls in `note`. Free-text lengths are explicit assumptions.
2. Run:

   ```bash
   python scripts/klm.py model.yaml --md          # results, ratios, per-step cumulative
   python scripts/klm.py model.yaml --json        # machine-readable
   python scripts/cogulator_export.py model.yaml  # Cogulator code + chunks + selection blocks
   python scripts/sheet.py model.yaml --lang cs   # observer sheet in the participant language
   ```

   A bad token stops klm.py with exit 2 and names the task, method and step.
   Fix the model, never the script.
3. Optional: measure R.
   `python scripts/measure_r.py model.yaml --profile app-profile.yaml --dry-run`
   first. It hard-refuses (exit 3, no browser started) any step with a
   `replay` block whose status isn't `verified` or that matches a
   forbidden action, personal data, a foreign origin, or an unapproved AI
   message.
4. Fill `templates/report.md` → one new file at the output location.
   Section 1 ranks hotspots **failure > delay > gap**. Section 6 turns each
   hotspot into hypothesis → what to observe → a post-task question in the
   participant's language. Section 8 is the debt checklist per task.

### 6. Model both methods wherever two exist

Wherever one goal has two methods (form vs chat, drag vs picker, batch
vs one-by-one, search vs browse), model **both** and give each a
`selection_rule` (a hypothesis until observed). klm.py reports their
ratio, with and without free text. The ratio is the headline, not the
seconds.

### 7. Only then compare with a prior model

Once your models are final, open the prior model. List **every**
difference in report §9 (task · method · prior · ours · reason), e.g. H
omitted, a different M rule, first-time tab, a new method. Don't "fix"
your model toward the prior without a reason you can state.

### 8. Verify before handing over

- [ ] `python -m pytest tests -q` passes (if the scripts were touched).
- [ ] klm.py, cogulator_export.py and sheet.py run clean on the final
      model, and the pasted tables match the current output.
- [ ] Every report section 0–10 is present and filled, or says why not.
- [ ] Every link and path in the report resolves.
- [ ] The disclaimer is present: hypotheses, not findings; ratios over seconds.
- [ ] The AI-assistant line is present ("not assessed" if no messages were sent).
- [ ] Every non-observed step carries [NOT EXECUTED] / [NOT VERIFIED] / [DOCUMENTED].
- [ ] **Re-read the written report from its destination path**, not from memory.
- [ ] Nothing else in the user's folders changed.

## Modelling conventions (summary; detail in references/)

- Tokens: `M P B BB… H K nK S R`, whitespace-separated. Click = `BB`;
  drag = `P B P B`; Ctrl modifier = 1 K; `H` on every mouse↔keyboard switch.
- `ops_low` counts toward nominal and low; `ops_extra` counts only toward
  high (extra Ms under Rule 2, first-time tabs, optional steps).
- **S** (scroll) is non-standard: 1.0 s nominal, 0.5 low, 2.0 high. Label it
  an assumption.
- **R** (system/LLM) is written down but **always excluded**; measure it and
  subtract it from observed times.
- Reported range = floor(low × 0.8) – ceil(high × 1.2). klm.py also reports
  nominal without free text (runs of ≥ 20 K).
- No M for visual search (expert assumption); that gap is density debt.
- Operator table override: `--table K=0.2,P=1.2` or `--table table.yaml`.
  State any override in report §4.

## Not covered

- It doesn't recruit or moderate participants, or analyse observed
  sessions statistically. The sheet collects data, and the search-cost
  marker is a rough per-task comparison.
- It doesn't cover mobile or touch operators (tap, swipe) or KLM for
  voice. Desktop web only unless you extend the operator table.
- It doesn't judge AI answer quality unless the user approves sending
  messages.
- `measure_r.py` replays only verified, read-only steps that carry a
  `replay` block. It never logs in and never measures behind forbidden
  actions.
