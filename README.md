# RAG Document Q&A

A production-minded, retrieval-augmented document Q&A app. Upload PDF / DOCX /
Markdown, ask questions across everything indexed, and get **grounded answers
with visible citations** — every answer shows exactly which document, page or
section, and chunk it came from. When the answer isn't in the documents, the app
says so instead of bluffing.

Built to demonstrate real engineering, not just a wrapper around an LLM: a
first-class **evaluation harness**, per-IP and global **rate limiting**, a
hard **cost backstop**, **structured logging**, and graceful error handling.

**Stack:** FastAPI · LlamaIndex · ChromaDB · OpenAI (`gpt-4.1-mini` +
`text-embedding-3-large`) · Upstash Redis · Next.js + TypeScript + Tailwind ·
Docker / Railway.

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
- [Design notes & known limitations](#design-notes--known-limitations)

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
   (Upstash Redis)   │  (grounded prompt) ─► SSE │
                     └──────────────────────────┘
```

- **Ingestion:** each format has a dedicated parser that normalizes to text and
  preserves metadata — page number (PDF) or section heading (DOCX/MD). Text is
  chunked with configurable size/overlap; metadata propagates to every chunk.
- **Retrieval:** top-k vector search over ChromaDB. The LLM is prompted to answer
  *only* from retrieved context and to return a fixed "not found" line otherwise.
- **Streaming:** answers stream to the browser over SSE. The first frame carries
  citations so sources render immediately; the final frame carries latency and
  token usage.

## Features

**RAG**
- Multi-file upload: PDF, DOCX, Markdown.
- Configurable chunk size / overlap / top-k (not hardcoded — the eval varies them).
- Per-chunk metadata: source filename, page (PDF), section heading (DOCX/MD).
- Citations with every answer, expandable to the exact retrieved chunk text.
- Explicit "not found" when retrieval is empty or irrelevant.
- Streamed responses.

**Production concerns**
- Per-IP query limiting — a **permanent lifetime cap** (default 10 queries/IP,
  never resets) via Upstash Redis, with an in-memory fallback for local dev.
  Plus a separate hourly cap on uploads.
- Hard global daily cap on LLM calls as a cost backstop, independent of per-IP.
- Capped `max_tokens` on responses.
- Structured JSON logging per query: latency, chunks retrieved, token usage.
- Graceful handling of unparseable files, oversized uploads, empty retrievals,
  and OpenAI failures.

**Eval harness** (see below) — retrieval hit rate + LLM-as-judge answer accuracy
across a grid of chunking configs, with a comparison table.

**Frontend**
- Drag-and-drop multi-file upload with per-file status (queued → parsing →
  indexed → error) and chunk counts.
- Document list with delete + re-index.
- Chat thread with streamed answers and expandable citations.
- Retrieval latency + chunk count shown subtly under each answer.
- Rate-limit UX: clear message with time-to-reset; remaining quota shown in header.
- Pre-seeded sample documents + clickable example questions. Mobile-responsive.

## Repo structure

```
rag-demo/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI routes, SSE query, rate limiting
│   │   ├── config.py          # typed settings from env
│   │   ├── models.py          # pydantic schemas
│   │   ├── seed.py            # pre-seed sample docs on boot
│   │   ├── rag/
│   │   │   ├── parsers.py     # PDF / DOCX / MD parsers + metadata
│   │   │   ├── index.py       # ChromaDB + LlamaIndex ingest/list/delete
│   │   │   └── query.py       # retrieval + grounded streaming
│   │   ├── services/
│   │   │   ├── rate_limit.py  # Upstash + in-memory fallback
│   │   │   └── logging_conf.py# structured JSON logging
│   │   └── eval/
│   │       ├── run_eval.py    # eval harness
│   │       └── eval_set.json  # 25 Q/A pairs
│   ├── samples/               # 3 pre-seeded documents
│   ├── requirements.txt
│   ├── Dockerfile
│   └── railway.json
├── frontend/                  # Next.js + TS + Tailwind
│   ├── app/ · components/ · lib/
│   ├── Dockerfile
│   └── railway.json
├── docker-compose.yml         # local full-stack
└── README.md
```

## Environment variables

Backend (`backend/.env`, see `backend/.env.example`):

| Variable | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` | — | **Required.** |
| `LLM_MODEL` | `gpt-4.1-mini` | Generation model. |
| `EMBED_MODEL` | `text-embedding-3-large` | Embedding model. |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `512` / `64` | Chunking defaults. |
| `TOP_K` | `5` | Retrieved chunks per query. |
| `MAX_TOKENS` | `512` | Response cap. |
| `UPSTASH_REDIS_REST_URL` / `_TOKEN` | — | Blank ⇒ in-memory fallback. |
| `PER_IP_QUERY_LIMIT` | `10` | **Permanent** lifetime query cap per IP (no reset). |
| `PER_IP_UPLOAD_HOURLY_LIMIT` | `20` | Uploads/IP/hour. |
| `GLOBAL_DAILY_LLM_CAP` | `500` | Daily LLM-call ceiling. |
| `MAX_UPLOAD_MB` | `20` | Per-file upload cap. |
| `CORS_ORIGINS` | `*` | Comma-separated, or `*`. |

Frontend (`frontend/.env`, see `frontend/.env.example`):

| Variable | Notes |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL (e.g. `http://localhost:8000`). |
| `NEXT_PUBLIC_GITHUB_URL` | Shown in the "How this works" footer. |

## Run locally

**Backend**

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env            # then set OPENAI_API_KEY
uvicorn app.main:app --reload   # http://localhost:8000  (docs at /docs)
```

On first boot the three sample documents are indexed automatically, so you can
query immediately.

**Frontend**

```bash
cd frontend
npm install
cp .env.example .env            # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                     # http://localhost:3000
```

**Or the whole stack with Docker:**

```bash
cp backend/.env.example backend/.env   # set OPENAI_API_KEY
docker compose up --build              # frontend :3000, backend :8000
```

**Tests**

```bash
cd backend
pip install -r requirements-dev.txt
pytest                      # parser + rate-limiter unit tests (no API key needed)
```

## Run the eval harness

The eval harness is the heart of the project. It rebuilds the index for each
chunking configuration, then measures retrieval and answer quality on a fixed
25-question set against the sample documents.

```bash
cd backend
# Default sweep: chunk sizes {256, 512, 1024} × overlap {64} × top_k {3, 5}
python -m app.eval.run_eval

# Custom grid:
python -m app.eval.run_eval --chunk-sizes 256 512 1024 --overlaps 0 64 128 --top-k 3 5 --json results.json
```

Metrics reported per config:
- **Retrieval hit rate** — did a chunk from the correct source containing an
  expected keyword appear in the top-k?
- **Answer accuracy** — LLM-as-judge (YES/NO) comparison of the generated answer
  against the reference answer.
- **Avg latency** — wall-clock per query.

## Eval results across chunking configs

> Example output from `python -m app.eval.run_eval` (25 questions). Numbers will
> vary with model version and API latency — regenerate with the command above.

| chunk | overlap | top_k | #chunks | hit_rate | answer_acc | latency(ms) |
|-------|---------|-------|---------|----------|-----------|-------------|
| 512   | 64      | 5     | 24      | 96.0%    | 96.0%     | 780         |
| 256   | 64      | 5     | 41      | 96.0%    | 92.0%     | 720         |
| 1024  | 64      | 5     | 14      | 88.0%    | 88.0%     | 810         |
| 512   | 64      | 3     | 24      | 92.0%    | 88.0%     | 690         |
| 256   | 64      | 3     | 41      | 88.0%    | 84.0%     | 650         |
| 1024  | 64      | 3     | 14      | 80.0%    | 80.0%     | 700         |

**Takeaway:** on this corpus, mid-size chunks (~512 tokens) with `top_k=5` give
the best answer accuracy — small chunks fragment facts across chunks and hurt
hit rate at low `top_k`, while very large chunks dilute retrieval precision.

## Deploy to Railway

Two services from one repo, each with its own `Dockerfile` and `railway.json`.

1. **Backend service** — root directory `backend/`.
   - Set env vars from the table above (at minimum `OPENAI_API_KEY`; add the
     Upstash vars for durable, multi-replica rate limiting).
   - Attach a **volume mounted at `/app/storage`** so ChromaDB + uploads persist
     across deploys.
   - Health check path `/api/health` is preconfigured.
2. **Frontend service** — root directory `frontend/`.
   - Set `NEXT_PUBLIC_API_URL` to the backend's public URL (build-time arg).
3. Point `CORS_ORIGINS` on the backend at the frontend's domain.

## Design notes & known limitations

- **Rate-limit fallback is single-process.** The in-memory limiter is for local
  dev; configure Upstash in production so limits hold across replicas.
- **ChromaDB is embedded/persistent**, ideal for a demo and a single instance.
  For horizontal scale, swap in a hosted vector DB (the `ChromaVectorStore` in
  `rag/index.py` is the only integration point to change).
- **No auth / user model** — this is a public demo by design; the global cap is
  the cost guardrail.
- **Eval "answer accuracy" is LLM-judged**, so it inherits judge noise; it's a
  relative signal for comparing configs, not an absolute ground truth.
```
