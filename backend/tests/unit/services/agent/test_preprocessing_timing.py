"""preprocessing_node subtask instrumentation.

Verifies each of the three fan-out subtasks (rag / classify / memory) is timed
and recorded under ``preprocessing:<label>`` in the shared node histogram, and
that a failing subtask records ``status="error"`` while the node still returns
its merged defaults (i.e. instrumentation is behaviour-preserving).
"""

from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

import src.services.agent._nodes_classify as nc


async def _run_with_spies(rag, classify, memory):
    """Invoke preprocessing_node with the three subtasks + the metric helper
    patched. Returns (merged_result, list_of_(node, status) recorded)."""
    recorded: list[tuple[str, str]] = []

    def _spy(node, status, duration):
        assert isinstance(duration, float) and duration >= 0.0
        recorded.append((node, status))

    with (
        patch.object(nc, "rag_node", rag),
        patch.object(nc, "_classify_core", classify),
        patch.object(nc, "memory_retrieval_node", memory),
        patch.object(nc, "record_node_duration", _spy),
        patch.object(nc, "tag_trace_intent", lambda *_a, **_k: None),
    ):
        result = await nc.preprocessing_node({}, {})
    return result, recorded


async def test_records_each_subtask_success():
    async def rag(_s, _c):
        return {"retrieved_contexts": [{"text": "x"}]}

    async def classify(_s, _c):
        return {"intent": "research", "intent_confidence": 0.9}

    async def memory(_s, _c):
        return {"user_memories": ["m"]}

    result, recorded = await _run_with_spies(rag, classify, memory)

    assert set(recorded) == {
        ("preprocessing:rag", "success"),
        ("preprocessing:classify", "success"),
        ("preprocessing:memory", "success"),
    }
    # Subtask results still merge into the node output.
    assert result["intent"] == "research"
    assert result["retrieved_contexts"] == [{"text": "x"}]
    assert result["user_memories"] == ["m"]


async def test_failing_subtask_records_error_and_falls_back():
    async def rag(_s, _c):
        raise RuntimeError("retrieval down")

    async def classify(_s, _c):
        return {"intent": "writing", "intent_confidence": 0.8}

    async def memory(_s, _c):
        return {"user_memories": []}

    result, recorded = await _run_with_spies(rag, classify, memory)

    assert ("preprocessing:rag", "error") in recorded
    assert ("preprocessing:classify", "success") in recorded
    # Failed rag subtask falls back to the default (empty contexts), other
    # subtasks still applied — existing merge behaviour is preserved.
    assert result["retrieved_contexts"] == []
    assert result["intent"] == "writing"


async def test_preprocessing_increments_turn_index_once():
    async def empty(_s, _c):
        return {}

    recorded: list[tuple[str, str]] = []
    with (
        patch.object(nc, "rag_node", empty),
        patch.object(nc, "_classify_core", empty),
        patch.object(nc, "memory_retrieval_node", empty),
        patch.object(
            nc, "record_node_duration", lambda *_a: recorded.append(("x", "x"))
        ),
        patch.object(nc, "tag_trace_intent", lambda *_a, **_k: None),
    ):
        result = await nc.preprocessing_node({"turn_index": 7}, {})

    assert result["turn_index"] == 8


def test_checkpoint_pruning_removes_only_complete_old_turns():
    messages = []
    for index in range(nc.MAX_CHECKPOINT_USER_TURNS + 3):
        messages.extend(
            [
                HumanMessage(content=f"q{index}", id=f"u{index}"),
                AIMessage(content=f"a{index}", id=f"a{index}"),
            ]
        )

    removals = nc._prune_checkpoint_history(messages)

    assert all(isinstance(message, RemoveMessage) for message in removals)
    assert [message.id for message in removals] == [
        "u0",
        "a0",
        "u1",
        "a1",
        "u2",
        "a2",
    ]
