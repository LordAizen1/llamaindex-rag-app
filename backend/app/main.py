"""FastAPI application: upload, list/delete/reindex documents, streaming query.

Production concerns wired in: per-IP + global rate limiting, structured
per-query logging, capped tokens, and graceful error handling.
"""
import json
import logging
import os
import time
import uuid

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config import Settings, get_settings
from .models import DocumentInfo, QuotaInfo, UploadResult
from .rag import index as index_mod
from .rag.parsers import EmptyDocument, UnsupportedFileType
from .rag.query import answer_stream, token_usage
from .seed import seed_samples
from .services.logging_conf import configure_logging, log_event
from .services.rate_limit import get_limiter

configure_logging()
logger = logging.getLogger("api")

app = FastAPI(title="RAG Document Q&A", version="1.0.0")

s = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=s.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    os.makedirs(get_settings().upload_dir, exist_ok=True)
    try:
        seed_samples()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Seeding failed: %s", exc)


def client_ip(request: Request) -> str:
    """Resolve the real client IP, honoring Railway's proxy header."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# --------------------------------------------------------------------------- #
# Health & config
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "llm_model": settings.llm_model,
        "embed_model": settings.embed_model,
        "rate_limit_mode": get_limiter().mode,
    }


@app.get("/api/config")
def config(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "top_k": settings.top_k,
        "max_tokens": settings.max_tokens,
        "max_upload_mb": settings.max_upload_mb,
        "per_ip_query_limit": settings.per_ip_query_limit,
    }


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
@app.get("/api/documents", response_model=list[DocumentInfo])
def list_docs() -> list[DocumentInfo]:
    return [DocumentInfo(**d) for d in index_mod.list_documents()]


@app.post("/api/upload", response_model=list[UploadResult])
async def upload(
    request: Request,
    files: list[UploadFile] = File(...),
    settings: Settings = Depends(get_settings),
):
    # Uploads embed documents (a cost), so they're rate limited per IP too.
    up_status = get_limiter().check_upload(client_ip(request))
    if not up_status.allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "scope": "upload",
                "message": f"Upload limit reached ({settings.per_ip_upload_hourly_limit}/hour).",
                "reset_seconds": up_status.reset_seconds,
            },
        )

    results: list[UploadResult] = []
    for f in files:
        filename = os.path.basename(f.filename or "unnamed")
        try:
            data = await f.read()
            if len(data) > settings.max_upload_bytes:
                raise ValueError(
                    f"File exceeds {settings.max_upload_mb} MB limit "
                    f"({len(data) / 1024 / 1024:.1f} MB)."
                )
            dest = os.path.join(settings.upload_dir, filename)
            with open(dest, "wb") as out:
                out.write(data)

            # Replace any prior version of this document before re-indexing.
            index_mod.delete_document(filename)
            n = index_mod.ingest_file(dest, filename)
            results.append(UploadResult(filename=filename, status="indexed", chunks=n))
            log_event(logger, "upload", filename=filename, chunks=n, bytes=len(data))
        except (UnsupportedFileType, EmptyDocument, ValueError) as exc:
            results.append(UploadResult(filename=filename, status="error", error=str(exc)))
            log_event(logger, "upload_error", filename=filename, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected upload failure for %s", filename)
            results.append(
                UploadResult(filename=filename, status="error", error="Internal error while indexing.")
            )
    return results


@app.delete("/api/documents/{source}")
def delete_doc(source: str) -> dict:
    removed = index_mod.delete_document(source)
    if removed == 0:
        raise HTTPException(status_code=404, detail=f"No document named '{source}'.")
    # Best-effort remove the stored upload too.
    path = os.path.join(get_settings().upload_dir, source)
    if os.path.isfile(path):
        os.remove(path)
    return {"deleted": source, "chunks_removed": removed}


@app.post("/api/documents/{source}/reindex")
def reindex_doc(source: str) -> dict:
    path = os.path.join(get_settings().upload_dir, source)
    if not os.path.isfile(path):
        # Fall back to the samples dir for pre-seeded docs.
        path = os.path.join(get_settings().samples_dir, source)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"Original file for '{source}' not found.")
    index_mod.delete_document(source)
    n = index_mod.ingest_file(path, source)
    return {"reindexed": source, "chunks": n}


# --------------------------------------------------------------------------- #
# Quota (unobtrusive display)
# --------------------------------------------------------------------------- #
@app.get("/api/quota", response_model=QuotaInfo)
def quota(request: Request, settings: Settings = Depends(get_settings)) -> QuotaInfo:
    limiter = get_limiter()
    ip_status = limiter.peek_ip(client_ip(request))
    return QuotaInfo(
        per_ip_limit=settings.per_ip_query_limit,
        remaining=ip_status.remaining,
        reset_seconds=ip_status.reset_seconds,
        global_daily_cap=settings.global_daily_llm_cap,
        global_used=limiter.peek_global(),
    )


# --------------------------------------------------------------------------- #
# Query (SSE stream)
# --------------------------------------------------------------------------- #
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/api/query")
async def query(request: Request, settings: Settings = Depends(get_settings)):
    body = await request.json()
    question = (body.get("question") or "").strip()
    top_k = body.get("top_k")
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty.")

    limiter = get_limiter()
    ip = client_ip(request)

    # 1. Per-IP hourly limit.
    ip_status = limiter.check_ip(ip)
    if not ip_status.allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "scope": "ip",
                "message": f"You've reached this demo's limit of {settings.per_ip_query_limit} queries.",
                "reset_seconds": ip_status.reset_seconds,
                "remaining": 0,
            },
        )

    # 2. Global daily cost backstop.
    global_status = limiter.check_global()
    if not global_status.allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "scope": "global",
                "message": "The demo has hit its daily capacity. Please try again tomorrow.",
                "reset_seconds": global_status.reset_seconds,
            },
        )

    request_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()

    try:
        result = answer_stream(question, top_k=top_k)
    except Exception:  # noqa: BLE001
        logger.exception("Retrieval failed for request %s", request_id)
        raise HTTPException(status_code=502, detail="Retrieval backend failed.")

    citations = result.citations()

    def event_stream():
        # First frame: metadata + citations, so the UI can render sources immediately.
        yield _sse(
            "meta",
            {
                "request_id": request_id,
                "chunks_retrieved": len(citations),
                "citations": citations,
                "quota_remaining": ip_status.remaining,
            },
        )
        answer_chars = 0
        try:
            for token in result.stream:
                answer_chars += len(token)
                yield _sse("token", {"t": token})
        except Exception:  # noqa: BLE001
            logger.exception("Streaming failed for request %s", request_id)
            yield _sse("error", {"message": "The model failed while generating the answer."})
            return

        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        usage = token_usage()
        yield _sse(
            "done",
            {
                "latency_ms": latency_ms,
                "chunks_retrieved": len(citations),
                "tokens": usage,
            },
        )
        log_event(
            logger,
            "query",
            request_id=request_id,
            ip=ip,
            question=question[:200],
            latency_ms=latency_ms,
            chunks_retrieved=len(citations),
            answer_chars=answer_chars,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
