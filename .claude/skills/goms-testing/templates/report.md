# GOMS/KLM test design: {{app}}

{{date}} · analyst: {{analyst}} · viewport {{viewport}} · clean browser profile · entry: {{guest|demo}}
Model: embedded in §4.5 · Profile: {{base URL, entry, forbidden actions — summarised in §10 if relevant}}

> **Read this first.** GOMS/KLM output is a set of **hypotheses** about an
> expert, error-free user, with system and LLM time (R) excluded. It is
> **never a finding about users**. **Rankings and method ratios matter more
> than absolute seconds.** Every number below exists to decide what the
> moderated sessions should watch.

Status tags: **[NOT EXECUTED]** = state-changing, modelled but never clicked ·
**[NOT VERIFIED]** = modelled, not observed live · **[DOCUMENTED]** = from
product docs only. Untagged steps were observed in the clean profile.

---

## 0. Executive summary

- {{3–5 bullets: the slowest routine methods (by rank), the biggest method ratio, the top debt, what the sessions must answer}}
- In-app AI assistant: {{no messages sent, so answer relevance was **not assessed** | N messages sent with operator approval on {{date}}}}
- Coverage: {{n}} tasks triaged, {{n}} modelled (⚙), {{n}} test-only (👁), {{n}} QA-only, {{n}} skipped.

## 1. Top 5 hotspots (ranked: failure > delay > gap)

| # | Hotspot | Type (failure / delay / gap) | Task · method · step | Evidence (walkthrough / model) | Moderator question (§6) |
|---:|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

*Failure* = the task is likely to fail (a dead end, a hidden method, a
label mismatch). *Delay* = it succeeds slowly (high KLM, a large ratio,
debt). *Gap* = the model can't see it (density, R, expert-only).

## 2. Task triage

| Task | Goal (participant words) | Triage | Why | Modelled methods |
|---|---|---|---|---|
| | | ⚙ routine / 👁 discovery / QA-only / skip | | |

Learning and recall modules are skipped. QA-only items are listed for
the team, not for participants.

## 3. Verified click paths

Per task and method: the path as walked in the clean profile. UI labels,
aria-labels and defaults verbatim; where dialogs open (first time vs
last-used tab); staged-Save behaviour; target sizes; distance below the
fold; search result lists verbatim (queries by **name, ticker and full
legal name**).

### {{task}} · {{method}}
1. {{step}} — "{{label verbatim}}" (aria-label "…"), {{w×h px}}, {{above fold | +__ px}} {{[NOT EXECUTED] | [NOT VERIFIED] | [DOCUMENTED]}}

## 4. KLM models

Operator table: K 0.28 · P 1.10 · B 0.10 (click = BB) · H 0.40 · M 1.35 s ·
S 1.0 s nominal (0.5–2.0, **non-standard, an assumption**) · R excluded.
M rules applied: `references/m-rules.md` (Rules 0–4 plus "read a value").

### 4.1 Results

{{paste: python scripts/klm.py model.yaml --md, the results and ratio tables}}

### 4.2 Method ratios

{{ratio table. Note which ratios flip when free text is excluded}}

### 4.3 Judgement calls

| Task · method · step | Call | Alternative | Effect on the total |
|---|---|---|---|
| | e.g. Rule 2: one M for three ticks (low), per-tick M in high | M per tick | +2.7 s high |

### 4.4 Per-step models

{{paste the per-step cumulative tables from klm.py --md}}

### 4.5 Model (embedded) and how to reproduce

The report is the only file written to the user's folder, so the full
model lives here. Save it as `model.yaml` and run the skill's scripts:

```bash
python scripts/klm.py model.yaml --md
python scripts/cogulator_export.py model.yaml
python scripts/sheet.py model.yaml --lang {{participant language}}
```

<details><summary>model.yaml</summary>

```yaml
{{paste the final model.yaml}}
```

</details>

## 5. Cogulator models + working-memory chunks

{{paste: python scripts/cogulator_export.py model.yaml. Code blocks hold operator lines only; notes stay outside}}

| Task · method | Chunks held | Peak concurrent | Risk |
|---|---|---:|---|
| | | | |

## 6. Hypotheses → moderator questions

| Hotspot | Hypothesis (GOMS says…) | What to observe | Post-task question ({{participant language}}) |
|---|---|---|---|
| | e.g. the chat is 1.41× faster than the form only if the prompt is short | method chosen, prompt length, edits | „{{question in the participant language}}" |

Questions are neutral: never name the modelled path or the "right" button.

## 7. Observer recording sheet

{{paste: python scripts/sheet.py model.yaml --lang {{participant language}} (embedded; the report is the only file written)}}

## 8. GOMS debt per task

{{one block per task from references/goms-debt.md: D1 density, D2 Fitts (min target token or "none found"), D3 expert-only, D4 excluded R, D5 working memory, D6 search-cost marker (filled after the sessions)}}

## 9. Differences vs any prior model

Read the prior model **only after** §4–§5 were final.

| Task · method | Prior | Ours | Difference | Reason |
|---|---|---|---|---|
| | | | | e.g. prior skipped H; the dialog opens on the last-used tab (extra) |

{{or: "No prior model was provided."}}

## 10. Open questions / not verified

- Every [NOT VERIFIED], [NOT EXECUTED] and [DOCUMENTED] step, and what would verify it.
- Assumptions: free-text lengths, S distances, selection rules not yet observed.
- In-app AI answer relevance: {{not assessed (no messages sent) | …}}.
- Design-token detection: {{min target token name/value | none found, WCAG 2.2 SC 2.5.8 used as the external floor}}.
