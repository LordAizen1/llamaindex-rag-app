"""Central configuration, sourced from environment / .env.

Chunking + retrieval params are surfaced here (not hardcoded) so the eval
harness can vary them.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- OpenAI ---
    openai_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"
    embed_model: str = "text-embedding-3-large"

    # --- Storage ---
    chroma_dir: str = "./storage/chroma"
    upload_dir: str = "./storage/uploads"
    collection_name: str = "documents"
    samples_dir: str = "./samples"

    # --- RAG params (configurable so the eval harness can vary them) ---
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 5
    max_tokens: int = 512

    # --- Rate limiting / cost backstop ---
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    per_ip_query_limit: int = 10           # PERMANENT lifetime cap on queries per IP
    per_ip_upload_hourly_limit: int = 20   # document uploads per IP per hour
    global_daily_llm_cap: int = 500        # hard daily ceiling on LLM calls

    # --- Uploads ---
    max_upload_mb: int = 20

    # --- Misc ---
    cors_origins: str = "*"                # comma-separated, or "*"
    seed_samples: bool = True              # pre-seed index with sample docs on boot

    @property
    def cors_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
