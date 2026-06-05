"""Regression tests for the L1 monotonic sequence guard (audit fix #15).

``set_job`` previously guarded L1 with ``created_at <=``, so two updates in the
same ``time.time()`` tick could overwrite out of order. A per-process ``_seq``
tiebreaker now orders same-tick writes via ``(created_at, _seq)``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


def test_is_newer_or_equal_seq_breaks_ties():
    from src.services.agent.job_store import _is_newer_or_equal

    older = {"created_at": 1000.0, "_seq": 5}
    newer = {"created_at": 1000.0, "_seq": 6}
    assert _is_newer_or_equal(newer, older) is True
    assert _is_newer_or_equal(older, newer) is False  # equal tick, lower seq loses


def test_is_newer_or_equal_created_at_dominates():
    from src.services.agent.job_store import _is_newer_or_equal

    # A newer wall-clock always wins regardless of _seq.
    assert _is_newer_or_equal(
        {"created_at": 1001.0, "_seq": 1}, {"created_at": 1000.0, "_seq": 99}
    ) is True


def test_is_newer_or_equal_backward_compat_missing_seq():
    from src.services.agent.job_store import _is_newer_or_equal

    # Pre-_seq Redis values default to seq 0; created_at still orders them.
    assert _is_newer_or_equal({"created_at": 1000.0}, {"created_at": 999.0}) is True


@pytest.mark.asyncio
async def test_set_job_same_tick_orders_by_seq(monkeypatch):
    """Two writes in one frozen tick: the later (higher _seq) must win."""
    import src.services.agent.job_store as js

    monkeypatch.setattr(js, "set_job_redis_only", AsyncMock())
    monkeypatch.setattr(js.time, "time", lambda: 1000.0)  # freeze created_at
    js._l1.clear()

    await js.set_job("job-1", {"status": "running"})
    await js.set_job("job-1", {"status": "completed"})

    assert js._l1["job-1"]["status"] == "completed"
