# FigJam renderer

Draws the board JSON (`scripts/board_draft.py` output) as a FigJam board through the Figma MCP
(`use_figma`, `upload_assets`). The board JSON is the deliverable; this renderer is one way to show it.

## Use

1. Create or open a FigJam file you can edit through the Figma MCP.
2. For each column, left to right in session order:
   `python scripts/figjam_code.py out/board_<ID>.json --column <id> --index <n>`
   → pass the printed code to `use_figma` (one call per column; the code must stay under 50 000 chars).
3. Each call returns `slots` (screenshot rectangle id per step key) and `hashes` (FNV-1a per text).
   Merge all `hashes` into `out/board_<ID>_hashes.json`.
4. Upload screenshots: `upload_assets` with `nodeIds` = the slot ids, then POST each PNG
   (`frames.py` output) to its upload URL.
5. `python scripts/board_hashcheck.py out/board_<ID>.json out/board_<ID>_hashes.json`
   must report `problems: 0`, and every slot must hold an image (check with a read-only `use_figma`).

## Layout

Columns are 1648 px wide with 200 px gaps (`--stride 1848`). Each column has a Summary section on
top and, when it has steps, a Walkthrough section below it. Step status pills: OK (green),
Borderline / Hraniční (orange), Problem / Problém (red), Info (grey).

## Limits

- **FigJam only.** Another whiteboard (Miro, tldraw, …) needs its own renderer reading the same
  board JSON. None ships here.
- **Text is passed inside the tool call**, so the hash check is mandatory: it is what proves the
  board text equals the rendered draft (quotes included).
- **Changes after the first render** (reordering columns, moving steps between columns, extra
  visual cards such as a filled rating card) were done with one-off `use_figma` scripts in our runs;
  they are not packaged. Re-render a column, or write a targeted script and re-run the hash check.
- Participants should not be asked to fill anything in FigJam: viewers without a Figma login cannot
  edit a board shared by link.
