from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_resolve_cli_auth_uses_explicit_values_before_saved_file(
    tmp_path: Path,
) -> None:
    from src.cli.auth_loader import resolve_cli_auth

    auth_file = tmp_path / "nous-auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "token": "file-token",
                "organization_id": "file-org",
            }
        )
    )

    resolved = resolve_cli_auth(
        token="flag-token",
        organization_id="",
        auth_file=str(auth_file),
    )

    assert resolved.token == "flag-token"
    assert resolved.organization_id == "file-org"
    assert resolved.source_path == auth_file


def test_write_cli_auth_payload_persists_to_default_auth_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cli.auth_loader import write_cli_auth_payload

    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))

    path = write_cli_auth_payload(
        {
            "token": "persisted-token",
            "organization_id": "persisted-org",
            "user_email": "admin@multimodal-rag.com",
        }
    )

    assert path == home_dir / ".nous" / "auth.json"
    payload = json.loads(path.read_text())
    assert payload["token"] == "persisted-token"
    assert payload["organization_id"] == "persisted-org"
    assert payload["user_email"] == "admin@multimodal-rag.com"


def test_resolve_cli_auth_finds_latest_downloaded_frontend_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cli.auth_loader import resolve_cli_auth

    home_dir = tmp_path / "home"
    downloads_dir = home_dir / "Downloads"
    downloads_dir.mkdir(parents=True)

    older_export = downloads_dir / "nous-auth.json"
    older_export.write_text(
        json.dumps(
            {
                "token": "older-token",
                "organization_id": "older-org",
            }
        )
    )

    newer_export = downloads_dir / "nous-auth (1).json"
    newer_export.write_text(
        json.dumps(
            {
                "token": "newer-token",
                "organization_id": "newer-org",
            }
        )
    )

    monkeypatch.setenv("HOME", str(home_dir))
    import os
    import time
    now = time.time()
    os.utime(older_export, (now - 10, now - 10))
    os.utime(newer_export, (now, now))

    resolved = resolve_cli_auth(token="", organization_id="")

    assert resolved.token == "newer-token"
    assert resolved.organization_id == "newer-org"
    assert resolved.source_path == newer_export


@pytest.mark.asyncio
async def test_async_main_uses_saved_auth_when_flags_are_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cli import agent_chat_cli as cli

    home_dir = tmp_path / "home"
    downloads_dir = home_dir / "Downloads"
    downloads_dir.mkdir(parents=True)
    export_file = downloads_dir / "nous-auth.json"
    export_file.write_text(
        json.dumps(
            {
                "token": "downloaded-token",
                "organization_id": "downloaded-org",
            }
        )
    )
    monkeypatch.setenv("HOME", str(home_dir))

    captured_kwargs: dict[str, object] = {}

    class FakeAgentAPIClient:
        def __init__(self, **kwargs: object) -> None:
            captured_kwargs.update(kwargs)

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(cli, "AgentAPIClient", FakeAgentAPIClient)

    exit_code = await cli.async_main(
        base_url="https://example.test",
        input_hook=lambda _: (_ for _ in ()).throw(EOFError()),
        output_hook=lambda _: None,
    )

    assert exit_code == 0
    assert captured_kwargs["token"] == "downloaded-token"
    assert captured_kwargs["organization_id"] == "downloaded-org"
