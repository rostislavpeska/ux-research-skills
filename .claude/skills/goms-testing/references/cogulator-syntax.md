# Cogulator syntax (what cogulator_export.py writes)

Cogulator is a CMN-GOMS calculator that predicts task time and
working-memory load. Source: the Cogulator primer, cogulator.io/primer.html
(checked 2026-09-30). This page covers only the subset we generate or tell
people to hand-edit.

## Lines

```
Goal: M6.2 form Form dialog
. Think dialog opener <goal values> (1350 ms)
. Point to dialog opener (1100 ms)
. Click dialog opener (200 ms)
```

- **`Goal: <name>`** opens a goal.
- **One `.` per nesting level.** Operators under a top-level goal take `. `;
  a sub-goal is `. Goal: …` and its operators take `. . `.
- **Operator line** = `<Operator> <label> <modifier>`. The first word is the
  operator and the rest is a free label.
- **Time modifier** = a trailing `(N ms)` or `(N seconds)`. **We always write
  one**, because Cogulator's defaults differ from our table (the primer
  gives Point = 950 ms, for example). Labels are sanitised so that no other
  parenthesis can be misread as a modifier: `(`→`[`, `)`→`]`.
- **Chunks** in `<angle brackets>` enter working memory
  (`Think read price <price>`). Several per line are fine: `<fund> <ticker>`.
  Labels are sanitised so that stray `<` or `>` never creates a chunk.

## Forced operator table

| KLM | Cogulator line | Modifier |
|---|---|---|
| M | `Think <target>` | `(1350 ms)` |
| P | `Point to <target>` (`[dragging]` while the button is down) | `(1100 ms)` |
| BB | `Click <target>`; `BBBB` = `Click double-click …`, `BBBBBB` = `Click triple-click …` | `(200 ms)` per click |
| B | `Click press on …` / `Click release on …` (a drag is `P B P B`) | `(100 ms)` |
| H | `Hands to keyboard` / `Hands to mouse` (tracked; starts on the mouse) | `(400 ms)` |
| K | `Keystroke <target>` | `(280 ms)` |
| nK | `Type <target> [n keys]` | `(n × 280 ms)`, e.g. `(3080 ms)` for 11 K |
| S | `Point scroll <target> [S, assumption]` (`--scroll-operator` changes the operator) | `(1000 ms)` nominal, `(2000 ms)` in `--variant high` |
| R | omitted (system/LLM time is always excluded) | none |

Chunks attach to the step's `Think` line (the "read a value" M) or, if
there's none, to its first line.

## Method calls (`@Goal:`)

`@Goal: <name>` re-uses a goal declared earlier and may pass chunks:
`@Goal: Point Click <button>`. The exporter doesn't emit it (each method is
written out in full so its times match klm.py); use it when you hand-edit
shared sub-methods.

## Parallel (`Also:`)

`. Also: <goal name>` runs a goal in parallel; `. Also: <goal> as hands`
serialises it on a named thread. KLM is serial, so the exporter never
emits `Also:`. Use it only in a hand-edited what-if model and say so in
report §5.

## Selection rules

```
CreateState method form
If method form
. Goal: M6.2 form Form dialog
. . Think dialog opener (1350 ms)
EndIf
If method chat
. Goal: M6.2 chat In-app AI chat
. . Think chat opener (1350 ms)
EndIf
```

- `CreateState <object> <state>` declares the state; `SetState <object>
  <state>` changes it later. `If <object> <state>` … `EndIf` guards a block,
  and `Goto Goal <name>` jumps.
- **`If` / `EndIf` / `CreateState` take no dot prefix**, and the lines inside
  an `If` are nested one level deeper.
- The exporter writes one selection block per task with ≥ 2 methods.
  `CreateState` picks the method marked `default: true`, or else the first
  one. Change the state value to evaluate another method.

## Notes and comments

Cogulator has **no documented comment syntax**. Anything that isn't an
operator line (selection-rule wording, assumptions, R omissions,
`[NOT EXECUTED]` tags) goes **outside the code blocks**, in the Markdown
around them. Never paste prose into the model.

## Commands

```bash
python scripts/cogulator_export.py model.yaml                  # low variant, Markdown to stdout
python scripts/cogulator_export.py model.yaml --variant high   # + ops_extra, S high
python scripts/cogulator_export.py model.yaml --out-dir cog/   # also one .txt per block
```

The low export's modifiers sum exactly to klm.py's nominal and the high
export's sum to klm.py's high; tests/test_exports.py enforces this.
