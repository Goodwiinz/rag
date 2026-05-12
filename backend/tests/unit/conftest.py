"""Shared fixtures for backend/tests/unit/.

Resets the module-level compiled-graph cache (introduced for first-token
latency wins) between every unit test so cross-test pollution from
``src.api.agent.streaming._COMPILED_GRAPH`` cannot bleed assertions
between unrelated test modules.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_compiled_graph_cache_unit():
    """Clear cached compiled graph between every unit test."""
    import src.api.agent.streaming as mod

    mod._COMPILED_GRAPH = None
    yield
    mod._COMPILED_GRAPH = None
