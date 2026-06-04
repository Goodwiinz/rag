"""Regression test for the L1 job-store cleanup throttle (audit fix #9).

``set_job`` previously ran the O(n) ``_l1_cleanup`` under ``_l1_lock`` on
every write; it now uses the throttled ``_l1_maybe_cleanup`` (already used by
``get_job``), so the full scan runs at most once per throttle window.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_job_uses_throttled_cleanup(monkeypatch):
    """Many writes in one window must not each trigger the full L1 cleanup."""
    import src.services.agent.job_store as js

    # No Redis dependency — isolate the L1 path.
    monkeypatch.setattr(js, "set_job_redis_only", AsyncMock())

    calls = {"n": 0}
    real_cleanup = js._l1_cleanup

    def _counting_cleanup():
        calls["n"] += 1
        real_cleanup()

    monkeypatch.setattr(js, "_l1_cleanup", _counting_cleanup)
    # Fresh throttle window so the 60s gate has just elapsed.
    monkeypatch.setattr(js, "_LAST_L1_CLEANUP", js.time.time())

    for i in range(50):
        await js.set_job(f"job-{i}", {"status": "running"})

    # Throttled: not one full O(n) cleanup per write within the <60s window.
    assert calls["n"] <= 1
