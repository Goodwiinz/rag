"""Trajectory rule upload must target graph roots only."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

import pytest

pytestmark = pytest.mark.unit


def test_documented_direct_entrypoint_help_is_importable() -> None:
    from tests.eval import upload_trajectory_rules as uploader

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, str(uploader.__file__), "--help"],
        cwd=uploader.REPO,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


def test_trajectory_rules_use_the_exact_graph_root_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.eval import upload_trajectory_rules as uploader

    posted_bodies: list[dict[str, Any]] = []

    monkeypatch.setattr(uploader, "_load_env", lambda: ("test-key", "https://test"))
    monkeypatch.setattr(uploader, "_resolve_session_id", lambda *_args: "session-1")
    monkeypatch.setattr(uploader, "_existing_rules", lambda *_args: [])

    def request(
        method: str, _url: str, _api_key: str, body: dict[str, Any] | None = None
    ) -> dict[str, str]:
        assert method == "POST"
        assert body is not None
        posted_bodies.append(body)
        return {"id": "rule-1"}

    monkeypatch.setattr(uploader, "_request", request)
    monkeypatch.setattr(sys, "argv", ["upload_trajectory_rules.py"])

    assert uploader.main() == 0

    expected = (
        'and(eq(is_root, true), and(eq(metadata_key, "trace_source"), '
        'eq(metadata_value, "graph")))'
    )
    assert uploader.TRAJECTORY_ROOT_FILTER == expected
    assert uploader.TRAJECTORY_ROOT_FILTER != "eq(is_root, true)"
    assert [body["filter"] for body in posted_bodies] == [expected] * len(
        uploader.METRICS
    )
