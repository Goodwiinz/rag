"""Contract tests for scripts/ci/changed_source_files.py.

The helper classifies files changed since a base ref into Python and
frontend TypeScript/JavaScript groups so CI ratchets can block new debt
on touched files only. Base selection must be explicit and trustworthy:
``--base`` wins, then ``PR_BASE_SHA``, then ``GITHUB_EVENT_BEFORE`` —
and an absent or all-zero base fails loudly instead of silently
diffing against the wrong thing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "changed_source_files.py"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "HOME": "/nonexistent-home",  # never read the user's gitconfig
    "PATH": "/usr/bin:/bin:/usr/local/bin",
}


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=GIT_ENV,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _write(repo: Path, relative: str, content: str = "x\n") -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _write(repo, "backend/src/existing.py")
    _write(repo, "frontend/src/existing.ts")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def _run(
    repo: Path,
    *args: str,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(GIT_ENV)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )


def _base_sha(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


def _commit_all(repo: Path, message: str = "change") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


class TestBaseSelection:
    def test_fails_clearly_without_any_base(self, repo: Path) -> None:
        result = _run(repo)
        assert result.returncode == 2
        assert "base" in result.stderr.lower()

    def test_rejects_all_zero_event_before(self, repo: Path) -> None:
        zeros = "0" * 40
        result = _run(repo, env_extra={"GITHUB_EVENT_BEFORE": zeros})
        assert result.returncode == 2
        assert "base" in result.stderr.lower()

    def test_rejects_unresolvable_base(self, repo: Path) -> None:
        result = _run(repo, "--base", "no-such-ref")
        assert result.returncode == 2

    def test_falls_back_to_pr_base_sha(self, repo: Path) -> None:
        base = _base_sha(repo)
        _write(repo, "backend/src/new.py")
        _commit_all(repo)
        result = _run(repo, "--kind", "python", env_extra={"PR_BASE_SHA": base})
        assert result.returncode == 0
        assert result.stdout.splitlines() == ["backend/src/new.py"]

    def test_falls_back_to_event_before(self, repo: Path) -> None:
        base = _base_sha(repo)
        _write(repo, "backend/src/new.py")
        _commit_all(repo)
        result = _run(repo, "--kind", "python", env_extra={"GITHUB_EVENT_BEFORE": base})
        assert result.returncode == 0
        assert result.stdout.splitlines() == ["backend/src/new.py"]

    def test_explicit_base_wins_over_env(self, repo: Path) -> None:
        base = _base_sha(repo)
        _write(repo, "backend/src/new.py")
        _commit_all(repo)
        # Bogus env values must be ignored when --base is given.
        result = _run(
            repo,
            "--base",
            base,
            "--kind",
            "python",
            env_extra={"PR_BASE_SHA": "not-a-ref", "GITHUB_EVENT_BEFORE": "0" * 40},
        )
        assert result.returncode == 0
        assert result.stdout.splitlines() == ["backend/src/new.py"]


class TestClassification:
    def test_separates_python_and_frontend(self, repo: Path) -> None:
        base = _base_sha(repo)
        _write(repo, "backend/src/service.py")
        _write(repo, "frontend/src/widget.tsx")
        _write(repo, "frontend/app/page.ts")
        _write(repo, "frontend/next.config.mjs")
        _write(repo, "docs/readme.md")
        _commit_all(repo)
        result = _run(repo, "--base", base)
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["python"] == ["backend/src/service.py"]
        assert sorted(payload["frontend"]) == [
            "frontend/app/page.ts",
            "frontend/next.config.mjs",
            "frontend/src/widget.tsx",
        ]

    def test_ignores_generated_frontend_types(self, repo: Path) -> None:
        base = _base_sha(repo)
        _write(repo, "frontend/src/types/generated/api.d.ts")
        _commit_all(repo)
        result = _run(repo, "--base", base, "--kind", "frontend")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_non_frontend_ts_is_not_frontend(self, repo: Path) -> None:
        base = _base_sha(repo)
        _write(repo, "tests/e2e/spec.ts")
        _commit_all(repo)
        result = _run(repo, "--base", base, "--kind", "frontend")
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestAddedDetection:
    def test_added_python_files_are_distinguished(self, repo: Path) -> None:
        base = _base_sha(repo)
        _write(repo, "backend/src/brand_new.py")
        (repo / "backend/src/existing.py").write_text("changed\n", encoding="utf-8")
        _commit_all(repo)
        result = _run(repo, "--base", base, "--kind", "python-added")
        assert result.returncode == 0
        assert result.stdout.splitlines() == ["backend/src/brand_new.py"]

    def test_json_output_includes_added_subset(self, repo: Path) -> None:
        base = _base_sha(repo)
        _write(repo, "backend/src/brand_new.py")
        (repo / "backend/src/existing.py").write_text("changed\n", encoding="utf-8")
        _commit_all(repo)
        result = _run(repo, "--base", base)
        payload = json.loads(result.stdout)
        assert payload["python_added"] == ["backend/src/brand_new.py"]
        assert sorted(payload["python"]) == [
            "backend/src/brand_new.py",
            "backend/src/existing.py",
        ]


class TestGitEdgeCases:
    def test_rename_reports_new_path_only(self, repo: Path) -> None:
        base = _base_sha(repo)
        _git(repo, "mv", "backend/src/existing.py", "backend/src/renamed.py")
        _commit_all(repo)
        result = _run(repo, "--base", base, "--kind", "python")
        assert result.returncode == 0
        assert result.stdout.splitlines() == ["backend/src/renamed.py"]

    def test_deleted_files_are_excluded(self, repo: Path) -> None:
        base = _base_sha(repo)
        (repo / "backend/src/existing.py").unlink()
        _commit_all(repo)
        result = _run(repo, "--base", base, "--kind", "python")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_handles_spaces_in_paths(self, repo: Path) -> None:
        base = _base_sha(repo)
        _write(repo, "frontend/src/with space.ts")
        _commit_all(repo)
        result = _run(repo, "--base", base, "--kind", "frontend")
        assert result.returncode == 0
        assert result.stdout.splitlines() == ["frontend/src/with space.ts"]

    def test_uncommitted_changes_are_included(self, repo: Path) -> None:
        # CI diffs base...HEAD, but local pre-commit use must also see
        # staged-but-uncommitted work; the contract is: committed + working tree.
        base = _base_sha(repo)
        _write(repo, "backend/src/wip.py")
        _git(repo, "add", "-A")
        result = _run(repo, "--base", base, "--kind", "python")
        assert result.returncode == 0
        assert "backend/src/wip.py" in result.stdout.splitlines()
