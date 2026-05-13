from __future__ import annotations

from uuid import UUID

from src.cli.agent_api_client import build_execute_payload


def test_user_message_gets_uuid() -> None:
    payload = build_execute_payload(messages=[{"role": "user", "content": "hi"}])
    cmid = payload["messages"][0]["client_message_id"]
    UUID(cmid)  # must parse — raises ValueError if not a valid UUID


def test_assistant_message_has_no_uuid() -> None:
    payload = build_execute_payload(
        messages=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hey"},
        ]
    )
    assert "client_message_id" not in payload["messages"][1]


def test_existing_uuid_is_preserved() -> None:
    existing = "550e8400-e29b-41d4-a716-446655440000"
    payload = build_execute_payload(
        messages=[{"role": "user", "content": "hi", "client_message_id": existing}]
    )
    assert payload["messages"][0]["client_message_id"] == existing
