"""``compile_agent_graph`` caches the compiled production graph.

Perf regression guard: the main graph + all three subgraphs were rebuilt and
recompiled on every chat turn. They must now be built once for the production
(checkpointer) path and reused.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langgraph.checkpoint.base import BaseCheckpointSaver


@pytest.mark.unit
def test_compile_caches_for_same_checkpointer():
    from src.services.agent import _builders

    _builders.reset_compiled_graph_cache()
    sentinel = object()
    fake_graph = MagicMock()
    fake_graph.compile.return_value = sentinel
    cp = MagicMock(spec=BaseCheckpointSaver)

    with patch.object(
        _builders, "build_agent_graph", return_value=fake_graph
    ) as mock_build:
        a = _builders.compile_agent_graph(checkpointer=cp)
        b = _builders.compile_agent_graph(checkpointer=cp)

    assert a is b is sentinel
    assert mock_build.call_count == 1  # built once; second call is a cache hit
    _builders.reset_compiled_graph_cache()


@pytest.mark.unit
def test_compile_rebuilds_for_different_checkpointer():
    from src.services.agent import _builders

    _builders.reset_compiled_graph_cache()
    fake_graph = MagicMock()
    fake_graph.compile.side_effect = lambda **kw: object()  # fresh per compile

    with patch.object(
        _builders, "build_agent_graph", return_value=fake_graph
    ) as mock_build:
        a = _builders.compile_agent_graph(checkpointer=MagicMock(spec=BaseCheckpointSaver))
        b = _builders.compile_agent_graph(checkpointer=MagicMock(spec=BaseCheckpointSaver))

    assert a is not b
    assert mock_build.call_count == 2  # different checkpointers → not shared
    _builders.reset_compiled_graph_cache()


@pytest.mark.unit
def test_memorysaver_path_is_not_cached():
    from src.services.agent import _builders

    _builders.reset_compiled_graph_cache()
    fake_graph = MagicMock()
    fake_graph.compile.side_effect = lambda **kw: object()

    with patch.object(
        _builders, "build_agent_graph", return_value=fake_graph
    ) as mock_build:
        a = _builders.compile_agent_graph(checkpointer=True)
        b = _builders.compile_agent_graph(checkpointer=True)

    assert a is not b  # checkpointer=True (fresh MemorySaver) always rebuilds
    assert mock_build.call_count == 2
    _builders.reset_compiled_graph_cache()
