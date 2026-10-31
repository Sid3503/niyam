# Deploy Niyam on Render

One Docker web service serves the API and the web console on the same host. A Render Postgres holds the data.

**Current Blueprint is the free tier:** web `plan: free`, Postgres `plan: free`, no disk. The service sleeps after ~15 minutes idle (open the URL to wake it). Stored PDFs/audio live on the instance disk and vanish on sleep/redeploy — re-run `tools/seed_demo.py` after a wake if previews 404. Free Postgres expires after 30 days.

Region is chosen at creation and cannot be changed. Default is Oregon. Singapore is usually closer if you are in India.

## 1. Create fresh keys

Keys that appeared in an earlier chat are burned. Create new ones **before** you paste anything into Render.

- **Niyam API key** (locks the demo; visitors paste it in Settings): a long random string, for example `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
- **Sarvam** (`SARVAM_API_KEY`): speech-to-text, and the language model if Ollama is unset. [Sarvam dashboard](https://dashboard.sarvam.ai/)
- **Ollama** (`OLLAMA_API_KEY`): preferred language model when set (faster in our benchmark). Optional if Sarvam is set.

Keep them out of git. `infra/.env` is already gitignored.

## 2. Push this repo to GitHub

The Blueprint and Dockerfile live at the repo root (`render.yaml`, `Dockerfile`). Commit and push to `Sid3503/niyam` (or a fork):

```bash
git add Dockerfile .dockerignore render.yaml docs/RENDER.md \
  apps/api/docker-entrypoint.sh apps/api/niyam/config.py apps/api/niyam/main.py \
  apps/api/tests/test_config.py apps/api/tests/test_console.py \
  infra/docker-compose.yml tools/seed_demo.py README.md
git status   # confirm no .env or keys
git commit -m "Add Render one-service deploy (console + API, persistent disk)."
git push origin HEAD
```

Render builds from git, so only **tracked** files go in the image (the cited regulation subset, rule cards, and the demo library). Untracked PDFs on your laptop stay off the image.

## 3. Create the Blueprint on Render

1. Log in at [dashboard.render.com](https://dashboard.render.com/).
2. **New > Blueprint**.
3. Connect the `Sid3503/niyam` GitHub repo (grant access if Render has not seen it yet).
4. Render reads `render.yaml`. Apply it.
5. When prompted (`sync: false` variables), paste:
   - `NIYAM_API_KEY` — the new Niyam key from step 1
   - `SARVAM_API_KEY` — new Sarvam key (needed for voice notes)
   - `OLLAMA_API_KEY` — new Ollama key, or leave empty to use Sarvam for text
6. Wait for the first deploy. The first build compiles the web console and installs Python deps; several minutes is normal.

The service starts as `https://niyam-XXXX.onrender.com` (name `niyam` plus a suffix if that name is taken). You can attach a custom domain later.

## 4. Confirm the API is up and the knowledge base has loaded

The process migrates the database, then ingests the cited regulations in the background (`NIYAM_INGEST_ON_START=true`).

```bash
curl -sS https://YOUR-SERVICE.onrender.com/healthz
# {"ok": true}

curl -sS https://YOUR-SERVICE.onrender.com/readyz
# {"ok": true, "documents": N}   wait until N > 0
```

If `documents` stays `0`, open the service logs in Render and look for the ingest JSON. The console at `/` should already load; API calls need the key (next step).

## 5. Seed the sales demo (once)

From this laptop, against the deployed URL:

```bash
export NIYAM_API=https://YOUR-SERVICE.onrender.com
export NIYAM_API_KEY='the-same-key-you-pasted-in-Render'
python3 tools/seed_demo.py
```

This talks to the public API only (no `docker exec`). It drafts rules from the Payment Aggregators circular, scans the library, commits one PDF wording, sends a few fixes for approval, and checks two synthetic voice notes. It needs a language-model key for drafted wording and `SARVAM_API_KEY` for voice.

Re-running it on a workspace that is already seeded will create duplicates. To start over, wipe the Postgres in the Render dashboard (or drop the data) and redeploy / re-seed. The disk still holds old blob files; they are content-addressed and harmless.

`tools/reset_demo.sh` is local-only (`docker exec`) and will not work on Render.

## 6. Open the console

1. Visit `https://YOUR-SERVICE.onrender.com/`
2. Go to **Settings**
3. Paste `NIYAM_API_KEY` (stored in that browser's `localStorage` as `niyam.apiKey`)
4. Set your name (sent as `X-Actor` on writes)
5. Open **Overview** and walk the library / approvals

Anyone with the URL **and** the API key can use the demo. There are no user accounts. Do not put real merchant data on this instance.

## What the image contains

| Path in the container | Source |
| --- | --- |
| `/app` | FastAPI app |
| `/app/console` | `apps/web` production build |
| `/data/rules` | rule cards + product facts |
| `/data/library` | synthetic demo documents and voice clips |
| `/data/regulations` | only the source files the cards cite (plus manifests) |
| `/data/var/blobs` | **persistent disk** — original PDFs and audio |

`WEB_CONCURRENCY=1` is required: PDF “Preview apply” is held in that one process’s memory.

## After you change code

Push to the connected branch. Render rebuilds the image and redeploys. The disk and the database stay. Ingest on start is idempotent (same sha256 is skipped).

## Honest limits

- One instance (a disk cannot scale horizontally).
- Redeploying without the disk would leave database rows pointing at missing files. The Blueprint attaches the disk; do not remove it.
- Production auth is a static API key. Fine for a synthetic demo.
- The knowledge base is the small cited subset, not the full corpus.
- AI-drafted fixes can take ~50 seconds on Sarvam. That is why this is a long-running service, not a serverless function.
