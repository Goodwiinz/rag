"""Schema tests for AgentExecuteRequest / AgentMessage.

Verifies that ``client_message_id`` is accepted on user-role messages
and rejected on assistant-role messages, and that it round-trips as a
UUID after Pydantic validation.
"""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.api.agent.execute import AgentExecuteRequest, AgentMessage


def test_user_message_accepts_client_message_id():
    cmid = uuid4()
    msg = AgentMessage(role="user", content="hi", client_message_id=str(cmid))
    assert msg.client_message_id == cmid
    assert isinstance(msg.client_message_id, UUID)


def test_assistant_message_rejects_client_message_id():
    with pytest.raises(ValidationError):
        AgentMessage(role="assistant", content="hi", client_message_id=str(uuid4()))


def test_request_round_trips_client_message_id():
    cmid = uuid4()
    req = AgentExecuteRequest(
        messages=[AgentMessage(role="user", content="hi", client_message_id=str(cmid))],
    )
    assert req.messages[0].client_message_id == cmid
