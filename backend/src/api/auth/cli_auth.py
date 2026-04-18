from __future__ import annotations

from datetime import UTC, datetime
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from src.core.config import settings
from src.core.dependencies import get_current_user
from src.core.security import auth_rate_limiter
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
    request: Request,
    store: InMemoryCLIAuthSessionStore = Depends(get_cli_auth_session_store),
) -> dict[str, Any]:
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = await auth_rate_limiter.check_rate_limit(
        client_ip, prefix="cli_start"
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many CLI auth requests. Try again later.",
            headers={"Retry-After": str(max(1, retry_after))},
        )
    await auth_rate_limiter.record_attempt(client_ip, prefix="cli_start")
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
    http_request: Request,
    store: InMemoryCLIAuthSessionStore = Depends(get_cli_auth_session_store),
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    organization_id = str(current_user.organization_id or "")
    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated user must belong to an organization",
        )

    # Pass through the caller's Supabase access token to the CLI client
    auth_header = http_request.headers.get("Authorization", "")
    supabase_token = auth_header.removeprefix("Bearer ").strip()
    if not supabase_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )

    credential_payload = {
        "token": supabase_token,
        "organization_id": organization_id,
        "user_email": str(current_user.email),
        "expires_at": _serialize_datetime(
            datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        ),
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
