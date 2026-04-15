from __future__ import annotations


def test_inmemory_store_round_trips_pending_and_approved_sessions() -> None:
    from src.services.auth.cli_auth_sessions import InMemoryCLIAuthSessionStore

    store = InMemoryCLIAuthSessionStore()
    session = store.create_session()

    fetched = store.get_session(session.session_id, session.poll_token)
    assert fetched is not None
    assert fetched.status == "pending"
    assert fetched.session_id == session.session_id
    assert fetched.poll_token == session.poll_token
    assert fetched.verification_code == session.verification_code

    store.approve_session(
        session.session_id,
        verification_code=session.verification_code,
        user_id="user-1",
        credential_payload={"token": "tok", "organization_id": "org-1"},
    )

    approved = store.get_session(session.session_id, session.poll_token)
    assert approved is not None
    assert approved.status == "approved"
    assert approved.user_id == "user-1"
    assert approved.credential_payload["token"] == "tok"
    assert approved.credential_payload["organization_id"] == "org-1"


def test_inmemory_store_rejects_invalid_verification_code() -> None:
    from src.services.auth.cli_auth_sessions import InMemoryCLIAuthSessionStore

    store = InMemoryCLIAuthSessionStore()
    session = store.create_session()

    result = store.approve_session(
        session.session_id,
        verification_code="bad-code",
        user_id="user-1",
        credential_payload={"token": "tok", "organization_id": "org-1"},
    )

    assert result is None

    fetched = store.get_session(session.session_id, session.poll_token)
    assert fetched is not None
    assert fetched.status == "pending"
    assert fetched.user_id is None


def test_inmemory_store_enforces_one_way_lifecycle() -> None:
    from src.services.auth.cli_auth_sessions import InMemoryCLIAuthSessionStore

    store = InMemoryCLIAuthSessionStore()

    approved_session = store.create_session()
    approved = store.approve_session(
        approved_session.session_id,
        verification_code=approved_session.verification_code,
        user_id="user-1",
        credential_payload={"token": "tok", "organization_id": "org-1"},
    )
    assert approved is not None
    assert approved.status == "approved"

    assert store.deny_session(approved_session.session_id) is None
    assert store.expire_session(approved_session.session_id) is None

    denied_session = store.create_session()
    denied = store.deny_session(denied_session.session_id)
    assert denied is not None
    assert denied.status == "denied"

    assert store.approve_session(
        denied_session.session_id,
        verification_code=denied_session.verification_code,
        user_id="user-2",
        credential_payload={"token": "tok-2", "organization_id": "org-2"},
    ) is None
    assert store.expire_session(denied_session.session_id) is None


def test_inmemory_store_rejects_invalid_poll_token() -> None:
    from src.services.auth.cli_auth_sessions import InMemoryCLIAuthSessionStore

    store = InMemoryCLIAuthSessionStore()
    session = store.create_session()

    assert store.get_session(session.session_id, "wrong-token") is None


def test_inmemory_store_can_deny_and_expire_sessions() -> None:
    from src.services.auth.cli_auth_sessions import InMemoryCLIAuthSessionStore

    store = InMemoryCLIAuthSessionStore()
    session = store.create_session()

    denied = store.deny_session(session.session_id)
    assert denied is not None
    assert denied.status == "denied"

    assert store.expire_session(session.session_id) is None
