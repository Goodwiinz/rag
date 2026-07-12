"""Tests for summarize_evidence (src/services/agent/evidence.py).

Never-raises passthrough is the load-bearing contract — RCS is presentation
enrichment on top of already-retrieved chunks, so any failure mode (timeout,
malformed LLM output, fabricated quote) must degrade to usable chunk data,
never drop or corrupt it.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agent.evidence import summarize_evidence


def _msg(content: str) -> SimpleNamespace:
    return SimpleNamespace(content=content)


def _chunk(text: str, document_id: str, title: str = "Doc") -> dict:
    return {
        "text": text,
        "score": 0.5,
        "document_id": document_id,
        "title": title,
        "metadata": {},
    }


def _patch_llm(side_effect):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=side_effect)
    return patch("src.services.agent.evidence.build_lightweight_llm", return_value=llm)


@pytest.mark.unit
async def test_happy_path_enriched_and_sorted_desc():
    chunks = [
        _chunk("Alpha content about apples.", "a"),
        _chunk("Beta content about bananas.", "b"),
    ]
    responses = [
        _msg(
            json.dumps(
                {
                    "relevance": 3,
                    "summary": "weak match",
                    "quote": "Alpha content about apples.",
                }
            )
        ),
        _msg(
            json.dumps(
                {
                    "relevance": 9,
                    "summary": "strong match",
                    "quote": "Beta content about bananas.",
                }
            )
        ),
    ]

    with _patch_llm(side_effect=responses):
        result = await summarize_evidence("q", chunks)

    assert [c["document_id"] for c in result] == ["b", "a"]
    assert result[0]["relevance"] == 9
    assert result[0]["summary"] == "strong match"
    assert result[1]["relevance"] == 3


@pytest.mark.unit
async def test_fabricated_quote_nulled_summary_kept():
    chunks = [_chunk("Real excerpt text.", "a")]
    response = _msg(
        json.dumps(
            {
                "relevance": 7,
                "summary": "kept summary",
                "quote": "This sentence was never in the excerpt.",
            }
        )
    )

    with _patch_llm(side_effect=[response]):
        result = await summarize_evidence("q", chunks)

    assert result[0]["quote"] is None
    assert result[0]["summary"] == "kept summary"


@pytest.mark.unit
async def test_malformed_json_passes_through_unenriched_others_fine():
    chunks = [_chunk("Broken one.", "a"), _chunk("Good one.", "b")]
    responses = [
        _msg("not json at all"),
        _msg(json.dumps({"relevance": 6, "summary": "ok", "quote": "Good one."})),
    ]

    with _patch_llm(side_effect=responses):
        result = await summarize_evidence("q", chunks)

    assert len(result) == 2
    # Enriched ("b") sorts first; unenriched ("a") has no 'relevance' key.
    assert result[0]["document_id"] == "b"
    assert result[0]["relevance"] == 6
    assert result[1]["document_id"] == "a"
    assert "relevance" not in result[1]


@pytest.mark.unit
async def test_budget_timeout_returns_input_unchanged():
    chunks = [_chunk("a text", "a"), _chunk("b text", "b")]

    async def _hangs(*args, **kwargs):
        raise asyncio.TimeoutError()

    with (
        patch("src.services.agent.evidence._EVIDENCE_BUDGET_SECONDS", 0.01),
        _patch_llm(side_effect=_hangs),
    ):
        result = await summarize_evidence("q", chunks)

    assert result == chunks


@pytest.mark.unit
async def test_more_than_five_chunks_only_first_five_enriched():
    chunks = [_chunk(f"text {i}", str(i)) for i in range(7)]
    responses = [
        _msg(json.dumps({"relevance": i, "summary": "s", "quote": f"text {i}"}))
        for i in range(5)
    ]

    with _patch_llm(side_effect=responses):
        result = await summarize_evidence("q", chunks)

    assert len(result) == 7
    enriched_ids = {c["document_id"] for c in result if "relevance" in c}
    assert enriched_ids == {"0", "1", "2", "3", "4"}
    # Tail (indices 5, 6) preserved after the enriched+unenriched block, in order.
    assert [c["document_id"] for c in result[-2:]] == ["5", "6"]


@pytest.mark.unit
async def test_relevance_clamping():
    chunks = [
        _chunk("high text", "hi"),
        _chunk("low text", "lo"),
        _chunk("bad text", "bad"),
    ]
    responses = [
        _msg(json.dumps({"relevance": 15, "summary": "s", "quote": "high text"})),
        _msg(json.dumps({"relevance": -3, "summary": "s", "quote": "low text"})),
        _msg(json.dumps({"relevance": "high", "summary": "s", "quote": "bad text"})),
    ]

    with _patch_llm(side_effect=responses):
        result = await summarize_evidence("q", chunks)

    by_id = {c["document_id"]: c for c in result}
    assert by_id["hi"]["relevance"] == 10
    assert by_id["lo"]["relevance"] == 0
    # Non-numeric relevance ("high") is either clamped or left unenriched.
    assert "relevance" not in by_id["bad"] or 0 <= by_id["bad"]["relevance"] <= 10
