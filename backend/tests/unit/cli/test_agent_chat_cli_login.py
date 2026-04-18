from __future__ import annotations


def test_main_login_subcommand_invokes_login_main(
    monkeypatch,
) -> None:
    from src.cli import agent_chat_cli as cli

    captured_kwargs: dict[str, object] = {}

    async def fake_login_main(**kwargs: object) -> int:
      captured_kwargs.update(kwargs)
      return 0

    monkeypatch.setattr(cli, "login_main", fake_login_main)

    exit_code = cli.main(
        [
            "login",
            "--base-url",
            "https://example.test",
            "--auth-file",
            "/tmp/nous-auth.json",
        ]
    )

    assert exit_code == 0
    assert captured_kwargs["base_url"] == "https://example.test"
    assert captured_kwargs["auth_file"] == "/tmp/nous-auth.json"
