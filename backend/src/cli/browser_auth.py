from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
import webbrowser

from src.cli.auth_loader import ResolvedCLIAuth, save_cli_auth


@dataclass(frozen=True)
class CLIBrowserAuthResult:
    token: str
    organization_id: str
    user_email: str = ""
    source_path: Path | None = None


async def login_via_browser(
    *,
    client: object,
    output_hook: Callable[[str], None],
    open_browser: Callable[[str], bool] = webbrowser.open,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    auth_path: Path | None = None,
) -> CLIBrowserAuthResult | None:
    start_response = await client.start_cli_auth()
    browser_url = str(start_response["browser_url"])
    session_id = str(start_response["session_id"])
    verification_code = str(start_response["verification_code"])
    poll_token = str(start_response["poll_token"])
    poll_interval_seconds = float(start_response.get("poll_interval_seconds") or 2)

    output_hook("auth> opening browser for NOUS CLI sign-in...")
    try:
        browser_opened = open_browser(browser_url)
    except Exception:
        browser_opened = False
    if not browser_opened:
        output_hook("auth> browser open failed, use the URL below manually.")
    output_hook(f"auth> visit: {browser_url}")
    output_hook(f"auth> code: {verification_code}")
    output_hook("auth> waiting for approval...")

    while True:
        if hasattr(client, "poll_cli_auth_status"):
            status_response = await client.poll_cli_auth_status(session_id, poll_token)
        else:
            status_response = await client.get_cli_auth_status(session_id, poll_token)
        status = str(status_response.get("status") or "pending")
        if status == "pending":
            await sleep(poll_interval_seconds)
            continue

        if status == "approved":
            token = str(status_response.get("token") or "")
            organization_id = str(status_response.get("organization_id") or "")
            user_email = str(status_response.get("user_email") or "")
            expires_at = str(status_response.get("expires_at") or "")
            saved_path = save_cli_auth(
                token=token,
                organization_id=organization_id,
                user_email=user_email,
                expires_at=expires_at,
                auth_path=auth_path,
            )
            if user_email:
                output_hook(f"auth> signed in as {user_email}")
            else:
                output_hook("auth> signed in")
            return CLIBrowserAuthResult(
                token=token,
                organization_id=organization_id,
                user_email=user_email,
                source_path=saved_path,
            )

        if status == "denied":
            output_hook("auth> login denied in browser")
            return None
        if status == "expired":
            output_hook("auth> login session expired")
            return None
        if status == "cancelled":
            output_hook("auth> login cancelled")
            return None

        output_hook(f"auth> login failed with unexpected status: {status}")
        return None


async def perform_browser_login(
    *,
    api_client: object,
    output_hook: Callable[[str], None],
    open_browser: Callable[[str], bool] = webbrowser.open,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    auth_path: Path | None = None,
) -> ResolvedCLIAuth:
    result = await login_via_browser(
        client=api_client,
        output_hook=output_hook,
        open_browser=open_browser,
        sleep=sleep,
        auth_path=auth_path,
    )
    if result is None:
        return ResolvedCLIAuth()
    return ResolvedCLIAuth(
        token=result.token,
        organization_id=result.organization_id,
        source_path=result.source_path,
    )
