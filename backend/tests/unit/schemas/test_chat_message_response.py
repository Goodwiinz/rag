from datetime import UTC, datetime
from uuid import uuid4

from src.schemas.chat import ChatMessageResponse


def _message_payload(**overrides: object) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "id": uuid4(),
        "thread_id": uuid4(),
        "content": "Find recent arXiv papers",
        "role": "user",
        "created_at": now,
        "updated_at": now,
        **overrides,
    }


def test_chat_message_response_serializes_client_message_id() -> None:
    client_message_id = uuid4()

    response = ChatMessageResponse.model_validate(
        _message_payload(client_message_id=client_message_id)
    )

    assert response.model_dump(mode="json")["client_message_id"] == str(
        client_message_id
    )


def test_chat_message_response_accepts_legacy_null_client_message_id() -> None:
    response = ChatMessageResponse.model_validate(
        _message_payload(client_message_id=None)
    )

    assert response.model_dump(mode="json")["client_message_id"] is None
