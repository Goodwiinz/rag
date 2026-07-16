#!/usr/bin/env python3
"""Fail when pre-commit duplicates CI-pinned tools via remote mirrors.

CI pins its lint toolchain in one pip-install line in
.github/workflows/test-pipeline.yml. Historically
.pre-commit-config.yaml carried its own *mirror* copies of those tools
(psf/black, pycqa/isort, pycqa/flake8, mirrors-mypy, mirrors-eslint)
whose revs drifted years behind the CI pins, so local commits and CI
disagreed about formatting and lint. The fix is structural: pre-commit
may only invoke repository-owned commands (``repo: local``) so there is
a single source of truth for tool versions.

Exit 1 lists each offending mirror; exit 0 means pre-commit cannot
drift from CI by construction. ``--print-pins`` prints the parsed CI
pins for humans and tests.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# Remote pre-commit repos that duplicate a CI-run (or CI-superseded) tool.
MIRROR_REPOS = {
    "github.com/psf/black": "black",
    "github.com/pycqa/black": "black",
    "github.com/pycqa/isort": "isort",
    "github.com/pycqa/flake8": "flake8 (superseded by ruff in CI)",
    "github.com/pre-commit/mirrors-mypy": "mypy",
    "github.com/pre-commit/mirrors-eslint": "eslint",
    "github.com/charliermarsh/ruff-pre-commit": "ruff",
    "github.com/astral-sh/ruff-pre-commit": "ruff",
}

PIN_PATTERN = re.compile(r"\b(ruff|black|isort|mypy)==([0-9][\w.]*)")


def _ci_pins(workflow_path: Path) -> dict[str, str]:
    text = workflow_path.read_text(encoding="utf-8")
    return {tool: version for tool, version in PIN_PATTERN.findall(text)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--print-pins",
        action="store_true",
        help="print the parsed CI tool pins and exit",
    )
    args = parser.parse_args()

    workflow = args.root / ".github" / "workflows" / "test-pipeline.yml"
    pins = _ci_pins(workflow)
    if args.print_pins:
        for tool, version in sorted(pins.items()):
            print(f"{tool}=={version}")
        return 0

    precommit_path = args.root / ".pre-commit-config.yaml"
    config = yaml.safe_load(precommit_path.read_text(encoding="utf-8")) or {}

    violations: list[str] = []
    for repo_entry in config.get("repos", []):
        repo_url = str(repo_entry.get("repo", ""))
        for fragment, tool in MIRROR_REPOS.items():
            if fragment in repo_url:
                rev = repo_entry.get("rev", "?")
                violations.append(
                    f"MIRROR-HOOK: {tool} is duplicated via {repo_url} "
                    f"(rev {rev}); CI pins are {pins or 'in the workflow'}. "
                    "Replace with a `repo: local` hook that runs the same "
                    "repository command CI runs."
                )

    if violations:
        print(f"{len(violations)} pre-commit/CI drift violation(s):\n")
        for violation in violations:
            print(f"  {violation}")
        return 1
    print("OK: pre-commit uses repository-owned commands only; CI pins are "
          f"{', '.join(f'{t}=={v}' for t, v in sorted(pins.items()))}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
