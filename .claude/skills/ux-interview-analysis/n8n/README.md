# n8n plumbing

Five webhook workflows. They carry **no method** — prompts, schemas and judgement live in the skill;
n8n only moves files, calls Gemini and stores rows. The templates in `workflows/` are our live
workflows (state of 2026-10-05) passed through `sanitize.py`: credentials, account data, ids and the
API key removed — nodes, connections and code otherwise unchanged.

| Template | Webhook | Credentials to select after import |
|---|---|---|
| `ingest.json` | `POST /webhook/ux-ingest` | Google Drive OAuth2, Google Gemini (PaLM) API, NocoDB |
| `gemini-call.json` | `POST /webhook/ux-gemini` | Google Gemini (PaLM) API, NocoDB |
| `rows.json` | `POST /webhook/ux-rows` | NocoDB |
| `publish-doc.json` | `POST /webhook/ux-publish` | Google Drive OAuth2, NocoDB |
| `fetch-recording.json` | `POST /webhook/ux-fetch` | Google Drive OAuth2, NocoDB |

## Setup

Step by step from zero — Docker, NocoDB tables, credentials, placeholders, import, smoke test,
troubleshooting: **[INSTALL.md](INSTALL.md)**.

Two things to know before you read it:
- **Async calls:** Ingest and Gemini Call answer at once with `{"job_id": <n8n execution id>}` and
  keep working; read the result from that execution (its last node) or from the `ux_*` row it
  writes. Rows, Publish Doc and Fetch Recording answer synchronously.
- **Auth:** every webhook checks one static key in an `x-api-key` header (IF node, our house
  pattern). n8n's built-in **Header Auth** on the Webhook node is the cleaner choice — swap it in if
  you prefer and delete the IF node.

## NocoDB tables

`ux_interviews` — one row per recording (ingest upserts by `interview_id`)

| Column | Type | Note |
|---|---|---|
| `interview_id` | SingleLineText | pseudonym, e.g. `S1-U01` |
| `study_id` | SingleLineText | |
| `participant_id` | SingleLineText | |
| `drive_file_id` | SingleLineText | the recording in Drive |
| `drive_md5` | SingleLineText | checked against the local copy |
| `duration_s` | Decimal | |
| `gemini_file_uri` | SingleLineText | Gemini Files API URI (expires after 48 h) |
| `gemini_file_expires_at` | DateTime | `YYYY-MM-DD HH:MM:SS` |
| `status` | SingleLineText | |
| `notes` | LongText | |
| `language` | SingleLineText | ISO code detected in the transcript |

`ux_runs` — append-only, one row per Gemini call

| Column | Type | Note |
|---|---|---|
| `run_id` | SingleLineText | `<interview>-<stage>-<execution id>` |
| `interview_id`, `stage`, `model`, `model_version`, `prompt_version`, `status` | SingleLineText | status: ok / truncated / parse_error / error / finish_* |
| `params_json` | LongText | request with prompt text and schema redacted (they are versioned files) |
| `output_json` | LongText | model output, byte-exact |
| `tokens_in`, `tokens_out` | Number | `tokens_out` includes thinking tokens |

`ux_transcript` — one row per transcript segment

| Column | Type | Note |
|---|---|---|
| `segment_id` | SingleLineText | `<interview>-T0001` … |
| `interview_id`, `run_id`, `speaker` | SingleLineText | speaker: moderator / participant / observer / unclear |
| `t_start_s`, `t_end_s` | Decimal | full-recording seconds |
| `text_cs` | LongText | the segment text **in any language** — the name is historical (first study was Czech) |

## Limits (honest)

- Built and run on one self-hosted n8n with NocoDB; not tested on n8n Cloud or other databases.
- The Rows workflow writes at most **100 rows per call** — NocoDB bulk inserts above that failed
  silently for us, so the cap is enforced and every written row is counted.
- The NocoDB node (v3) shows a validator warning for plain-string workspace/base ids; it works.
- The Gemini upload uses n8n's Google Gemini node; its available node version depends on your n8n
  version — if the imported node shows as unknown, re-add "Upload a file" from the palette.
- Gemini Files API: max 2 GB per file, files deleted after 48 h — re-ingest after that.
