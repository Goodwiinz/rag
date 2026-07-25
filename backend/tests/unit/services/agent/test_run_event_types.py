"""Contract tests for the versioned run-event vocabulary (Hermes runtime).

The envelope + payload models in ``run_event_types`` / ``schemas.agent_run_events``
are the public wire contract for `/api/v1/agent/runs/{id}/events`. These tests
pin the invariants the design demands:

- every public type has a payload model and JSON-serializes through the
  versioned envelope;
- payloads are bounded (delta text cap, total byte cap) and display-safe
  (tool args run through redact_tool_args; failures expose code + client-safe
  message only);
- unknown event types parse forward-compatibly (sequence accounting must not
  break when an older client meets a newer server);
- LangGraph callback names never appear in the public vocabulary.
"""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.agent_run_events import AgentRunEventEnvelope
from src.services.agent.run_event_types import (
    MAX_DELTA_TEXT_CHARS,
    MAX_PAYLOAD_BYTES,
    PAYLOAD_MODELS,
    TERMINAL_RUN_EVENTS,
    PayloadTooLargeError,
    RunEventType,
    validate_payload,
)

pytestmark = pytest.mark.unit


def make_event(event_type: str, payload: dict, seq: int = 12) -> dict:
    return {
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "run_id": str(uuid.uuid4()),
        "conversation_id": str(uuid.uuid4()),
        "thread_id": str(uuid.uuid4()),
        "message_id": None,
        "seq": seq,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


def test_public_vocabulary_is_exactly_the_design_set() -> None:
    assert {t.value for t in RunEventType} == {
        "run.created",
        "run.started",
        "run.stopping",
        "assistant.delta",
        "retrieval.context",
        "plan.updated",
        "reflection.completed",
        "tool.started",
        "tool.completed",
        "approval.required",
        "approval.resolved",
        "usage.updated",
        "run.completed",
        "run.failed",
        "run.cancelled",
    }


def test_terminal_events_are_the_three_terminal_outcomes() -> None:
    assert TERMINAL_RUN_EVENTS == {
        RunEventType.RUN_COMPLETED,
        RunEventType.RUN_FAILED,
        RunEventType.RUN_CANCELLED,
    }


def test_every_type_has_a_payload_model() -> None:
    assert set(PAYLOAD_MODELS) == set(RunEventType)


def test_no_langgraph_callback_names_leak_into_the_vocabulary() -> None:
    for name in ("on_chat_model_stream", "on_tool_start", "on_tool_end", "token"):
        assert name not in {t.value for t in RunEventType}


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


def test_delta_envelope_is_versioned_and_scoped() -> None:
    event = make_event(
        "assistant.delta", validate_payload("assistant.delta", {"text": "hello"})
    )
    body = AgentRunEventEnvelope.model_validate(event).model_dump(mode="json")
    assert body["version"] == 1
    assert body["type"] == "assistant.delta"
    assert body["seq"] > 0
    assert body["payload"] == {"text": "hello"}


def test_envelope_rejects_nonpositive_sequence() -> None:
    with pytest.raises(ValidationError):
        AgentRunEventEnvelope.model_validate(make_event("run.started", {}, seq=0))


def test_unknown_event_type_parses_forward_compatibly() -> None:
    event = make_event("workspace.migrated", {"anything": True}, seq=7)
    envelope = AgentRunEventEnvelope.model_validate(event)
    assert envelope.type == "workspace.migrated"
    assert envelope.seq == 7


def test_every_known_type_round_trips_through_the_envelope() -> None:
    samples: dict[RunEventType, dict] = {
        RunEventType.RUN_CREATED: {},
        RunEventType.RUN_STARTED: {},
        RunEventType.RUN_STOPPING: {"reason": "user_requested"},
        RunEventType.ASSISTANT_DELTA: {"text": "chunk"},
        RunEventType.RETRIEVAL_CONTEXT: {
            "items": [{"document_id": str(uuid.uuid4()), "title": "Paper"}]
        },
        RunEventType.PLAN_UPDATED: {"steps": [{"title": "Search", "status": "done"}]},
        RunEventType.REFLECTION_COMPLETED: {"summary": "looked good"},
        RunEventType.TOOL_STARTED: {
            "tool_call_id": "call_1",
            "name": "search_documents",
            "args": {"query": "attention"},
        },
        RunEventType.TOOL_COMPLETED: {
            "tool_call_id": "call_1",
            "name": "search_documents",
            "status": "success",
        },
        RunEventType.APPROVAL_REQUIRED: {
            "approval_id": str(uuid.uuid4()),
            "tool_call_id": "call_2",
            "name": "ingest_arxiv_paper",
            "args": {"paper_id": "2401.00001"},
        },
        RunEventType.APPROVAL_RESOLVED: {
            "approval_id": str(uuid.uuid4()),
            "decision": "approved",
        },
        RunEventType.USAGE_UPDATED: {"input_tokens": 10, "output_tokens": 20},
        RunEventType.RUN_COMPLETED: {"assistant_message_id": str(uuid.uuid4())},
        RunEventType.RUN_FAILED: {"code": "graph_error", "message": "The run failed."},
        RunEventType.RUN_CANCELLED: {"reason": "user_requested"},
    }
    assert set(samples) == set(RunEventType)
    for event_type, payload in samples.items():
        validated = validate_payload(event_type, payload)
        envelope = AgentRunEventEnvelope.model_validate(
            make_event(event_type.value, validated)
        )
        assert envelope.model_dump(mode="json")["type"] == event_type.value


# ---------------------------------------------------------------------------
# Bounds and redaction
# ---------------------------------------------------------------------------


def test_delta_text_is_capped() -> None:
    validated = validate_payload(
        "assistant.delta", {"text": "x" * (MAX_DELTA_TEXT_CHARS + 500)}
    )
    assert len(validated["text"]) == MAX_DELTA_TEXT_CHARS


def test_payload_byte_cap_is_enforced() -> None:
    # Passes the per-field caps (50 items, 500-char titles) but blows the
    # total byte budget — the cap must catch what the models admit.
    huge = {"items": [{"document_id": str(uuid.uuid4()), "title": "t" * 500}] * 50}
    with pytest.raises(PayloadTooLargeError):
        validate_payload("retrieval.context", huge)
    assert MAX_PAYLOAD_BYTES <= 64 * 1024


def test_tool_args_are_redacted() -> None:
    validated = validate_payload(
        "tool.started",
        {
            "tool_call_id": "call_9",
            "name": "create_note",
            "args": {"contact": "reach me at alice@example.com"},
        },
    )
    assert "alice@example.com" not in str(validated)
    assert "<email>" in validated["args"]["contact"]


def test_failure_payload_is_code_plus_client_safe_message_only() -> None:
    with pytest.raises(ValidationError):
        validate_payload(
            "run.failed",
            {
                "code": "graph_error",
                "message": "failed",
                "stack_trace": "Traceback (most recent call last): ...",
            },
        )


def test_unknown_type_payload_is_rejected_by_validate() -> None:
    with pytest.raises(ValueError):
        validate_payload("not.a.type", {})
