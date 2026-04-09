from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_perform_browser_login_opens_browser_and_persists_auth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cli.browser_auth import perform_browser_login

    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))

    opened_urls: list[str] = []
    slept_for: list[float] = []
    rendered_output: list[str] = []

    class FakeCLIAuthClient:
        def __init__(self) -> None:
            self.status_calls = 0

        async def start_cli_auth(self) -> dict[str, object]:
            return {
                "session_id": "session-1",
                "verification_code": "ABCD-1234",
                "browser_url": "http://localhost:3000/cli-auth?session_id=session-1&code=ABCD-1234",
                "poll_token": "poll-1",
                "expires_at": "2026-03-27T12:34:56Z",
                "poll_interval_seconds": 2,
            }

        async def poll_cli_auth_status(
            self, session_id: str, poll_token: str
        ) -> dict[str, object]:
            self.status_calls += 1
            assert session_id == "session-1"
            assert poll_token == "poll-1"
            if self.status_calls == 1:
                return {"status": "pending"}
            return {
                "status": "approved",
                "token": "cli-token",
                "organization_id": "org-1",
                "user_email": "admin@multimodal-rag.com",
                "expires_at": "2026-03-27T20:34:56Z",
            }

    async def fake_sleep(seconds: float) -> None:
        slept_for.append(seconds)

    def fake_open_browser(url: str) -> bool:
        opened_urls.append(url)
        return True

    result = await perform_browser_login(
        api_client=FakeCLIAuthClient(),
        open_browser=fake_open_browser,
        sleep=fake_sleep,
        output_hook=rendered_output.append,
    )

    auth_file = home_dir / ".nous" / "auth.json"
    payload = json.loads(auth_file.read_text())

    assert result.token == "cli-token"
    assert result.organization_id == "org-1"
    assert result.source_path == auth_file
    assert payload["token"] == "cli-token"
    assert payload["organization_id"] == "org-1"
    assert payload["user_email"] == "admin@multimodal-rag.com"
    assert opened_urls == [
        "http://localhost:3000/cli-auth?session_id=session-1&code=ABCD-1234"
    ]
    assert slept_for == [2]
    assert any("opening browser" in line.lower() for line in rendered_output)
    assert any("signed in as admin@multimodal-rag.com" in line.lower() for line in rendered_output)


@pytest.mark.asyncio
async def test_perform_browser_login_survives_browser_open_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cli.browser_auth import perform_browser_login

    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))

    rendered_output: list[str] = []

    class FakeCLIAuthClient:
        async def start_cli_auth(self) -> dict[str, object]:
            return {
                "session_id": "session-2",
                "verification_code": "WXYZ-5678",
                "browser_url": "http://localhost:3000/cli-auth?session_id=session-2&code=WXYZ-5678",
                "poll_token": "poll-2",
                "poll_interval_seconds": 0,
            }

        async def poll_cli_auth_status(
            self, session_id: str, poll_token: str
        ) -> dict[str, object]:
            assert session_id == "session-2"
            assert poll_token == "poll-2"
            return {
                "status": "approved",
                "token": "cli-token-2",
                "organization_id": "org-2",
            }

    async def fake_sleep(_: float) -> None:
        return None

    resolved = await perform_browser_login(
        api_client=FakeCLIAuthClient(),
        open_browser=lambda _: (_ for _ in ()).throw(RuntimeError("no browser")),
        sleep=fake_sleep,
        output_hook=rendered_output.append,
    )

    assert resolved.token == "cli-token-2"
    assert resolved.organization_id == "org-2"
    assert any("browser open failed" in line.lower() for line in rendered_output)
    assert any("visit:" in line.lower() for line in rendered_output)
