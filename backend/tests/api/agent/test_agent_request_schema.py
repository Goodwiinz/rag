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


# --------------------------------------------------------------------------- #
# Edit-and-resend: the replacement must carry a FRESH client_message_id
# --------------------------------------------------------------------------- #


def test_edit_reusing_the_superseded_cmid_is_rejected():
    """422 at the edge, because the failure downstream is silent and total.

    The replacement INSERT hits ``ON CONFLICT (thread_id, client_message_id)
    DO NOTHING`` and dedups onto the very row being edited; the tombstone sweep
    would then mark its own replacement superseded and the turn would vanish
    from every reader.
    """
    cmid = uuid4()
    with pytest.raises(ValidationError) as exc:
        AgentExecuteRequest(
            messages=[
                AgentMessage(role="user", content="edited", client_message_id=cmid)
            ],
            thread_id=str(uuid4()),
            supersedes_client_message_id=cmid,
        )
    assert "edited turn must carry a fresh client_message_id" in str(exc.value)


def test_edit_with_a_fresh_cmid_is_accepted():
    old, new = uuid4(), uuid4()
    request = AgentExecuteRequest(
        messages=[AgentMessage(role="user", content="edited", client_message_id=new)],
        thread_id=str(uuid4()),
        supersedes_client_message_id=old,
    )
    assert request.supersedes_client_message_id == old
    assert request.messages[0].client_message_id == new


def test_edit_without_a_cmid_on_the_new_turn_is_allowed():
    """No key to collide with; the legacy no-idempotency path still works."""
    request = AgentExecuteRequest(
        messages=[AgentMessage(role="user", content="edited")],
        thread_id=str(uuid4()),
        supersedes_client_message_id=uuid4(),
    )
    assert request.messages[0].client_message_id is None


def test_a_non_edit_request_is_untouched_by_the_validator():
    cmid = uuid4()
    request = AgentExecuteRequest(
        messages=[AgentMessage(role="user", content="hi", client_message_id=cmid)],
        thread_id=str(uuid4()),
    )
    assert request.supersedes_client_message_id is None
    assert request.messages[0].client_message_id == cmid
