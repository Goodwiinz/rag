"""Audit S2-M2 regression: rag_context / PLAN / REFLECTION frames bypassed
every byte bound on the live+buffered SSE path — live caps counted items,
the Redis buffer ltrim'd frame counts, and MAX_PAYLOAD_BYTES was enforced
only on the durable ledger. A single oversized retrieval context therefore
amplified into both the live socket and up to 5000 replayed copies.

The emitter must clamp any oversized payload to the shared MAX_PAYLOAD_BYTES
budget *before* the frame reaches the wire or the resumable buffer, so live
consumers and replays see byte-identical bounded frames.
"""

import json

import pytest

from src.api.agent import streaming as streaming_mod
from src.api.agent.streaming import _SeqEmitter
from src.services.agent.run_event_types import MAX_PAYLOAD_BYTES
from src.shared.enums import AgentStreamEvent

# The envelope adds fixed per-frame metadata (schema_version, sequence,
# event_id, occurred_at, trace_id, thread_id, route) around the clamped
# payload — allow slack for it on top of the payload budget.
_ENVELOPE_SLACK_BYTES = 2048


def _frame_data(frame: str) -> dict:
    for line in frame.splitlines():
        if line.startswith("data: "):
            data: dict = json.loads(line[len("data: ") :])
            return data
    raise AssertionError("frame carries no data line")


async def _emitter_capturing_buffer(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_SeqEmitter, list[str]]:
    captured: list[str] = []

    async def fake_append(sid: str, seq: int, frame: str) -> None:
        captured.append(frame)

    monkeypatch.setattr(streaming_mod._stream_buffer, "append", fake_append)
    emitter = _SeqEmitter()
    emitter.set_context(thread_id="thread-1")
    emitter.sid = "sid-bounds"
    return emitter, captured


async def test_oversized_rag_context_bounded_on_wire_and_buffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitter, buffered = await _emitter_capturing_buffer(monkeypatch)
    giant_contexts = [{"text": "x" * 200_000} for _ in range(3)]

    frame = await emitter.emit(
        AgentStreamEvent.RAG_CONTEXT, {"contexts": giant_contexts}
    )

    assert len(frame.encode("utf-8")) <= MAX_PAYLOAD_BYTES + _ENVELOPE_SLACK_BYTES
    # Replay must see exactly what live saw — one clamp point feeds both.
    assert buffered == [frame]
    data = _frame_data(frame)
    assert data["payload_truncated"] is True
    # Shape survives clipping: still a list of context dicts.
    assert isinstance(data["contexts"], list) and len(data["contexts"]) == 3
    assert all(
        isinstance(ctx, dict) and isinstance(ctx["text"], str)
        for ctx in data["contexts"]
    )


async def test_oversized_plan_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    emitter, _ = await _emitter_capturing_buffer(monkeypatch)

    frame = await emitter.emit(
        AgentStreamEvent.PLAN,
        {
            "steps": [
                {"title": f"step-{i}", "detail": "y" * 50_000} for i in range(200)
            ],
            "reasoning": "z" * 300_000,
        },
    )

    assert len(frame.encode("utf-8")) <= MAX_PAYLOAD_BYTES + _ENVELOPE_SLACK_BYTES
    assert _frame_data(frame)["payload_truncated"] is True


async def test_oversized_reflection_issues_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitter, _ = await _emitter_capturing_buffer(monkeypatch)

    frame = await emitter.emit(
        AgentStreamEvent.REFLECTION,
        {
            "passed": False,
            "issues": ["w" * 120_000 for _ in range(10)],
            "round": 1,
            "revising": True,
        },
    )

    assert len(frame.encode("utf-8")) <= MAX_PAYLOAD_BYTES + _ENVELOPE_SLACK_BYTES
    data = _frame_data(frame)
    assert data["payload_truncated"] is True
    assert data["passed"] is False and data["revising"] is True


async def test_normal_sized_payload_passes_through_untouched() -> None:
    """Under-budget frames keep their exact pre-clamp shape — no marker, no
    mutation — so this is a no-op for every well-behaved producer."""
    emitter = _SeqEmitter()
    emitter.set_context(thread_id="thread-1")

    payload = {
        "contexts": [{"title": "Paper", "score": 0.87, "snippet": "short"}],
    }
    frame = await emitter.emit(AgentStreamEvent.RAG_CONTEXT, payload, buffer=False)

    data = _frame_data(frame)
    assert data["contexts"] == payload["contexts"]
    assert "payload_truncated" not in data


async def test_clamped_frames_stay_individually_valid_sse() -> None:
    """A pathological multi-megabyte payload must not wedge the stream: the
    emitter degrades to a bounded frame instead of raising."""
    emitter = _SeqEmitter()
    emitter.set_context(thread_id="thread-1")
    pathological = {"contexts": [{"text": "\uffff" * 5_000_000}]}

    frame = await emitter.emit(AgentStreamEvent.RAG_CONTEXT, pathological, buffer=False)

    assert frame.startswith("id: 1\nevent: rag_context\ndata: ")
    assert len(frame.encode("utf-8")) <= MAX_PAYLOAD_BYTES + _ENVELOPE_SLACK_BYTES
