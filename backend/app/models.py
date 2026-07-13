"""Pydantic request/response schemas."""
from pydantic import BaseModel


class Citation(BaseModel):
    source: str
    page: int | None = None
    section: str | None = None
    score: float | None = None
    text: str


class QueryRequest(BaseModel):
    question: str
    top_k: int | None = None


class DocumentInfo(BaseModel):
    source: str
    chunks: int
    file_type: str | None = None


class UploadResult(BaseModel):
    filename: str
    status: str          # indexed | error
    chunks: int = 0
    error: str | None = None


class QuotaInfo(BaseModel):
    per_ip_limit: int
    remaining: int
    reset_seconds: int
    global_daily_cap: int
    global_used: int
