"""Audit finding D (live trace thread e3c56cef, 2026-08-11): DO KB chunks were
injected into the prompt regardless of relevance score — a query about
attention mechanisms pulled 5 chunks at 0.036-0.25 cohere relevance from
unrelated cybersecurity surveys. ``_drop_low_relevance_chunks`` floors only
cohere-scored chunks (the one calibrated 0-1 scale in the code); other score
sources (rank_proxy, upstream) pass through untouched.
"""

from __future__ import annotations

from src.services.agent._nodes_rag import _drop_low_relevance_chunks


def _ctx(score: float, score_source: str | None) -> dict:
    return {"content": "x", "score": score, "score_source": score_source}


def test_drops_junk_cohere_scores_below_floor() -> None:
    contexts = [_ctx(0.036, "cohere"), _ctx(0.25, "cohere")]
    kept = _drop_low_relevance_chunks(contexts)
    assert kept == [_ctx(0.25, "cohere")]


def test_keeps_non_cohere_scores_regardless_of_value() -> None:
    """rank_proxy / upstream scales aren't verified — never floored here."""
    contexts = [_ctx(0.01, "rank_proxy"), _ctx(0.02, "upstream"), _ctx(0.0, None)]
    assert _drop_low_relevance_chunks(contexts) == contexts


def test_no_chunks_dropped_is_a_noop() -> None:
    contexts = [_ctx(0.9, "cohere")]
    assert _drop_low_relevance_chunks(contexts) == contexts
