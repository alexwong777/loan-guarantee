# Letter of Guarantee Studio

A small, self-contained web app for two workflows:

1. **Letter of Guarantee comparison** — upload the client's letter and Mizuho's
   letter, OCR both with GLM-OCR, and see a word-level diff with a match
   percentage. Anything only in one letter is highlighted so it's easy to spot
   where the Mizuho letter deviates from the client's original wording.
2. **KYC document extraction** — upload a passport, ID card, or company
   registration document and get structured fields back (name, ID number,
   address, dates, company/registration numbers, etc.) alongside the raw OCR
   text.

Everything runs in Docker. The only thing that runs outside Docker is Ollama
itself (already running on your Mac with the `glm-ocr` model, per your setup).

## Architecture

```
frontend (React + Vite, served by nginx)  →  backend (FastAPI)  →  Ollama /api/chat (GLM-OCR)
        :3000                                      :8000                  :11434 (host)
```

- `backend/` — FastAPI service that converts uploaded PDFs/images to page
  images, sends each page to GLM-OCR, diffs the two letters, and extracts KYC
  fields.
- `frontend/` — React UI, built and served via nginx, which reverse-proxies
  `/api/*` to the backend container.

## Running it

```bash
git clone https://github.com/alexwong777/loan-guarantee.git
cd loan-guarantee
cp .env.example .env   # adjust OLLAMA_URL / OCR_MODEL if needed
docker compose up --build
```

Then open **http://localhost:3000**.

Make sure Ollama is running on your host with the GLM-OCR model available:

```bash
ollama list          # confirm "glm-ocr" (or whatever OCR_MODEL is set to) is present
ollama serve         # if it isn't already running
```

On Docker Desktop for Mac, `host.docker.internal` already resolves to your
host machine, so the backend can reach `http://localhost:11434` on your Mac
as `http://host.docker.internal:11434` with no extra setup.

## About the OCR fix

Your original `ocr_pdf.py` posted to Ollama's **OpenAI-compatible** endpoint
(`/v1/chat/completions`) with an `"options": {"num_ctx": 8192}` field. That
endpoint doesn't honor Ollama's `options` block — it's specific to Ollama's
native API. So every page was actually running with Ollama's small default
context window. A page image alone can consume most of a small context
window, leaving almost no budget left for output tokens, which is exactly why
generation stopped after the first line of each page.

The backend here (`backend/app/ocr.py`) instead calls Ollama's **native**
`/api/chat` endpoint, where `options.num_ctx` and `options.num_predict` are
respected, and passes the page image via the native `images` field on the
message rather than an OpenAI-style `image_url` block. `OCR_NUM_CTX` (default
`8192`) and `OCR_NUM_PREDICT` (default `4096`) are both configurable via
environment variables in `.env` if you still see pages getting cut short —
try raising them further for dense, multi-page documents.

## API

Both flows are job-based so the frontend can poll for live per-page progress
instead of blocking on one long request with no feedback:

- `GET /api/health`
- `POST /api/compare/start` — multipart form fields `client_file`, `mizuho_file` → `{job_id}`
- `POST /api/extract-kyc/start` — multipart form field `file` → `{job_id}`
- `GET /api/jobs/{job_id}` — `{status, elapsed_seconds, tracks, result, error}`,
  where `status` is `running` / `done` / `error` / `cancelled`
- `POST /api/jobs/{job_id}/stop` — requests cancellation; the job stops before
  starting its next page

Accepted file types: PDF, PNG, JPG/JPEG, WEBP, TIFF, BMP.

## Debugging / logs

The backend writes every OCR request (target URL, timing, response size or
error) to `backend/logs/backend.log` on your machine — that folder is
volume-mounted into the container, so it updates live while the app runs:

```bash
tail -f backend/logs/backend.log
```

The same lines also show up with `docker compose logs -f backend`.

If a Compare/Extract click just spins with no result, this is the first
place to look — a page can legitimately take a couple of minutes on CPU
inference, especially the first request after starting Ollama (it has to
load the model into memory). The UI itself will show an error after 15
minutes of no response rather than spinning forever.

## Editing `.env`

`.env` isn't committed (it's git-ignored) — it's created locally from
`.env.example` and read by `docker-compose.yml`. To change a setting:

```bash
nano .env      # or any editor — change OLLAMA_URL, OCR_MODEL, etc.
docker compose up -d --build
```

`docker compose up` picks up `.env` changes automatically and recreates any
container whose config changed.

## Local frontend dev (optional)

If you want hot-reload while tweaking the UI, without rebuilding the Docker
image each time:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# in another terminal
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000` automatically.
