"""Phase 3 of the arXiv-429 fix: the shared cross-pod rate gate
(`_acquire_arxiv_rate_slot`). Pure unit tests — a fake Redis runs the same
slot-reservation logic as the Lua script; no real Redis.

Pins: (1) no REDIS_URL disables the gate (per-process fallback); (2) rapid calls
are serialized >= 3s apart; (3) a queue deeper than the cap proceeds now;
(4) a transient Redis error falls back without permanently disabling.
"""

from __future__ import annotations

from src.services.arxiv import arxiv_service as svc


def _reset(monkeypatch, redis_obj):
    monkeypatch.setattr(svc, "_arxiv_gate_redis", redis_obj, raising=False)
    monkeypatch.setattr(svc, "_arxiv_gate_disabled", False, raising=False)


class _FakeRedis:
    """Mimics the Lua slot-reservation in Python so we can assert timing."""

    def __init__(self):
        self.store = {}

    async def eval(self, _script, _numkeys, key, now_ms, interval, maxwait, ttl):
        last = int(self.store.get(key, 0))
        slot = max(int(now_ms), last + int(interval))
        wait = slot - int(now_ms)
        if wait > int(maxwait):
            return -1
        self.store[key] = slot
        return wait


class _RaisingRedis:
    async def eval(self, *_a, **_k):
        raise RuntimeError("redis down")


async def test_no_redis_url_disables_gate(monkeypatch):
    _reset(monkeypatch, None)
    from src.core.config import settings

    monkeypatch.setattr(settings, "REDIS_URL", "", raising=False)
    assert await svc._acquire_arxiv_rate_slot() is None  # → per-process fallback


async def test_rapid_calls_serialize_three_seconds_apart(monkeypatch):
    _reset(monkeypatch, _FakeRedis())
    w1 = await svc._acquire_arxiv_rate_slot()
    w2 = await svc._acquire_arxiv_rate_slot()
    assert w1 is not None and w2 is not None
    assert 0.0 <= w1 < 0.2  # first caller fires ~immediately
    assert 2.7 <= w2 <= 3.0  # second caller waits ~one 3s interval


async def test_deep_queue_proceeds_now(monkeypatch):
    fake = _FakeRedis()
    _reset(monkeypatch, fake)
    # Pre-load a slot far in the future so the next reservation exceeds MAX_WAIT.
    import time

    fake.store[svc._ARXIV_RATE_KEY] = int(time.time() * 1000) + 60_000
    assert await svc._acquire_arxiv_rate_slot() == 0.0  # proceed, don't pile up


async def test_transient_error_falls_back_without_disabling(monkeypatch):
    _reset(monkeypatch, _RaisingRedis())
    assert await svc._acquire_arxiv_rate_slot() is None
    assert svc._arxiv_gate_disabled is False  # not permanently disabled
