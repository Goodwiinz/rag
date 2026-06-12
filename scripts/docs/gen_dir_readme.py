#!/usr/bin/env python3
"""Scaffold a per-directory README.md that *must* be filled in before it merges.

This is the deliberate opposite of an auto-placeholder generator. Instead of
writing plausible-looking boilerplate ("This directory is part of the
project."), it writes a skeleton whose every content slot is an explicit
``<!-- TODO(dir-doc): ... -->`` marker. ``check_dir_docs.py`` rejects those
markers, so a scaffolded-but-unfilled file fails CI — you cannot merge an empty
doc, only a real one.

Usage::

    # Scaffold one directory
    python3 scripts/docs/gen_dir_readme.py --dir backend/src/services/search

    # Scaffold every tracked directory that has no README.md / doc.md yet
    python3 scripts/docs/gen_dir_readme.py --missing

    # Preview without writing
    python3 scripts/docs/gen_dir_readme.py --missing --dry-run

By default existing docs are never overwritten; pass ``--force`` to replace.
Stdlib only.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DOC_FILENAMES = ("README.md", "doc.md")

SKIP_FRAGMENTS = (
    "/node_modules/",
    "/.venv/",
    "/venv/",
    "/.next/",
    "/dist/",
    "/build/",
    "/__pycache__/",
    "/.git/",
    "/site-packages/",
)

TEMPLATE = """\
# {title}

<!-- TODO(dir-doc): one paragraph — what lives in this directory and what depends
     on it. Where does it sit in the request/data flow? Delete this comment once
     written. -->

## Key files

<!-- TODO(dir-doc): list the real files here and a one-line purpose for each.
     Drop rows that don't exist; this is not a fill-in-the-blanks form. -->

| File | Purpose |
| ---- | ------- |
| `...` | ... |

## Notes

<!-- TODO(dir-doc): the things a newcomer needs and can't infer from filenames —
     entry points, conventions, gotchas, how this connects to the rest of the
     system. Remove this section if there is genuinely nothing to add. -->
"""


def _title_for(directory: Path) -> str:
    """Human title for a directory, avoiding the degenerate ``# .`` at repo root."""
    name = directory.name
    if name in ("", "."):
        return "Repository root"
    return name


def _git_tracked_dirs() -> list[Path]:
    """All directories that contain at least one tracked file."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    dirs = set()
    for f in out.split("\0"):
        if not f:
            continue
        parent = Path(f).parent
        dirs.add(parent)
    return sorted(dirs)


def _has_doc(directory: Path) -> bool:
    return any((directory / name).exists() for name in DOC_FILENAMES)


def _is_skipped(directory: Path) -> bool:
    posix = "/" + directory.as_posix().strip("/") + "/"
    return any(frag in posix for frag in SKIP_FRAGMENTS)


def _write(directory: Path, force: bool, dry_run: bool) -> str:
    target = directory / "README.md"
    if target.exists() and not force:
        return f"skip (exists)  {target.as_posix()}"
    content = TEMPLATE.format(title=_title_for(directory))
    if dry_run:
        return f"would write    {target.as_posix()}"
    target.write_text(content, encoding="utf-8")
    return f"wrote          {target.as_posix()}"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--dir", help="single directory to scaffold")
    group.add_argument(
        "--missing",
        action="store_true",
        help="scaffold every tracked directory lacking a README.md/doc.md",
    )
    ap.add_argument(
        "--force", action="store_true", help="overwrite an existing README.md"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="print actions without writing"
    )
    args = ap.parse_args(argv)

    if args.dir:
        directory = Path(args.dir)
        if not directory.is_dir():
            print(f"error: not a directory: {directory}", file=sys.stderr)
            return 2
        print(_write(directory, args.force, args.dry_run))
        return 0

    # --missing
    written = 0
    for directory in _git_tracked_dirs():
        if _is_skipped(directory) or _has_doc(directory):
            continue
        line = _write(directory, args.force, args.dry_run)
        print(line)
        if line.startswith(("wrote", "would write")):
            written += 1
    verb = "would scaffold" if args.dry_run else "scaffolded"
    print(f"\n{verb} {written} directory doc(s). Fill the TODO markers, then:")
    print("  python3 scripts/docs/check_dir_docs.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
