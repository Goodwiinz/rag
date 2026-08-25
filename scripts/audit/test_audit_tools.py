from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "scripts/audit/launch_audit.sh"
PARTITION_CHECK = ROOT / "scripts/audit/partition_check.py"


def run(
    *args: str | Path, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="audit tools ") as temp_dir:
        root = Path(temp_dir)
        origin = root / "origin.git"
        repo = root / "source repo"
        base = root / "audit base"

        run("git", "init", "--bare", origin)
        run("git", "init", repo)
        run("git", "config", "user.email", "audit@example.com", cwd=repo)
        run("git", "config", "user.name", "Audit Test", cwd=repo)
        (repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
        run("git", "add", "tracked.txt", cwd=repo)
        run("git", "commit", "-m", "initial", cwd=repo)
        run("git", "branch", "-M", "develop", cwd=repo)
        run("git", "remote", "add", "origin", origin, cwd=repo)
        run("git", "push", "-u", "origin", "develop", cwd=repo)

        def launch(slug: str) -> Path:
            result = run(
                LAUNCHER,
                "launch",
                "--repo",
                repo,
                "--ref",
                "develop",
                "--slug",
                slug,
                "--base",
                base,
            )
            session_id = next(
                line.split(":", 1)[1].strip()
                for line in result.stdout.splitlines()
                if line.startswith("session:")
            )
            return base / repo.name / session_id

        hook = repo / ".git/hooks/post-checkout"
        hook.write_text(
            '#!/bin/sh\nprintf tampered > "$(git rev-parse --show-toplevel)/tracked.txt"\n',
            encoding="utf-8",
        )
        hook.chmod(0o755)
        (repo / "tracked.txt").write_text("dirty one\n", encoding="utf-8")

        session = launch("smoke")
        worktree = session / "worktree"
        assert (worktree / "tracked.txt").read_text() == "clean\n"
        assert not (worktree / "AUDIT_HANDOFF.md").exists()
        assert (session / "AUDIT_HANDOFF.md").is_file()
        run(LAUNCHER, "verify", "--session", session, "--strict-primary")

        (repo / "tracked.txt").write_text("dirty two\n", encoding="utf-8")
        drift = run(
            LAUNCHER,
            "verify",
            "--session",
            session,
            "--strict-primary",
            check=False,
        )
        assert drift.returncode == 1 and "primary working state changed" in drift.stdout
        (repo / "tracked.txt").write_text("dirty one\n", encoding="utf-8")

        (worktree / "tracked.txt").write_text("mutated\n", encoding="utf-8")
        assert run(LAUNCHER, "clean", "--session", session, check=False).returncode == 1
        assert worktree.is_dir()
        (worktree / "tracked.txt").write_text("clean\n", encoding="utf-8")
        (worktree / "empty-dir").mkdir()
        assert (
            run(LAUNCHER, "verify", "--session", session, check=False).returncode == 1
        )
        (worktree / "empty-dir").rmdir()
        run(LAUNCHER, "clean", "--session", session)

        archive = session.parent / "archive"
        first_receipt = archive / f"{session.name}.verify.receipt"
        assert (
            first_receipt.is_file() and "primary=unchanged" in first_receipt.read_text()
        )
        second = launch("second")
        run(LAUNCHER, "clean", "--session", second)
        assert first_receipt.is_file()
        assert (archive / f"{second.name}.verify.receipt").is_file()

        outside = root / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
        os.symlink(outside, repo / "escape")
        run("git", "add", "escape", cwd=repo)
        run("git", "commit", "-m", "add external link", cwd=repo)
        run("git", "push", "origin", "develop", cwd=repo)
        escaped = run(
            LAUNCHER,
            "launch",
            "--repo",
            repo,
            "--ref",
            "develop",
            "--slug",
            "external",
            "--base",
            base,
            check=False,
        )
        assert (
            escaped.returncode == 1
            and "symlink escapes audit worktree" in escaped.stderr
        )

        for name in ("a.py", "b.py"):
            (root / name).write_text(f"{name[0]} = 1\n", encoding="utf-8")
        partition = root / "partition.json"
        data = {
            "files": ["a.py", "b.py"],
            "scopes": [{"name": "one", "own": ["a.py"], "contract_files": ["b.py"]}],
        }
        partition.write_text(json.dumps(data), encoding="utf-8")
        incomplete = run(
            sys.executable, PARTITION_CHECK, partition, "--repo", root, check=False
        )
        assert (
            incomplete.returncode == 1
            and "scoped file(s) have no owner" in incomplete.stdout
        )
        data["scopes"] = [
            {"name": "one", "own": ["a.py", "b.py"], "contract_files": ["b.py"]}
        ]
        partition.write_text(json.dumps(data), encoding="utf-8")
        run(sys.executable, PARTITION_CHECK, partition, "--repo", root)


if __name__ == "__main__":
    main()
    print("audit tool self-check: OK")
