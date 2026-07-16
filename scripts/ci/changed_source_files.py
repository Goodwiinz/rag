#!/usr/bin/env python3
"""List Python and frontend TS/JS files changed since a trusted base.

CI ratchets block new debt on *touched* files only, so the changed-file
set must be computed against an explicit, trustworthy base:

1. ``--base <ref>`` (highest priority)
2. ``PR_BASE_SHA`` environment variable (pull_request events)
3. ``GITHUB_EVENT_BEFORE`` environment variable (push events); an
   all-zero SHA (new branch) is rejected as untrustworthy
4. otherwise: exit 2 with a clear error — never guess a base

The diff runs from ``merge-base(base, HEAD)`` against the working tree,
so committed, staged, and unstaged changes are all included (pre-commit
hooks reuse this helper). Deletions are excluded; renames report the
new path. Generated files are never reported.

Usage:
    changed_source_files.py [--base REF] [--kind {python,frontend,all}]

``--kind python``/``--kind frontend`` print newline-separated paths;
``--kind all`` (default) prints a JSON object with both lists.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

FRONTEND_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
GENERATED_PREFIXES = ("frontend/src/types/generated/",)
ALL_ZERO_SHAS = {"0" * 40, "0" * 64}


def _fail(message: str) -> "None":
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        _fail(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _resolve_base(explicit: str | None) -> str:
    candidate = explicit
    source = "--base"
    if candidate is None:
        candidate = os.environ.get("PR_BASE_SHA") or None
        source = "PR_BASE_SHA"
    if candidate is None:
        before = os.environ.get("GITHUB_EVENT_BEFORE") or None
        if before in ALL_ZERO_SHAS:
            _fail(
                "GITHUB_EVENT_BEFORE is all zeros (new branch); "
                "no trustworthy base ref is available. Pass --base explicitly."
            )
        candidate = before
        source = "GITHUB_EVENT_BEFORE"
    if candidate is None:
        _fail(
            "no base ref: pass --base, or set PR_BASE_SHA / "
            "GITHUB_EVENT_BEFORE. Refusing to guess a diff base."
        )
    verify = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    if verify.returncode != 0:
        _fail(f"base ref from {source} ({candidate!r}) does not resolve to a commit")
    return verify.stdout.strip()


def _changed_paths(base: str) -> list[str]:
    merge_base = _git("merge-base", base, "HEAD").strip()
    # -z: NUL separators (spaces/renames safe); -M: detect renames;
    # ACMR: added/copied/modified/renamed — deletions excluded.
    raw = _git(
        "diff", "--name-status", "-z", "-M", "--diff-filter=ACMR", merge_base
    )
    fields = raw.split("\0")
    paths: list[str] = []
    i = 0
    while i < len(fields):
        status = fields[i]
        if not status:
            i += 1
            continue
        if status.startswith(("R", "C")):
            # rename/copy: old path, then new path — keep the new one
            if i + 2 >= len(fields) + 1:
                break
            paths.append(fields[i + 2])
            i += 3
        else:
            if i + 1 >= len(fields):
                break
            paths.append(fields[i + 1])
            i += 2
    return paths


def classify(paths: list[str]) -> dict[str, list[str]]:
    python: list[str] = []
    frontend: list[str] = []
    for path in paths:
        if any(path.startswith(prefix) for prefix in GENERATED_PREFIXES):
            continue
        if path.endswith(".py"):
            python.append(path)
        elif path.startswith("frontend/") and path.endswith(FRONTEND_SUFFIXES):
            frontend.append(path)
    return {"python": sorted(python), "frontend": sorted(frontend)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="base ref to diff against")
    parser.add_argument(
        "--kind", choices=("python", "frontend", "all"), default="all"
    )
    args = parser.parse_args()

    base = _resolve_base(args.base)
    groups = classify(_changed_paths(base))
    if args.kind == "all":
        print(json.dumps(groups, indent=2))
    else:
        for path in groups[args.kind]:
            print(path)


if __name__ == "__main__":
    main()
