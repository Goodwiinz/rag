"""R4-L16: InMemoryRateLimiter.requests must not retain expired keys forever.

defaultdict(deque) never drops a key on its own -- every distinct rate-limit
identifier (user id / IP) that has ever made one request stays in memory,
even after its whole window has expired. This pins the fix: pruning an empty
deque for the just-touched key, plus a periodic full sweep for keys that stop
being queried entirely.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from src.middleware.rate_limiting import _SWEEP_EVERY_N_CALLS, InMemoryRateLimiter

pytestmark = pytest.mark.unit


def test_stale_timestamp_pruned_on_next_touch_of_same_key():
    limiter = InMemoryRateLimiter()
    limiter.is_allowed("user-1", limit=5, window=60)
    assert len(limiter.requests["user-1"]) == 1

    with patch("time.time", return_value=time.time() + 61):
        limiter.is_allowed("user-1", limit=5, window=60)
        # The old (now-expired) timestamp was pruned; only the new request remains.
        assert len(limiter.requests["user-1"]) == 1


def test_key_with_no_further_requests_is_dropped_not_kept_forever():
    limiter = InMemoryRateLimiter()
    limiter.is_allowed("one-shot-user", limit=5, window=60)
    assert "one-shot-user" in limiter.requests

    # Nobody ever calls is_allowed("one-shot-user", ...) again. A different
    # key's sweep (triggered every _SWEEP_EVERY_N_CALLS calls) must still
    # reclaim it once its window has passed -- this is the actual R4-L16 leak
    # (defaultdict never drops keys that just go quiet).
    with patch("time.time", return_value=time.time() + 61):
        for i in range(_SWEEP_EVERY_N_CALLS):
            limiter.is_allowed(f"other-{i}", limit=5, window=60)

    assert "one-shot-user" not in limiter.requests


def test_thousand_distinct_keys_do_not_survive_past_their_window():
    limiter = InMemoryRateLimiter()
    base_time = time.time()

    with patch("time.time", return_value=base_time):
        for i in range(1000):
            limiter.is_allowed(f"key-{i}", limit=5, window=60)
    assert len(limiter.requests) == 1000

    # Advance well past the window and touch one more (unrelated) key. The
    # periodic sweep plus per-key eviction must reclaim the 1000 stale
    # entries instead of leaking them for the process lifetime.
    with patch("time.time", return_value=base_time + 120):
        for i in range(_SWEEP_EVERY_N_CALLS - 1000 + 6):
            limiter.is_allowed("fresh-key", limit=5, window=60)

    assert len(limiter.requests) <= 1  # only "fresh-key" (if still in-window) survives
    assert all(k == "fresh-key" for k in limiter.requests)


def test_sweep_does_not_evict_a_longer_window_key_that_is_merely_older_than_this_calls_window():
    """A 300s-window (api_calls) call must not sweep away a 3600s-window
    (heavy_operations) key whose last hit is only 400s old -- that would
    silently reset an hourly security budget. The sweep has to judge
    staleness against the widest window any caller has used, not whichever
    call happens to trigger the periodic sweep."""
    limiter = InMemoryRateLimiter()
    base_time = time.time()

    with patch("time.time", return_value=base_time):
        limiter.is_allowed("heavy-user", limit=10, window=3600)

    # 400s later: still well within the 3600s window, long past a 300s one.
    with patch("time.time", return_value=base_time + 400):
        for i in range(_SWEEP_EVERY_N_CALLS):
            limiter.is_allowed(f"api-caller-{i}", limit=100, window=300)

    assert "heavy-user" in limiter.requests


def test_rate_limiting_still_enforced_after_eviction_logic_added():
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        allowed, _ = limiter.is_allowed("user-1", limit=3, window=60)
        assert allowed is True
    allowed, info = limiter.is_allowed("user-1", limit=3, window=60)
    assert allowed is False
    assert info["retry_after"] is not None
