# Install the n8n plumbing — from zero to five working webhooks

About an hour the first time. At the end you have: n8n and NocoDB running, three NocoDB tables,
the five workflows imported and active, and a smoke test that proves they answer.

What we actually run: a self-hosted n8n 2.x and NocoDB on one small Linux VPS (2 vCPU, 8 GB RAM),
behind a reverse proxy with HTTPS. Not tested: n8n Cloud, other databases, Windows hosts.

## 0. You need

- A machine with **Docker**. A VPS for real studies; your laptop is fine for a first try.
- A **public HTTPS address** for n8n if the agent runs on another machine. For a laptop trial,
  `http://localhost:5678` works (Google OAuth accepts localhost redirects).
- The **Google account** that can open the recordings in Drive.
- A **Gemini API key** from [Google AI Studio](https://aistudio.google.com/apikey). Use a paid
  (billing-enabled) key for real participant data and read its data-use terms yourself.

## 1. Run n8n and NocoDB

A minimal `docker-compose.yml` to start from — **not our production file**; add HTTPS (Caddy,
Traefik, nginx) before you expose it, and change the host names:

```yaml
services:
  n8n:
    image: docker.n8n.io/n8nio/n8n
    restart: unless-stopped
    ports: ["5678:5678"]
    environment:
      - N8N_HOST=n8n.example.com            # or localhost
      - N8N_PROTOCOL=https                  # http for localhost
      - WEBHOOK_URL=https://n8n.example.com/
      - GENERIC_TIMEZONE=Europe/Prague
      - N8N_DEFAULT_BINARY_DATA_MODE=filesystem   # recordings are hundreds of MB — never keep them in memory
    volumes: ["n8n_data:/home/node/.n8n"]
  nocodb:
    image: nocodb/nocodb:latest
    restart: unless-stopped
    ports: ["8080:8080"]
    volumes: ["nocodb_data:/usr/app/data"]
volumes:
  n8n_data:
  nocodb_data:
```

```bash
docker compose up -d
```

Open n8n (port 5678) and NocoDB (port 8080) and create the owner accounts.

## 2. NocoDB: tables, ids, token

1. Create a base, e.g. `UX research`.
2. Create the three tables **`ux_interviews`, `ux_runs`, `ux_transcript`** with the columns listed
   in [README.md](README.md#nocodb-tables). Column names must match exactly — the workflows map
   fields by name. NocoDB adds its own `Id` column; keep it.
3. Note four kinds of ids: **workspace, base, and one id per table**. Open a table: the ids are in
   the browser URL (in recent NocoDB versions `…/#/<workspace>/<base>/<table>`) and in the table's
   API snippet.
4. Create an **API token** (account menu → Tokens). n8n uses it in step 4.

## 3. Fill in the placeholders — before importing

The templates contain `REPLACE_…` placeholders. Fill them in once, into an ignored folder, so you
never edit node by node:

```bash
cd .claude/skills/ux-interview-analysis
python -c "import secrets; print(secrets.token_urlsafe(32))"     # your webhook API key
python - <<'EOF'
import pathlib
values = {                                   # your values; this file is not saved anywhere
    "REPLACE_WITH_YOUR_API_KEY": "paste the key from above",
    "REPLACE_NOCODB_WORKSPACE_ID": "...",
    "REPLACE_NOCODB_BASE_ID": "...",
    "REPLACE_TABLE_ID_ux_interviews": "...",
    "REPLACE_TABLE_ID_ux_runs": "...",
    "REPLACE_TABLE_ID_ux_transcript": "...",
}
out = pathlib.Path("out/n8n-workflows"); out.mkdir(parents=True, exist_ok=True)
for p in pathlib.Path("n8n/workflows").glob("*.json"):
    s = p.read_text(encoding="utf-8")
    for k, v in values.items():
        s = s.replace(k, v)
    assert "REPLACE_" not in s, f"{p.name}: placeholder left"
    (out / p.name).write_text(s, encoding="utf-8")
    print("ready:", out / p.name)
EOF
```

`out/` is git-ignored: the filled files contain your key and ids — never commit them.

## 4. Credentials in n8n

n8n → **Credentials → Create**. Three are needed:

| Credential type | Fill in |
|---|---|
| **NocoDB API Token** | Host = your NocoDB URL as n8n sees it (`http://nocodb:8080` inside the compose network), token from step 2 |
| **Google Gemini(PaLM) API** | Host `https://generativelanguage.googleapis.com`, your API key |
| **Google Drive OAuth2 API** | Client ID + secret from Google Cloud (below), then *Sign in with Google* |

Google Drive OAuth client, once:
1. [Google Cloud Console](https://console.cloud.google.com/) → new project → *APIs & Services* →
   enable **Google Drive API**.
2. *OAuth consent screen*: user type External (or Internal in Workspace); add your account as a
   test user.
3. *Credentials → Create credentials → OAuth client ID → Web application*; as **Authorized redirect
   URI** paste the *OAuth Redirect URL* that n8n shows in the credential dialog.
4. Copy client ID and secret into n8n and sign in with the account that can open the recordings.

> While the consent screen is in **Testing**, Google expires the refresh token after 7 days and
> every Drive call fails until you sign in again. Publish the app (or use an Internal app) for
> anything longer than a trial.

## 5. Import, connect, activate

For each file in `out/n8n-workflows/`: n8n → **Workflows → Create → ⋯ → Import from file**. Open
every node with a warning triangle and select your credential:

| Workflow | Credentials |
|---|---|
| `ingest.json` | Google Drive OAuth2, Google Gemini, NocoDB |
| `gemini-call.json` | Google Gemini, NocoDB |
| `rows.json` | NocoDB |
| `publish-doc.json` | Google Drive OAuth2, NocoDB |
| `fetch-recording.json` | Google Drive OAuth2, NocoDB |

Save and **activate** (publish) all five. In n8n 2.x an edited workflow keeps serving its last
published version until you publish again — after every edit, re-publish.

## 6. Smoke test

```bash
B=https://n8n.example.com        # your n8n base URL
K=your-webhook-api-key

# 1) the guard works: no key → 401 {"error":"unauthorized"}
curl -s -X POST "$B/webhook/ux-rows" -H "Content-Type: application/json" -d '{"op":"read","table":"ux_interviews"}'

# 2) NocoDB is wired: → {"table":"ux_interviews","count":0,"rows":[]}
curl -s -X POST "$B/webhook/ux-rows" -H "x-api-key: $K" -H "Content-Type: application/json" \
  -d '{"op":"read","table":"ux_interviews"}'

# 3) Drive is wired: creates a Google Doc "ux-harness test" in a folder you own → {"status":"created","id":…,"url":…}
curl -s -X POST "$B/webhook/ux-publish" -H "x-api-key: $K" -H "Content-Type: application/json" \
  -d '{"folder_id":"<a Drive folder id>","title":"ux-harness test","text":"hello"}'

# 4) Gemini is wired: ingest one recording (any short test video in Drive) → {"job_id":"…"}
curl -s -X POST "$B/webhook/ux-ingest" -H "x-api-key: $K" -H "Content-Type: application/json" \
  -d '{"interview_id":"TEST-01","study_id":"TEST","participant_id":"P00","drive_file_id":"<Drive file id>"}'
```

Ingest is asynchronous: watch the execution in n8n (*Executions*); when it ends, the row appears
(`ux-rows` read with `"where":"(interview_id,eq,TEST-01)"`) with a `gemini_file_uri`. Then
`ux-fetch` with `{"interview_id":"TEST-01"}` streams the same video back (`-o test.mp4`). The Gemini
Call webhook is exercised by the skill itself (`scripts/build_request.py`, see `SKILL.md`). Delete
the test Doc and the `TEST-01` row afterwards.

## 7. Connect the skill

The skill needs only two things: the base URL `B` and the key `K`. Keep the key **out of the skill's
files**; read it at run time (for example from the "Check API Key" node through an n8n MCP server)
or from your own secret store.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `404` on a webhook | Workflow not active / not re-published after an edit, or you called `/webhook-test/…` |
| `401 unauthorized` with the key | The key differs between workflows, or a typo in the `x-api-key` header |
| Drive `File not found` | The Drive account is not **Editor** on the folder; Meet recordings also need "viewers can download" |
| Drive calls fail after a week | OAuth consent screen still in Testing (7-day refresh tokens) |
| "Upload to Gemini" node shows as unknown | Your n8n is older than the Gemini node version in the template — update n8n or re-add *Google Gemini → Upload a file* |
| n8n runs out of memory on ingest | `N8N_DEFAULT_BINARY_DATA_MODE=filesystem` is missing |
| Rows: `NocoDB stored X of Y rows` | A column name differs from the table spec, or more than 100 rows were sent |
| Gemini `403` / `429` | Key without billing, or quota — check AI Studio |
