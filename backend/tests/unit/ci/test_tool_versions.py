"""Contract tests for scripts/ci/check_tool_versions.py.

Pre-commit must invoke the same repository-owned checks CI runs — not
its own pinned mirror copies, which historically drifted years behind
the CI pins (black 23.11 vs 26.5, flake8 vs ruff, eslint 8 vs 9). The
checker fails when .pre-commit-config.yaml duplicates a CI-pinned tool
through a remote mirror repo instead of a local hook.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "check_tool_versions.py"

WORKFLOW_SNIPPET = textwrap.dedent(
    """
    jobs:
      lint-backend:
        steps:
          - name: Install lint tools (current pins)
            run: pip install ruff==0.15.15 black==26.5.1 isort==5.13.2 mypy==1.7.1
    """
)


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
    )


def _make_root(tmp_path: Path, precommit: str) -> Path:
    root = tmp_path / "project"
    workflow_dir = root / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "test-pipeline.yml").write_text(
        WORKFLOW_SNIPPET, encoding="utf-8"
    )
    (root / ".pre-commit-config.yaml").write_text(
        textwrap.dedent(precommit), encoding="utf-8"
    )
    return root


def test_parses_ci_pins_from_workflow(tmp_path: Path) -> None:
    root = _make_root(tmp_path, "repos: []\n")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--print-pins"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "ruff==0.15.15" in result.stdout
    assert "black==26.5.1" in result.stdout
    assert "isort==5.13.2" in result.stdout
    assert "mypy==1.7.1" in result.stdout


def test_fails_on_remote_mirror_of_ci_tool(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        """
        repos:
          - repo: https://github.com/psf/black
            rev: 23.11.0
            hooks:
              - id: black
        """,
    )
    result = _run(root)
    assert result.returncode == 1
    assert "black" in result.stdout


def test_fails_on_mirror_of_tool_ci_does_not_even_run(tmp_path: Path) -> None:
    # flake8 duplicates ruff's job with different rules — also a drift source.
    root = _make_root(
        tmp_path,
        """
        repos:
          - repo: https://github.com/pycqa/flake8
            rev: 6.1.0
            hooks:
              - id: flake8
        """,
    )
    result = _run(root)
    assert result.returncode == 1
    assert "flake8" in result.stdout


def test_passes_with_local_hooks_only(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        """
        repos:
          - repo: https://github.com/pre-commit/pre-commit-hooks
            rev: v4.4.0
            hooks:
              - id: trailing-whitespace
          - repo: local
            hooks:
              - id: ruff
                name: ruff (same command as CI)
                entry: python3 -m ruff check
                language: system
        """,
    )
    result = _run(root)
    assert result.returncode == 0, result.stdout + result.stderr


def test_real_repo_precommit_has_no_drifting_mirrors() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(REPO_ROOT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
