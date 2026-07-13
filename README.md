# RAG Document Q&A

Upload a PDF, DOCX, or Markdown file and ask questions about it. Every answer
comes only from your documents and shows which file, page, and chunk it used. If
the answer isn't in your files, it says so instead of making something up.

I built this to be more than an API wrapper. It has an evaluation harness for
comparing chunking strategies, per-IP and global rate limits, a daily spend cap,
structured logging, and error handling for the cases that usually get skipped.

**Stack:** FastAPI, LlamaIndex, ChromaDB, OpenAI (`gpt-4.1-mini` and
`text-embedding-3-large`), Upstash Redis, Next.js + TypeScript + Tailwind,
Docker, Railway.

---

## Table of contents

- [Architecture](#architecture)
- [Features](#features)
- [Repo structure](#repo-structure)
- [Environment variables](#environment-variables)
- [Run locally](#run-locally)
- [Run the eval harness](#run-the-eval-harness)
- [Eval results across chunking configs](#eval-results-across-chunking-configs)
- [Deploy to Railway](#deploy-to-railway)
- [Notes and limitations](#notes-and-limitations)

---

## Architecture

```
                     ┌──────────────────────────┐
  Next.js UI ──────► │  FastAPI backend         │
  (chat + upload)    │                          │
        ▲            │  parsers ─► chunker ─►    │
        │  SSE       │  OpenAI embeddings ─►     │
        └──────────  │  ChromaDB (persistent)    │
                     │        │                  │
   per-IP + global   │        ▼                  │
   rate limit ◄──────┤  retrieve top-k ─► LLM    │
   (Upstash Redis)   │  (context-only) ─► SSE    │
                     └──────────────────────────┘
```

- **Ingestion:** each file type has its own parser that pulls out the text and
  keeps metadata with it (page number for PDFs, section heading for DOCX and
  Markdown). The text is split into chunks with a configurable size and overlap,
  and every chunk carries that metadata.
- **Retrieval:** top-k vector search over ChromaDB. The prompt tells the model to
  answer only from the retrieved chunks, and to return a fixed "not found" line
  when the answer isn't there.
- **Streaming:** answers stream to the browser over SSE. The first message carries
  the citations so sources show up right away, and the last one carries latency
  and token counts.

## Features

**RAG**
- Upload multiple PDF, DOCX, or Markdown files at once.
- Chunk size, overlap, and top-k are configurable, so the eval can vary them.
- Each chunk keeps its source filename, page (PDF), and section heading (DOCX/MD).
- Every answer comes with citations you can expand to see the exact chunk text.
- Says "not found" when nothing relevant comes back.
- Streamed responses.

**Production concerns**
- Per-IP query limit as a permanent lifetime cap (10 queries per IP by default,
  no reset) via Upstash Redis, with an in-memory fallback for local dev. Uploads
  have a separate hourly limit.
- A hard daily cap on total LLM calls so the demo can't run up a bill, separate
  from the per-IP limit.
- `max_tokens` is capped on responses.
- One structured JSON log line per query with latency, chunks retrieved, and
  token usage.
- Handles unparseable files, oversized uploads, empty retrievals, and OpenAI
  failures without crashing.

**Eval harness** (below): retrieval hit rate plus an LLM-as-judge accuracy check
across a grid of chunking configs, with a comparison table.

**Frontend**
- Drag-and-drop upload with per-file status (queued, parsing, indexed, error) and
  chunk counts.
- Document list with delete and re-index.
- Chat thread with streamed answers and expandable citations.
- Latency and chunk count shown quietly under each answer.
- On a rate-limit hit you get a clear message; remaining quota sits in the header.
- Sample documents are pre-loaded and there are example questions to click.
  Works on mobile.

## Repo structure

```
rag-demo/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI routes, SSE query, rate limiting
│   │   ├── config.py          # typed settings from env
│   │   ├── models.py          # pydantic schemas
│   │   ├── seed.py            # pre-load sample docs on boot
│   │   ├── rag/
│   │   │   ├── parsers.py     # PDF / DOCX / MD parsers + metadata
│   │   │   ├── index.py       # ChromaDB + LlamaIndex ingest/list/delete
│   │   │   └── query.py       # retrieval + streaming answers
│   │   ├── services/
│   │   │   ├── rate_limit.py  # Upstash + in-memory fallback
│   │   │   └── logging_conf.py# structured JSON logging
│   │   └── eval/
│   │       ├── run_eval.py    # eval harness
│   │       └── eval_set.json  # 25 Q/A pairs
│   ├── samples/               # 3 pre-loaded documents
│   ├── requirements.txt
│   ├── Dockerfile
│   └── railway.json
├── frontend/                  # Next.js + TS + Tailwind
│   ├── app, components, lib
│   ├── Dockerfile
│   └── railway.json
├── docker-compose.yml         # local full-stack
└── README.md
```

## Environment variables

Backend (`backend/.env`, see `backend/.env.example`):

| Variable | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` | — | Required. |
| `LLM_MODEL` | `gpt-4.1-mini` | Generation model. |
| `EMBED_MODEL` | `text-embedding-3-large` | Embedding model. |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `512` / `64` | Chunking defaults. |
| `TOP_K` | `5` | Retrieved chunks per query. |
| `MAX_TOKENS` | `512` | Response cap. |
| `UPSTASH_REDIS_REST_URL` / `_TOKEN` | — | Blank means in-memory fallback. |
| `PER_IP_QUERY_LIMIT` | `10` | Permanent lifetime query cap per IP (no reset). |
| `PER_IP_UPLOAD_HOURLY_LIMIT` | `20` | Uploads per IP per hour. |
| `GLOBAL_DAILY_LLM_CAP` | `500` | Daily ceiling on LLM calls. |
| `MAX_UPLOAD_MB` | `20` | Per-file upload cap. |
| `CORS_ORIGINS` | `*` | Comma-separated, or `*`. |

Frontend (`frontend/.env`, see `frontend/.env.example`):

| Variable | Notes |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL (e.g. `http://localhost:8000`). |
| `NEXT_PUBLIC_GITHUB_URL` | Link shown in the header. |

## Run locally

You only need an `OPENAI_API_KEY`. Upstash is optional locally (it falls back to
an in-memory limiter), and ChromaDB is embedded, so there's no database to set up.

**Backend**

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env            # then set OPENAI_API_KEY
uvicorn app.main:app --reload   # http://localhost:8000  (docs at /docs)
```

The three sample documents get indexed on first boot, so you can ask questions
right away.

**Frontend**

```bash
cd frontend
npm install
cp .env.example .env            # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                     # http://localhost:3000
```

**Whole stack with Docker**

```bash
cp backend/.env.example backend/.env   # set OPENAI_API_KEY
docker compose up --build              # frontend :3000, backend :8000
```

**Tests**

```bash
cd backend
pip install -r requirements-dev.txt
pytest                      # parser + rate-limiter unit tests, no API key needed
```

## Run the eval harness

This is the part I'd point a reviewer at first. It rebuilds the index for each
chunking config, then scores retrieval and answer quality on a fixed 25-question
set against the sample documents.

```bash
cd backend
# Default sweep: chunk sizes {256, 512, 1024} x overlap {64} x top_k {3, 5}
python -m app.eval.run_eval

# Custom grid:
python -m app.eval.run_eval --chunk-sizes 256 512 1024 --overlaps 0 64 128 --top-k 3 5 --json results.json
```

What it reports per config:
- **Retrieval hit rate:** did a chunk from the right source containing an expected
  keyword show up in the top-k?
- **Answer accuracy:** an LLM-as-judge YES/NO check of the generated answer against
  the reference answer.
- **Average latency:** wall-clock per query.

## Eval results across chunking configs

> Output from `python -m app.eval.run_eval` (25 questions across 6 configs). Exact
> numbers move around with model version and API latency, so regenerate them with
> the command above.

| chunk | overlap | top_k | hit_rate | answer_acc | latency(ms) |
|-------|---------|-------|----------|-----------|-------------|
| 256   | 64      | 3     | 100.0%   | 96.0%     | 3265        |
| 512   | 64      | 3     | 100.0%   | 96.0%     | 2840        |
| 512   | 64      | 5     | 100.0%   | 96.0%     | 2331        |
| 1024  | 64      | 3     | 100.0%   | 96.0%     | 1893        |
| 1024  | 64      | 5     | 100.0%   | 96.0%     | 2048        |
| 256   | 64      | 5     | 100.0%   | 92.0%     | 2944        |

On this small, curated corpus retrieval saturates: every config lands the right
chunk in the top-k (100% hit rate), so search isn't the bottleneck here. Answer
accuracy holds at 96% across configs, with the one dip at 256-token chunks and
`top_k=5`, where more, smaller fragments hand the model noisier context. The app
ships `512 / top_k=5` — top accuracy with latency in the better half of the range.
On a larger corpus the configs would start to separate on hit rate; the harness
exists to catch exactly that.

## Deploy to Railway

Two services from one repo, each with its own `Dockerfile` and `railway.json`.

1. **Backend service**, root directory `backend/`.
   - Set the env vars from the table above (at least `OPENAI_API_KEY`; add the
     Upstash vars so the rate limits survive restarts and hold across replicas).
   - Attach a volume mounted at `/app/storage` so ChromaDB and uploads persist
     across deploys.
   - The `/api/health` health check is already configured.
2. **Frontend service**, root directory `frontend/`.
   - Set `NEXT_PUBLIC_API_URL` to the backend's public URL (it's a build-time arg).
3. Point `CORS_ORIGINS` on the backend at the frontend's domain.

## Notes and limitations

- The in-memory rate limiter is for local dev only. It resets on restart and is
  per-process, so use Upstash in production for the caps to actually hold.
- ChromaDB is embedded and persistent, which is fine for a demo on one instance.
  For horizontal scale, swap in a hosted vector store. `ChromaVectorStore` in
  `rag/index.py` is the only place that changes.
- There's no auth or user accounts. It's a public demo, and the daily cap is what
  keeps costs bounded.
- Answer accuracy is judged by an LLM, so it carries some judge noise. Treat it as
  a way to compare configs against each other, not as ground truth.
