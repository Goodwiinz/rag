"""The /chat client resends the FULL conversation each turn. LangGraph's
``add_messages`` reducer dedupes only by message ``.id`` — so if the endpoint
rebuilds each prior user turn as a ``HumanMessage`` with no id (fresh random id
per request), every turn re-appends the whole history into the checkpoint's
messages channel: O(n^2) growth the compactor never prunes.

``build_user_history_messages`` assigns deterministic ids (client idempotency
key, else a (thread_id, position) derivation) so a resent history no-ops in the
reducer and only the new turn appends. These tests pin that: pure Python, no
DB / no network — just the reducer applied to the messages the endpoint builds.
"""

from __future__ import annotations

from types import SimpleNamespace

from langgraph.graph import add_messages

from src.services.agent.agent_execution_service import build_user_history_messages


def _user(content: str, cmid=None) -> SimpleNamespace:
    return SimpleNamespace(role="user", content=content, client_message_id=cmid)


def test_resent_history_does_not_duplicate_in_channel() -> None:
    """Turn 2 resends turn 1's history — the channel must not grow it twice."""
    thread_id = "thread-abc"

    # Turn 1: client sends [msg1]. It lands in the (empty) checkpoint channel.
    turn1 = [_user("hello")]
    channel = add_messages([], build_user_history_messages(turn1, thread_id))
    assert len(channel) == 1

    # Turn 2: client resends [msg1, msg2] (full conversation).
    turn2 = [_user("hello"), _user("how are you")]
    channel = add_messages(channel, build_user_history_messages(turn2, thread_id))

    # msg1 must dedupe (same id), only msg2 appends → 2, not 3.
    assert len(channel) == 2
    assert [m.content for m in channel] == ["hello", "how are you"]


def test_client_message_id_drives_dedup() -> None:
    """A client-supplied idempotency key anchors identity across resends."""
    thread_id = "thread-xyz"
    cmid = "11111111-1111-1111-1111-111111111111"

    turn1 = [_user("q", cmid=cmid)]
    channel = add_messages([], build_user_history_messages(turn1, thread_id))

    turn2 = [_user("q", cmid=cmid), _user("q2")]
    channel = add_messages(channel, build_user_history_messages(turn2, thread_id))

    assert len(channel) == 2


def test_original_cmid_turn_converges_with_cmid_less_resend() -> None:
    """Audit finding B (live trace thread e3c56cef, 2026-08-11): the real /chat
    client only attaches ``client_message_id`` to the newest turn in a request —
    a turn resent later as history arrives WITHOUT it. The old code preferred
    cmid when present, so turn 1's message got an id from its cmid (uuid4) while
    the SAME turn resent on turn 2 (now cmid-less) got a *different* positional
    fallback id (uuid5) — two ids, so the reducer kept both copies of turn 1.
    Ids must now be positional-only so the same turn converges regardless of
    whether cmid happens to be attached on a given request.
    """
    thread_id = "thread-real"
    cmid1 = "11111111-1111-1111-1111-111111111111"
    cmid2 = "22222222-2222-2222-2222-222222222222"

    # Turn 1: only message in the request, carries its cmid (as the real
    # client does for the newest turn).
    turn1 = [_user("hello", cmid=cmid1)]
    channel = add_messages([], build_user_history_messages(turn1, thread_id))
    assert len(channel) == 1

    # Turn 2: full history resent — turn 1's message now WITHOUT cmid (as the
    # real client actually behaves), plus the new turn WITH cmid.
    turn2 = [_user("hello", cmid=None), _user("how are you", cmid=cmid2)]
    channel = add_messages(channel, build_user_history_messages(turn2, thread_id))

    # Must converge to 2 messages, not 3 — turn 1 must not duplicate.
    assert len(channel) == 2
    assert [m.content for m in channel] == ["hello", "how are you"]


def test_naive_no_id_construction_regresses() -> None:
    """Guard-rail: the OLD (no-id) construction is what grows unboundedly, so a
    regression back to it would flip this assert and fail loudly."""
    from langchain_core.messages import HumanMessage

    def naive(msgs):
        return [HumanMessage(content=m.content) for m in msgs if m.role == "user"]

    turn1 = [_user("hello")]
    channel = add_messages([], naive(turn1))
    turn2 = [_user("hello"), _user("how are you")]
    channel = add_messages(channel, naive(turn2))

    # No stable ids → the resent turn 1 is re-appended → 3, not 2.
    assert len(channel) == 3
