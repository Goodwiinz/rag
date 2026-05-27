"""Integration test for semantic memory recall (P4.2).

Trace evidence (rag-agent-dev `019e05ad`, `019e040b`) showed every
recalled `user_memory` entry carried `score: null` — confirming that
`AsyncPostgresStore.asearch` was running without a semantic index and
falling back to lexical / recency ranking.

After P4.2, `memory.py` wires Cohere as the embedder in
`AsyncPostgresStore(pool, index={...})`. This test stores two semantically
distinct documents and asserts the query "neural networks" ranks the
"deep learning" doc above the "weather" doc with a non-null score.

Requires a real Postgres + Cohere API key. Marked @integration so the
default unit-suite run skips it.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def store():
    if not os.getenv("COHERE_EMBED_API_KEY") and not os.getenv(
        "COHERE_RERANK_API_KEY"
    ):
        pytest.skip("Cohere API key not set — skipping semantic recall test")

    from src.services.agent.memory import get_memory_store, reset_memory_store

    await reset_memory_store()
    s = await get_memory_store()
    yield s
    await reset_memory_store()


async def test_async_postgres_store_returns_score_with_index(store):
    """Stored docs are ranked by similarity, not random."""
    namespace = ("user", f"test-{uuid4()}")

    await store.aput(
        namespace,
        "deep-learning",
        {"query": "transformer architectures and attention mechanisms"},
    )
    await store.aput(
        namespace,
        "weather",
        {"query": "tomorrow's weather forecast in Manhattan"},
    )

    out = await store.asearch(namespace, query="neural networks", limit=5)

    assert out, "expected at least one recalled memory"
    top = out[0]
    assert (
        getattr(top, "score", None) is not None
    ), f"score must be populated when index= is configured, got {top}"
    assert 0.0 < float(top.score) <= 1.0
    # The deep-learning doc should out-rank the weather doc.
    keys = [item.key for item in out]
    assert keys.index("deep-learning") < keys.index("weather"), (
        f"semantic rank wrong: {keys}"
    )


async def test_indexed_store_logs_indexed_true(store, caplog):
    """Diagnostic log emits indexed=True once Cohere index wired."""
    # Reset already happened in fixture teardown; trigger fresh init.
    from src.services.agent.memory import get_memory_store, reset_memory_store

    await reset_memory_store()
    caplog.clear()
    with caplog.at_level("INFO"):
        await get_memory_store()

    assert any(
        "indexed=True" in record.message
        for record in caplog.records
        if "Memory store initialised" in record.message
    ), "expected diagnostic log to confirm indexed=True"
