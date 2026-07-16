#!/usr/bin/env python3
"""Ratchet frontend/tsconfig.json production exclusions against a baseline.

``frontend/tsconfig.json`` excludes many production files from
type-checking. That debt is frozen in
``frontend/quality-baseline.json`` under ``tsconfigProductionExclusions``
and may only shrink. This checker fails (exit 1) when:

- a production exclusion exists in tsconfig but not in the baseline
  (new debt added without a reviewed baseline update);
- a baseline entry no longer appears in tsconfig (stale record that
  would let the exclusion silently return later);
- a baseline entry matches nothing on disk (the excluded file is gone —
  remove the entry);
- a changed production file is still excluded (touching a file requires
  fixing its types and removing the exclusion).

Structural exclusions — node_modules, test/spec/story globs, e2e,
playwright config, test setup — are not debt and are ignored.

Usage:
    check_tsconfig_exclusions.py [--root DIR] [--base REF | --changed PATH ...]
    check_tsconfig_exclusions.py --emit-baseline   # print current debt JSON
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Exclusions that are test/tooling structure, not production type debt.
STRUCTURAL_EXACT = {
    "node_modules",
    "playwright.config.ts",
    "trigger.config.ts",
}
STRUCTURAL_PREFIXES = (
    "e2e/",
    "examples/",
    "src/test/",
    "src/components/__tests__/",
)
STRUCTURAL_GLOB_SUFFIXES = (
    ".test.ts",
    ".test.tsx",
    ".spec.ts",
    ".spec.tsx",
    ".stories.ts",
    ".stories.tsx",
)


def _is_structural(entry: str) -> bool:
    if entry in STRUCTURAL_EXACT:
        return True
    if any(entry.startswith(prefix) for prefix in STRUCTURAL_PREFIXES):
        return True
    stripped = entry.rstrip("*/")  # "e2e/**/*" -> "e2e"
    if any((stripped + "/").startswith(prefix) for prefix in STRUCTURAL_PREFIXES):
        return True
    if entry.startswith("**/") and any(
        entry.endswith(suffix) for suffix in STRUCTURAL_GLOB_SUFFIXES
    ):
        return True
    return False


def _load_jsonc(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # tolerate // comments and trailing commas (tsconfig is JSONC)
        no_comments = re.sub(r"^\s*//.*$", "", raw, flags=re.MULTILINE)
        no_trailing = re.sub(r",(\s*[}\]])", r"\1", no_comments)
        return json.loads(no_trailing)


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a tsconfig exclude glob into a path regex."""
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern[i : i + 3] == "**/":
                out.append(r"(?:.*/)?")
                i += 3
                continue
            if pattern[i : i + 2] == "**":
                out.append(r".*")
                i += 2
                continue
            out.append(r"[^/]*")
            i += 1
            continue
        out.append(re.escape(ch))
        i += 1
    return re.compile("".join(out) + r"(?:/.*)?$")


def _production_exclusions(tsconfig: dict) -> list[str]:
    return sorted(
        entry
        for entry in tsconfig.get("exclude", [])
        if not _is_structural(entry)
    )


def _matches_anything(entry: str, frontend_dir: Path) -> bool:
    if not any(ch in entry for ch in "*?["):
        return (frontend_dir / entry).exists()
    regex = _glob_to_regex(entry)
    prefix = entry.split("*", 1)[0].rstrip("/")
    search_root = frontend_dir / prefix if prefix else frontend_dir
    if not search_root.exists():
        return False
    for path in search_root.rglob("*"):
        if path.is_file():
            relative = path.relative_to(frontend_dir).as_posix()
            if regex.match(relative):
                return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--base", help="git base ref for changed-file check")
    parser.add_argument(
        "--changed",
        action="append",
        default=[],
        help="repo-relative changed file (repeatable; alternative to --base)",
    )
    parser.add_argument(
        "--emit-baseline",
        action="store_true",
        help="print the current production exclusions as JSON and exit",
    )
    args = parser.parse_args()

    frontend_dir = args.root / "frontend"
    tsconfig = _load_jsonc(frontend_dir / "tsconfig.json")
    production = _production_exclusions(tsconfig)

    if args.emit_baseline:
        print(json.dumps(production, indent=2))
        return 0

    baseline_path = frontend_dir / "quality-baseline.json"
    baseline_doc = _load_jsonc(baseline_path)
    baseline = baseline_doc.get("tsconfigProductionExclusions")
    if baseline is None:
        print(
            f"ERROR: {baseline_path} has no tsconfigProductionExclusions key",
            file=sys.stderr,
        )
        return 2

    changed = list(args.changed)
    if args.base:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from changed_source_files import _changed_paths, _resolve_base, classify

        changed.extend(classify(_changed_paths(_resolve_base(args.base)))["frontend"])

    violations: list[str] = []

    baseline_set = set(baseline)
    for entry in production:
        if entry not in baseline_set:
            violations.append(
                f"NEW-EXCLUSION: {entry} is excluded in tsconfig.json but not in "
                "the reviewed baseline. Fix the file's types instead, or update "
                "frontend/quality-baseline.json in this PR with justification."
            )

    production_set = set(production)
    for entry in baseline:
        if entry not in production_set:
            violations.append(
                f"STALE-BASELINE: {entry} is in quality-baseline.json but no "
                "longer excluded in tsconfig.json. Remove it from the baseline "
                "so the exclusion cannot silently return."
            )
        elif not _matches_anything(entry, frontend_dir):
            violations.append(
                f"MISSING-FILE: baseline entry {entry} matches no file on disk. "
                "Remove the exclusion and the baseline entry."
            )

    patterns = [(entry, _glob_to_regex(entry)) for entry in production]
    for repo_path in changed:
        if not repo_path.startswith("frontend/"):
            continue
        relative = repo_path[len("frontend/") :]
        for entry, regex in patterns:
            if regex.match(relative):
                violations.append(
                    f"TOUCHED-BUT-EXCLUDED: {repo_path} changed but is still "
                    f"excluded from type-checking by {entry!r}. Remove the "
                    "exclusion (and its baseline entry) and fix the types."
                )

    if violations:
        print(f"{len(violations)} tsconfig exclusion violation(s):\n")
        for violation in violations:
            print(f"  {violation}")
        return 1
    print(
        f"OK: {len(production)} baselined production exclusions, "
        "no new type-check debt."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
