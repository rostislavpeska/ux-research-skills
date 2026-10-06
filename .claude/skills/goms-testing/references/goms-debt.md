# GOMS debt: what the model can't see

KLM predicts an **expert, error-free** user on a **known** method with
system time removed. Everything outside that is *GOMS debt*. It's real
time the participant spends that the model deliberately leaves out. Debt
is never added to the KLM total; it's listed per task (report §8), ranked,
and turned into moderator questions (§6).

Fill this checklist for **every modelled task**, and for discovery tasks
where it applies.

## Per-task checklist

| # | Debt | What to record during the walkthrough | Hotspot when |
|---|---|---|---|
| D1 | **Visual search / density (Hick–Hyman)**: choice time grows with the number of equally likely options, T ≈ a + b·log₂(n + 1) | n = options in the region the user must scan (menu items, result rows, table columns, icons); record the result lists **verbatim**, and for company search test the **name, ticker AND full legal name** | n is large, options look alike, or the right one isn't first for one of the three queries |
| D2 | **Pointing difficulty (Fitts)**: MT ≈ a + b·log₂(D/W + 1); P = 1.10 s is an average that hides it | target size W (px, from the DOM box at the fixed viewport), distance D from the previous target, distance **below the fold** | W is below the minimum target (see the DS tie-in below), or D is large and W small (icon-only, edge-of-row actions) |
| D3 | **Expert-only assumption**: the model assumes the method is known | labels vs participant vocabulary (in the participant's language), icon-only controls, methods found only through docs, first-time vs last-used dialog tab, defaults that must be noticed, staged Save (nothing persists until a later Save) | the method is found only through docs, a label doesn't match the task wording, or the dialog opens on a different tab the first time |
| D4 | **Excluded system / LLM time (R)**: always excluded from KLM | every R in the method: page loads, search latency, LLM answers; measure with `scripts/measure_r.py` (verified read-only steps only) or from the recording | R per step > ~1 s, or LLM time dominates the chat method (and answer relevance was **not assessed** unless messages were approved) |
| D5 | **Working memory**: chunks held across steps | `chunks` per step; Cogulator's working-memory estimate | more than ~4 chunks held at once, or a value must be re-typed from memory |
| D6 | **Search-cost marker** | after the session: (observed − R) − predicted nominal | the gap exceeds predicted high, or tasks rank differently than predicted |

## The search-cost marker

```
search/comprehension cost ≈ (observed − measured R) − predicted nominal
```

This is a **marker**, not a measurement. It rolls up D1–D3 and D5 together
with errors and hesitation. Compare it **across tasks and methods**; the
absolute value doesn't matter much. A large marker on a task the model
calls fast is the most useful hotspot the pairing of GOMS and moderated
testing can produce.

## Design-system tie-in (Fitts flag)

Only if the target app, or the repo that holds its design tokens, defines a
**minimum target size** or **spacing tokens**. **Detect them; don't
hardcode values.**

1. Search the token sources (the JSON token files and the built CSS custom
   properties). With the Grep tool, or in a shell:

   ```bash
   rg -n -i "(min[-_]?(target|touch|tap|hit|click)|(target|touch|tap|hit)[-_]?(size|min|area))" <token-dir> <built-css>
   rg -n -i "\"?(--)?(spacing|space|gap)[-_][a-z0-9_-]+\"?\s*[:=]" <token-dir> <built-css>
   ```

2. If a min-target token exists, record its **name and value** in the app
   profile under `design_tokens.min_target`. Every modelled target whose
   rendered box (from the walkthrough DOM) is smaller is a **Fitts hotspot**
   (D2) and goes into report §1.
3. If only spacing tokens exist, use them for the *spacing* half of the
   check. Undersized targets need clearance from neighbours: flag adjacent
   targets closer than the smallest spacing step the DS uses between
   interactive controls.
4. If nothing is found, say so in report §10. The fallback floor is the
   external standard **WCAG 2.2 SC 2.5.8 Target Size (Minimum)**. Label it
   as an external criterion, not a DS token.

**This repo (aig-desigsystem), detected 2026-09-30:** there's no dedicated
min-target token. It does have a spacing scale (`spacing-*`, `space-*` in
`tokens/base.tokens.json`) and `selection-size`. `selection-size` is the
checkbox/radio glyph size, **not** a hit-area minimum, so don't use it as the
threshold. Button heights are `CALIBRATED` component constants in CSS, not
tokens. Re-run the detection before each study; tokens change.

## Per-task block (copy into report §8)

```markdown
### <task id> — <title>
- D1 density: n = __ options in <region>; result lists: name "…" → […], ticker "…" → […], legal name "…" → […]
- D2 Fitts: smallest target __×__ px (<element>), min token <name|none> → <ok|HOTSPOT>; below fold __ px
- D3 expert-only: <labels vs vocabulary, first-time tab, staged Save, docs-only method>
- D4 excluded R: <step: measured __ s | not measured>; LLM relevance <assessed | NOT assessed>
- D5 WM chunks: max __ held (<chunks>)
- D6 marker: filled after the session: (observed − R) − predicted = __ s
```
