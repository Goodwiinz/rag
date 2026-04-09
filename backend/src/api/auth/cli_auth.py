from __future__ import annotations

from datetime import UTC, datetime
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.core.config import settings
from src.core.dependencies import get_current_user
from src.core.security import create_access_token
from src.services.auth.cli_auth_sessions import InMemoryCLIAuthSessionStore

router = APIRouter(prefix="/cli-auth", tags=["cli-auth"])

_POLL_INTERVAL_SECONDS = 2
_session_store = InMemoryCLIAuthSessionStore()


class CLIAuthApproveRequest(BaseModel):
    session_id: str
    verification_code: str


def get_cli_auth_session_store() -> InMemoryCLIAuthSessionStore:
    return _session_store


def _frontend_base_url() -> str:
    return settings.cors_origins_list[0].rstrip("/")


def _serialize_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@router.post("/start")
async def start_cli_auth(
    store: InMemoryCLIAuthSessionStore = Depends(get_cli_auth_session_store),
) -> dict[str, Any]:
    session = store.create_session()
    browser_url = (
        f"{_frontend_base_url()}/cli-auth"
        f"?session_id={session.session_id}&code={session.verification_code}"
    )
    return {
        "session_id": session.session_id,
        "verification_code": session.verification_code,
        "browser_url": browser_url,
        "poll_token": session.poll_token,
        "expires_at": _serialize_datetime(session.expires_at),
        "poll_interval_seconds": _POLL_INTERVAL_SECONDS,
    }


@router.get("/status/{session_id}")
async def get_cli_auth_status(
    session_id: str,
    poll_token: str = Query(...),
    store: InMemoryCLIAuthSessionStore = Depends(get_cli_auth_session_store),
) -> dict[str, Any]:
    session = store.get_session(session_id, poll_token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CLI auth session not found",
        )

    body: dict[str, Any] = {
        "session_id": session.session_id,
        "status": session.status,
        "expires_at": _serialize_datetime(session.expires_at),
    }
    if session.credential_payload:
        body.update(session.credential_payload)
    return body


@router.post("/approve")
async def approve_cli_auth(
    request: CLIAuthApproveRequest,
    store: InMemoryCLIAuthSessionStore = Depends(get_cli_auth_session_store),
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    organization_id = str(current_user.organization_id or "")
    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated user must belong to an organization",
        )

    role = getattr(current_user, "role", "")
    role_value = role.value if hasattr(role, "value") else str(role)
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    credential_payload = {
        "token": create_access_token(
            data={
                "sub": str(current_user.id),
                "email": current_user.email,
                "organization_id": organization_id,
                "role": role_value,
                "source": "cli",
            },
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        ),
        "organization_id": organization_id,
        "user_email": str(current_user.email),
        "expires_at": _serialize_datetime(expires_at),
    }
    session = store.approve_session(
        request.session_id,
        verification_code=request.verification_code,
        user_id=str(current_user.id),
        credential_payload=credential_payload,
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CLI auth session not found",
        )

    return {
        "session_id": session.session_id,
        "status": session.status,
        **credential_payload,
    }
