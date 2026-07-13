"""Rate limiting + global cost backstop.

Three independent limits:
  1. Per-IP queries: a PERMANENT lifetime cap (no reset) — once an IP has used
     its N queries, it is blocked for good. This is the primary cost guard.
  2. Per-IP uploads: N/hour (fixed hourly window).
  3. Global: hard daily ceiling on LLM calls, regardless of IP.

Backed by Upstash Redis when configured; otherwise falls back to an in-process
store so the app runs locally with no external dependency.

Note: the permanent per-IP cap is only truly permanent with Upstash configured.
The in-memory fallback resets when the process restarts (and is per-replica),
which is fine for local dev but means production needs Upstash to enforce it.
"""
import threading
import time
from dataclasses import dataclass

from ..config import get_settings

try:
    from upstash_redis import Redis  # type: ignore
except Exception:  # pragma: no cover
    Redis = None  # noqa: N816


@dataclass
class LimitStatus:
    allowed: bool
    remaining: int
    reset_seconds: int   # 0 means "never resets" (permanent cap)
    used: int = 0


class _MemoryBackend:
    """Counters kept in memory (single-process only). ttl=None => permanent."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[int, float | None]] = {}  # key -> (count, expires_at|None)
        self._lock = threading.Lock()

    def incr(self, key: str, ttl: int | None) -> tuple[int, int]:
        now = time.time()
        with self._lock:
            count, expires = self._store.get(key, (0, None if ttl is None else now + ttl))
            if expires is not None and now >= expires:
                count, expires = 0, now + ttl  # type: ignore[operator]
            count += 1
            self._store[key] = (count, expires)
            remaining_ttl = 0 if expires is None else int(expires - now)
            return count, remaining_ttl

    def get(self, key: str) -> int:
        now = time.time()
        with self._lock:
            count, expires = self._store.get(key, (0, None))
            if expires is not None and now >= expires:
                return 0
            return count


class _RedisBackend:
    def __init__(self, url: str, token: str) -> None:
        self._redis = Redis(url=url, token=token)

    def incr(self, key: str, ttl: int | None) -> tuple[int, int]:
        count = self._redis.incr(key)
        if ttl is not None and count == 1:
            self._redis.expire(key, ttl)  # no expiry set => key persists forever
        if ttl is None:
            return int(count), 0
        remaining_ttl = self._redis.ttl(key)
        return int(count), int(remaining_ttl if remaining_ttl and remaining_ttl > 0 else ttl)

    def get(self, key: str) -> int:
        val = self._redis.get(key)
        return int(val) if val else 0


class RateLimiter:
    def __init__(self) -> None:
        s = get_settings()
        if Redis and s.upstash_redis_rest_url and s.upstash_redis_rest_token:
            self.backend = _RedisBackend(s.upstash_redis_rest_url, s.upstash_redis_rest_token)
            self.mode = "redis"
        else:
            self.backend = _MemoryBackend()
            self.mode = "memory"

    def _hour_bucket(self) -> int:
        return int(time.time() // 3600)

    def _day_bucket(self) -> int:
        return int(time.time() // 86400)

    def check_ip(self, ip: str) -> LimitStatus:
        """Permanent lifetime cap on queries per IP (no window, never resets)."""
        s = get_settings()
        key = f"rl:ip:{ip}"  # no time bucket => permanent
        count, _ = self.backend.incr(key, None)
        return LimitStatus(
            allowed=count <= s.per_ip_query_limit,
            remaining=max(0, s.per_ip_query_limit - count),
            reset_seconds=0,
            used=count,
        )

    def peek_ip(self, ip: str) -> LimitStatus:
        """Read current usage without incrementing (for quota display)."""
        s = get_settings()
        count = self.backend.get(f"rl:ip:{ip}")
        return LimitStatus(
            allowed=count < s.per_ip_query_limit,
            remaining=max(0, s.per_ip_query_limit - count),
            reset_seconds=0,
            used=count,
        )

    def check_upload(self, ip: str) -> LimitStatus:
        s = get_settings()
        key = f"rl:upload:{ip}:{self._hour_bucket()}"
        count, ttl = self.backend.incr(key, 3600)
        return LimitStatus(
            allowed=count <= s.per_ip_upload_hourly_limit,
            remaining=max(0, s.per_ip_upload_hourly_limit - count),
            reset_seconds=ttl,
            used=count,
        )

    def check_global(self) -> LimitStatus:
        s = get_settings()
        key = f"rl:global:{self._day_bucket()}"
        count, ttl = self.backend.incr(key, 86400)
        return LimitStatus(
            allowed=count <= s.global_daily_llm_cap,
            remaining=max(0, s.global_daily_llm_cap - count),
            reset_seconds=ttl,
            used=count,
        )

    def peek_global(self) -> int:
        key = f"rl:global:{self._day_bucket()}"
        return self.backend.get(key)


_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter
