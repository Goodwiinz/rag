"""DO KB ingest metrics must actually fire.

The old ``_record_metric`` read ``metrics.agent_do_kb_ingest_total`` via
getattr — a module attribute that was never defined — so every ingest metric
silently no-oped. It now goes through ``increment_counter`` with a counter
registered in ``initialize_default_metrics``, matching the retrieval path.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.services.do_kb.ingest import _record_metric

pytestmark = pytest.mark.unit


def test_record_metric_calls_increment_counter():
    with patch("src.observability.metrics.increment_counter") as inc:
        _record_metric("ok")
    inc.assert_called_once_with("agent_do_kb_ingest_total", attributes={"status": "ok"})


def test_counter_is_registered_by_default_metrics():
    # increment_counter is a no-op for unregistered names — the exact failure
    # mode this fix closes — so the name must be in the default registration.
    import inspect

    from src.observability import metrics as metrics_mod

    src = inspect.getsource(metrics_mod.initialize_default_metrics)
    assert "agent_do_kb_ingest_total" in src
