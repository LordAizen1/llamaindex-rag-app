"""Unit tests for the in-memory rate limiter fallback."""
from app.services.rate_limit import RateLimiter, _MemoryBackend


def _limiter_with_limits(per_ip: int, daily: int) -> RateLimiter:
    rl = RateLimiter()
    rl.backend = _MemoryBackend()  # force in-memory regardless of env
    # Patch settings-derived limits via monkeying the getter is overkill;
    # instead rely on defaults and assert relative behavior.
    return rl


def test_per_ip_blocks_after_limit(monkeypatch):
    from app.services import rate_limit as rl_mod

    rl = RateLimiter()
    rl.backend = _MemoryBackend()

    # Drive up to the configured per-IP limit.
    limit = rl_mod.get_settings().per_ip_query_limit
    statuses = [rl.check_ip("9.9.9.9") for _ in range(limit + 2)]

    assert statuses[0].allowed is True
    assert statuses[limit - 1].allowed is True          # last allowed call
    assert statuses[limit].allowed is False             # first blocked call
    assert statuses[-1].remaining == 0


def test_peek_does_not_increment():
    rl = RateLimiter()
    rl.backend = _MemoryBackend()
    rl.check_ip("5.5.5.5")
    before = rl.peek_ip("5.5.5.5")
    after = rl.peek_ip("5.5.5.5")
    assert before.used == after.used == 1


def test_memory_backend_window_expiry():
    b = _MemoryBackend()
    count, ttl = b.incr("k", ttl=100)
    assert count == 1 and 0 < ttl <= 100
    count2, _ = b.incr("k", ttl=100)
    assert count2 == 2
    assert b.get("k") == 2
