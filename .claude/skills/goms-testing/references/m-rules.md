# M-placement rules

Heuristics from Card, Moran & Newell (1983, ch. 8), applied the way Kieras
teaches KLM. Write the **physical** operators first (P, BB, H, K, S), then
place M with Rule 0 and delete with Rules 1–4. Every M you keep or delete is
a judgement call: log the non-obvious ones in the step `note` and in report
§4 ("judgement calls").

Operator table (forced everywhere): K 0.28 · P 1.10 · B 0.10 (click = BB) ·
H 0.40 · M 1.35 s · S 1.0 s nominal (0.5–2.0; non-standard, an assumption) ·
R excluded.

---

## Rule 0: insert candidate Ms

Put an **M before every K that is not part of an argument string** (a command
keystroke such as a shortcut, Enter, Esc, Tab-to-commit, or a Ctrl modifier
used as a command) and an **M before every P that selects a command**: tab,
button, star, select, list option, checkbox, menu item, link.

- Clicking **into** a text or number field points at an *argument*, so it gets **no M**.
- Typed values are argument strings, so there's **no M per keystroke**.

| GUI step | ops | why |
|---|---|---|
| Click the **Filters** tab | `M P BB` | P selects a command (a tab) |
| Click into the **Amount** field | `P BB` | pointing at an argument, no M |
| Type `1500` | `H 4K` | argument string, no M per key |
| Press **Ctrl+K** to open search | `H M 2K` | command keystrokes (Ctrl = 1 K) |

## Rule 1: delete M when the next operator is fully anticipated

If the operator after an M was fully anticipated by the one before, drop the M.

- **P + BB is one unit**, so there's never an M between pointing and clicking.
- The **option of a just-opened select** gets no M: deciding to open it
  already decided the option.

| GUI step | ops |
|---|---|
| Open the **Currency** select | `M P BB` |
| Pick **CZK** in the list that just opened | `P BB` (no M, Rule 1) |
| Ctrl-click the 2nd file after clicking the 1st (multi-select plan) | `K P BB` (no M) |

## Rule 2: one cognitive unit keeps one M

Repeated identical commands that form **one cognitive unit** keep **one M in
the low variant**. The **high variant keeps an M per click**, so put the extra
Ms in `ops_extra`.

| GUI step | ops_low | ops_extra |
|---|---|---|
| Tick **Stocks** | `M P BB` | |
| Tick **ETFs** | `P BB` | `M` |
| Tick **Bonds** | `P BB` | `M` |
| Click **+** three times on a stepper | `M P BB BB BB` | `M M` |

## Rule 3: a redundant terminator loses its M

A terminator that immediately follows another terminator for the same unit
(a command terminator right after its argument's terminator) is redundant, so
delete its M.

| GUI step | ops | why |
|---|---|---|
| Rename inline, **Enter** commits the name | `M K` | Rule 4 (variable string) |
| Then click **Done** that only closes edit mode | `P BB` | redundant terminator, no M |

## Rule 4: a terminating K keeps its M only after a variable string

If a K terminates a **variable** string (an argument the user composed), it
**keeps** its M, giving `M K`. If it terminates a **constant** string (a
command name typed from memory), delete the M.

| GUI step | ops |
|---|---|
| Chat: type a request (28 chars), **Enter** to send | `H 28K` then `M K` |
| Command palette: type `/new`, **Enter** | `H 4K` then `K` (constant string) |
| Search: type a company name, **Enter** | `H nK` then `M K` |

---

## "Read a value" M

Add an M **only where a value must be read and held**: reading a price to
type it elsewhere, reading a ticker from the result list to confirm the
match, or reading a date to compare it. Record the held item in `chunks`
(Cogulator working memory). Merely looking at the screen is **not** an M.

| GUI step | ops | chunks |
|---|---|---|
| Read the current price in the header | `M` | `[price]` |
| Click into **Limit** and type it (7 chars) | `P BB` / `H 7K` | |

## No M for visual search (expert assumption)

KLM assumes an expert who knows where things are. Finding an item in a long
result list, a dense table, or an icon-only toolbar costs time that **no M
covers**. Don't add an M to "fix" that. Log it as **density debt** in
`references/goms-debt.md` and turn it into a moderator question. The
session measures it: (observed − R) − predicted.

## Physical conventions

- **H** on **every** mouse↔keyboard switch, both directions. Track where
  the hands are; a method that starts by typing starts with H.
- **Drag** = `P B P B` (point at the source, press, point at the target,
  release). Add an M in front if choosing the drag is a decision.
- **Ctrl / Shift / Alt modifier** = 1 K (Ctrl-click = `K P BB`).
- **Double-click** = `BBBB`, **triple-click** = `BBBBBB`.
- **Free-text length is an explicit assumption.** Put the character count in
  the label ("Type the request (28 chars)") and its source in `note`
  (pilot median, task script, or guess). Runs of ≥ 20 K are free text:
  klm.py reports every method with and without them.
- **Scroll (S)** isn't standard KLM. Use it only where the target is below
  the fold at the fixed viewport, and record the distance in `note`.
- **R** (system/LLM response) is written into `ops_low` for the record but
  always excluded from the total. Measure it and subtract it from observed
  times.
- A step that exists only sometimes (a dialog that opens on the last-used
  tab, a first-time tooltip) goes in `ops_extra` with an empty `ops_low`.
