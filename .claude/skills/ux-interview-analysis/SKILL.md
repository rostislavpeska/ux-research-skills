---
name: ux-interview-analysis
description: Turn screen-recorded moderated usability sessions (e.g. Google Meet recordings in Google Drive) into client deliverables — a verbatim timestamped transcript, a session summary and an observed-session board where every client-surface second is covered and every claim is checked against video frames. Use for "transcribe the interview", "analyse the usability session", "observed walkthrough", usability-session evidence. Complements goms-testing (model vs observed).
---

# UX interview analysis

Every step ends in a **client deliverable**. Plumbing is n8n (no method inside), the method is this
skill (versioned prompts + schemas + pure scripts), the evidence store is NocoDB, deliverables land
in the interview's own Drive folder.

## Roles

- **The agent (Claude Code) = orchestrator and analyst.** All reasoning happens here: segmentation,
  what counts as a problem, severity, interpretation, GOMS predicted-vs-observed, synthesis.
- **Gemini via n8n = perception specialist.** Transcription, what is on screen and when, cursor and
  clicks, spoken scores. Its output is evidence to reason over, not conclusions.
- **Sources per interview:** transcript, video observations, the call chat (links + times ≈
  recording time), the session's boards, and the observer's notes when they exist.

## Languages

- **Documentation language** = `python scripts/doc_language.py <interviews.json> --study <ID>`:
  all interviews in one language → that language; several → **ask the user**; an explicit request
  ("report in English") → `--override en`.
- Everything fixed (titles, speaker labels, markers, headings, quote marks) comes from
  `locales/<lang>.yaml`; scripts take `--lang`. New language = new locale file (`locales/README.md`).
  Shipped: `cs`, `en`.
- **Quotes are evidence: never translated.** In a mixed-language study they may carry a gloss in the
  documentation language, marked as a translation.

## Hard rules

1. **No participant data in a repo.** Recording titles carry real names; use pseudonyms
   (`S1-U01`). Working files go to `out/` (gitignored).
2. **Never re-type evidence.** Text moves file → curl → n8n → NocoDB/Drive. The agent reads and
   judges; quotes are inserted by `render_quotes.py`, never typed.
3. **One controlled run, then check.** Never retry-loop a webhook on timeout; read the n8n execution.
4. **A success message is not success.** Verify the stored result (row counts, the Doc itself).
5. Prefer false negatives: an "inaudible" marker beats a guessed word; a claim not visible on a
   frame is dropped and logged as excluded.

## Plumbing (n8n, all guarded by an `x-api-key` header)

Import the five workflows from `n8n/workflows/` following `n8n/INSTALL.md`
(Docker, NocoDB tables, credentials, API key, smoke test). Never store the key in files of this skill; read it from
your n8n at run time (for example through an n8n MCP server: the "Check API Key" node).

| Webhook | Workflow | Does |
|---|---|---|
| `POST /webhook/ux-ingest` | Ingest | Drive recording → Gemini Files API (48 h) → `ux_interviews` row. Async → `{job_id}` |
| `POST /webhook/ux-gemini` | Gemini Call | Any Gemini `generateContent` body → `ux_runs` row (raw output, tokens, model version). Async |
| `POST /webhook/ux-rows` | Rows | `read`/`write` the `ux_*` tables only. **Max 100 rows per write** |
| `POST /webhook/ux-publish` | Publish Doc | Text → Google Doc in the interview's Drive folder (`interview_id`), or in any folder n8n can edit (`folder_id`, e.g. the study folder). Same title = update (Drive keeps revisions) |
| `POST /webhook/ux-fetch` | Fetch Recording | Streams an ingested recording to the agent's machine (frames are cut locally). Execution data not saved |

`B` = your n8n base URL, `K` = the key. Async jobs: check the n8n execution with the returned `job_id`.

## Before an interview can run (once per study / recording)

- Share the **study folder** (parent of the interview folders) with the Google account your n8n
  Drive credential uses, as **Editor**. Without it, publishes fail with Drive "File not found".
- On a Google Meet **recording** file: Share → ⚙ → tick **"Viewers and commenters can download"**
  (Meet recordings block downloads by default; error `cannotDownloadFile` means this is missing).

## Step 0 — Study brief (once per study; deliverable: Doc "Study brief – <STUDY>")

The harness is universal; the brief is the per-study instruction that decides what the reports
contain. Fill `templates/study-brief.md` from the research-phase materials (session script — see
`templates/session-script.md` — test plan, persona and rating materials); the session script wins
where sources disagree. Publish it to the study folder (`ux-publish` with `folder_id`).
Every later step reads it first: client surfaces (coverage), session blocks (board sections and
their order), expected answers (task success), metrics, moderation rules ("never say" list).

## Step 1 — Transcript (deliverable: Doc "<locale transcript title> – <ID>")

Run from this skill's directory.

1. **Ingest:** `curl -X POST $B/webhook/ux-ingest -H "x-api-key: $K" -d '{"interview_id":"S1-U02","study_id":"S1","participant_id":"U02","drive_file_id":"<recording id>"}'`
   → wait for the execution → read the row: `ux-rows {"op":"read","table":"ux_interviews","where":"(interview_id,eq,S1-U02)"}`
   → check `duration_s` and `drive_md5` match Drive.
2. **Transcribe** in 10-minute windows (last window ends at the duration):
   `python scripts/build_request.py --stage transcript --prompt prompts/transcript.v2.md --schema schemas/transcript.v2.json --interview S1-U02 --file-uri <gemini_file_uri> --start 0 --end 600 --model <gemini model> --lang <lang> --var glossary=@examples/demo/glossary.txt -o out/req.json`
   → `curl ... $B/webhook/ux-gemini --data-binary @out/req.json` (fire all windows; each returns a job id).
3. **Assemble + QA:** export runs `ux-rows {"op":"read","table":"ux_runs"} > out/runs.json`, then
   `python scripts/segments.py out/runs.json --interview S1-U02 --lang <lang> --duration <s> --rows-out out/rows.json --md-out out/t.md --docx-out out/t.docx --txt-out out/t.txt`
   → must print `0 QA flags`; then look at seams (10:00, 20:00 …), gaps > 25 s and an opening sample.
4. **Store:** write `out/rows.json` to `ux_transcript` **in chunks of 100**; verify the stored count
   equals the segment count and `segment_id`s are unique.
5. **Publish:** body `{"interview_id","title","text":<t.txt>}` built by script → `curl $B/webhook/ux-publish`
   → open the Doc and check the text is there.

## Step 2 — Session summary (deliverable: Doc "<locale summary title> – <ID>")

1. Read the whole transcript (`out/t.md`) and the call chat.
2. Write `out/<ID>_summary.draft.txt`: participant, persona fit, timeline, task outcomes, the spoken
   final assessment, ranked issues, what worked, says-vs-does, GOMS predicted vs observed. Cite every
   moment as `{{q:MM:SS}}` (`{{q:MM:SS@participant}}` when two segments share the second).
3. `python scripts/render_quotes.py out/<ID>_summary.draft.txt out/rows.json --lang <lang> -o out/<ID>_summary.txt`
   — fails on any missing or ambiguous quote; spot-check the filled quotes.
4. Publish and open the Doc.

## Step 3 — Observed session board (deliverable: whiteboard, whole session, GOMS format)

One column per session block from the brief, left to right in session order: **session overview**
(timeline plan vs actual, coverage, ranked issues, ⚠ confirmed / not / untested, metrics collected?,
script adherence, test-material problems, items for the client to verify) → interview & personas →
website → app onboarding → app first steps → each task → moderator detours → closing & rating.
Each column = Summary section (title, context, coloured cards) + Walkthrough section (one card per
step: screenshot with markers · status OK / Borderline / Problem / Info · what happened · verbatim
quote · time vs GOMS · "Why"/"Interpretation" lines).

1. **Sources from the interview folder:** call chat → board links (persona board, GOMS board, rating
   card), app URL, test data; plus observer notes. Read board texts through your whiteboard's MCP —
   persona fit needs the card wording. Better: keep the canonical text of participant materials in
   the study brief, so no step depends on one whiteboard vendor.
2. **Local video**: `curl $B/webhook/ux-fetch -d '{"interview_id":…}' -o out/<ID>.mp4` → md5 must
   equal `ux_interviews.drive_md5`.
3. **Screen timeline (Gemini)** for the whole recording: `prompts/timeline.v1.md` +
   `schemas/timeline.v1.json`, `--fps 0.5 --media-resolution MEDIA_RESOLUTION_LOW`, ~20-min windows,
   `--var "client_surfaces=<from the brief>"`. Check every boundary on frames (contact sheet); the
   `address` field is unreliable OCR — use the frame.
4. **Session map**: `out/session_map_<ID>.json` — blocks (start/end, type, board section) +
   frame-verified corrections. **Coverage gate**:
   `python scripts/coverage.py out/timeline_runs_<ID>.json out/session_map_<ID>.json` must exit 0
   (every client-surface second in a reported block) before the board is built.
5. **Perception (Gemini)**: per block window with a client surface, `prompts/observe.v1.md` +
   `schemas/observe.v1.json`, `--fps 2 --media-resolution MEDIA_RESOLUTION_HIGH`, transcript excerpt
   (`scripts/excerpt.py`) for timing only. GOMS predictions are NOT sent (no confirmation bias).
   `scripts/obs_print.py` prints the runs compactly.
6. **Verification (the agent)**: cut frames at every claimed moment and LOOK at them (zoom for
   tooltip text). Fix wrong timestamps, drop claims not visible on screen (log them as "excluded").
   Gemini MM:SS can be off by up to a minute.
7. **Screenshots**: `scripts/frames.py out/<ID>.mp4 steps.json --outdir … --crop x0,y0,x1,y1` —
   crop to the shared screen so webcam tiles (faces, names) never reach a deliverable; tighter crop
   for whiteboard frames (viewer avatars); place boxes from a gridded frame; check every marker on a
   contact sheet.
8. **Rating card**: when the card stays unfilled and scores are spoken, extract them from the audio
   with `prompts/rating.v1.md` + `schemas/rating.v1.json` (`--var statements=@<card statements>`,
   rating window only) and compare with the transcript — only scores where both agree go on the
   board; any disagreement is reported, not resolved by guessing.
9. **Board text**: `out/board_<ID>.draft.txt` (format in `scripts/board_draft.py`) with `{{q:MM:SS}}`
   → `render_quotes.py` → `board_draft.py` → `out/board_<ID>.json`. Task outcome against the brief's
   expected answers; script adherence (★ asked / not, never-say words) and test-material problems
   kept apart from product findings.
10. **Render**: the board JSON is the canonical, tool-agnostic deliverable; a renderer draws it.
   Shipped: FigJam via the Figma MCP (`renderers/figjam/`): one `use_figma` call per column
   (`python scripts/figjam_code.py`), which returns slot ids + FNV-1a hashes → upload screenshots
   into the slots (`upload_assets` with nodeIds) →
   `python scripts/board_hashcheck.py out/board_<ID>.json out/board_<ID>_hashes.json` must report
   0 problems, and every slot must hold an image.
11. Link the board from the session summary Doc and republish it.

**Observer notes:** a plain notepad with an automatic timestamp per line (we use Obsidian + the free
"Time Bullet" plugin: format `HH:mm:ss`, **Use UTC off**); first line `▶ recording started` at
recording start; one `.md` per session uploaded to the interview folder. Guides:
`templates/observer-notes-guide.en.md`, `templates/observer-notes-guide.cs.md`.

**Participant-input materials** (rating card, exercises) must be editable **without an account** —
test the participant link in a private window before every session.

## Data (NocoDB)

`ux_interviews`, `ux_runs` (append-only), `ux_transcript` — columns in `n8n/README.md`.

## Files

| Path | Use |
|---|---|
| `prompts/transcript.v2.md` + `schemas/transcript.v2.json` | verbatim transcript, language-neutral (locale variables) |
| `prompts/transcript.v1.md` + `schemas/transcript.v1.json` | first, Czech-only version (kept for reproducibility) |
| `prompts/timeline.v1.md` + `schemas/timeline.v1.json` | whole-recording screen timeline (surface per interval) |
| `prompts/observe.v1.md` + `schemas/observe.v1.json` | step-by-step on-screen observation per block |
| `prompts/rating.v1.md` + `schemas/rating.v1.json` | spoken scores per rating-card statement (cross-check of the transcript) |
| `locales/*.yaml` | all fixed strings per documentation language |
| `examples/demo/glossary.txt` | spelling help only (product terms, never participant data) |
| `examples/railo/` | FICTIONAL end-to-end demo (README): session + GOMS board drafts, transcript rows with `text_en`, screen timeline + session map for `coverage.py` |
| `templates/study-brief.md` | per-study brief (Step 0) |
| `templates/session-script.md` | session script skeleton (blocks, ★/○ questions, ⚠ critical points, expected answers) |
| `templates/observer-notes-guide.{en,cs}.md` | setup + rules for the observer's timestamped notes |
| `scripts/build_request.py` | prompt + schema + clip window → webhook body (pure) |
| `scripts/segments.py` | runs → rows + Markdown + .docx + .txt, with QA flags (pure) |
| `scripts/doc_language.py` | documentation-language rule (pure) |
| `scripts/excerpt.py` | transcript rows → excerpt for a time window (pure) |
| `scripts/coverage.py` | timeline + session map → client-surface coverage gate (pure) |
| `scripts/obs_print.py` | observe runs → compact step list (pure) |
| `scripts/frames.py` | annotated, cropped screenshots from the local recording |
| `scripts/render_quotes.py` | `{{q:MM:SS}}` → verbatim quote with locale quote marks; `--translation text_en` adds the row's translation under each quote |
| `scripts/board_draft.py` | rendered board draft → board JSON (pure) |
| `scripts/figjam_code.py` | board JSON column → `use_figma` code for the FigJam renderer (pure) |
| `scripts/board_hashcheck.py` | board JSON vs hashes returned by the renderer (pure) |
