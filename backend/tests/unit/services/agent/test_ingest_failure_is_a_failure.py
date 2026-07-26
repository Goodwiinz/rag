"""A zero-paper ingest must reach the graph as a failure, not a success.

``_tool_ingest_arxiv`` returned ``{"status": "ingestion_failed",
"ingested_count": 0, ...}`` with **no top-level "error"**. The tool layer
classifies on exactly that key::

    # _nodes_tools.py
    if isinstance(result, dict) and "error" in result:
        status = "failed"

so a run that imported nothing was recorded ``status="completed"``. Three
consequences, all silent:

* the agent's error ceiling never tripped (``error_increment = 0``);
* ``tool_dedupe`` caches only ``completed`` entries, so the *failure* was
  cached as a good result and a same-turn retry was short-circuited;
* ``find_repeated_failures`` never saw it, bypassing the circuit breaker.

Same fake-success family as the synthetic harness reporting ``confirmed(n)``
for a run that ingested nothing — this is the agent-state half of it.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _classifies_as_failed(result: dict) -> bool:
    """The predicate _nodes_tools uses to downgrade an execution."""
    return isinstance(result, dict) and "error" in result


class TestFailureStatuses:
    def test_zero_ingest_carries_a_top_level_error(self) -> None:
        from src.services.agent.tools_impl import (
            _INGEST_FAILURE_STATUSES,
            INGEST_STATUS_FAILED,
        )

        assert INGEST_STATUS_FAILED in _INGEST_FAILURE_STATUSES

        result = {"status": INGEST_STATUS_FAILED, "ingested_count": 0}
        if result["status"] in _INGEST_FAILURE_STATUSES:
            result["error"] = "Ingested 0 of 1 paper(s)."

        assert _classifies_as_failed(result), (
            "a zero-paper ingest recorded as 'completed' bypasses the error "
            "ceiling, poisons the dedupe cache, and hides from the breaker"
        )

    def test_partial_ingest_also_counts_as_failure(self) -> None:
        from src.services.agent.tools_impl import (
            _INGEST_FAILURE_STATUSES,
            INGEST_STATUS_PARTIAL,
        )

        assert INGEST_STATUS_PARTIAL in _INGEST_FAILURE_STATUSES

    def test_success_statuses_are_not_failures(self) -> None:
        """A completed ingest must not be poisoned into an error."""
        from src.services.agent.tools_impl import (
            _INGEST_FAILURE_STATUSES,
            INGEST_STATUS_COMPLETE,
            INGEST_STATUS_COMPLETE_LINK_FAILED,
        )

        assert INGEST_STATUS_COMPLETE not in _INGEST_FAILURE_STATUSES
        # "ingested fine but not attached" is deliberately NOT a failure: the
        # papers are in the system and searchable.
        assert INGEST_STATUS_COMPLETE_LINK_FAILED not in _INGEST_FAILURE_STATUSES

    def test_mirrors_the_reflection_guards_vocabulary(self) -> None:
        """reflection.py already encodes which ingest statuses mean failure."""
        from src.services.agent.reflection import _INGEST_FAILURE_STATUSES as reflect
        from src.services.agent.tools_impl import _INGEST_FAILURE_STATUSES as tools

        assert set(tools) == set(reflect), (
            "the two lists must agree, or the reflection guard and the tool "
            "layer will disagree about whether an ingest succeeded"
        )
