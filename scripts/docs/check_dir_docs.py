#!/usr/bin/env python3
"""Lint per-directory docs (README.md / doc.md) for content, not boilerplate.

This guard exists because a "drop an identical placeholder in every folder"
change is worse than no docs: it costs reviewers nothing to add and everyone
something to read, and it rots silently the moment a directory changes. The
rule we enforce here is simple — a committed directory doc must say something
true about *that* directory.

It fails (exit 1) when a tracked ``README.md``/``doc.md`` contains:

1. Known boilerplate sentences (the auto-generated placeholder template).
2. Un-filled scaffold markers (``<!-- TODO(dir-doc): ... -->``) left over from
   ``gen_dir_readme.py``. A freshly scaffolded file is *meant* to fail this
   check until a human replaces the markers with real content.
3. Effectively no prose — headings and empty tables with nothing else.

Usage::

    python3 scripts/docs/check_dir_docs.py            # scan all tracked docs
    python3 scripts/docs/check_dir_docs.py PATH ...   # scan specific files (pre-commit)

Stdlib only; runs anywhere Python 3.8+ does.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# --- Configuration ----------------------------------------------------------

# Filenames treated as "directory docs" and therefore subject to this lint.
DOC_FILENAMES = ("README.md", "doc.md")

# Path fragments never worth linting (vendored / generated / ephemeral).
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

# Boilerplate sentences from the auto-placeholder template. Substring match,
# case-insensitive. Keep these verbatim to the generator that produced them.
BANNED_PHRASES = (
    "this directory is part of the project",
    "refer to the main project documentation for more information",
    "documentation for `./",
)

# Scaffold markers emitted by gen_dir_readme.py. Their presence in a *committed*
# file means the author scaffolded but never filled it in.
SCAFFOLD_MARKER = "<!-- TODO(dir-doc):"

# Minimum count of real content words (prose, table cells, and informative
# headings, after stripping fences, HTML comments, table separators, and a bare
# title that merely echoes the directory name). Low on purpose: any genuine
# directory doc clears it easily; an echo-title-only stub does not.
MIN_BODY_WORDS = 12

# Optional ignore file: newline-separated path globs, ``#`` comments allowed.
IGNORE_FILE = Path(__file__).resolve().parent / "dir-docs-ignore.txt"

_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_WORD_RE = re.compile(r"[A-Za-z]{2,}")


# --- Discovery --------------------------------------------------------------


def _git_tracked_docs() -> list[Path]:
    """Every tracked README.md/doc.md in the repo, via ``git ls-files``."""
    patterns = []
    for name in DOC_FILENAMES:
        patterns += [name, f"**/{name}"]
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z", *patterns],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [Path(p) for p in out.split("\0") if p]


def _load_ignore_globs() -> list[str]:
    if not IGNORE_FILE.exists():
        return []
    globs = []
    for line in IGNORE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            globs.append(line)
    return globs


def _is_skipped(path: Path, ignore_globs: list[str]) -> bool:
    posix = "/" + path.as_posix().lstrip("/")
    if any(frag in posix for frag in SKIP_FRAGMENTS):
        return True
    return any(path.match(glob) for glob in ignore_globs)


# --- Checks -----------------------------------------------------------------


def _body_word_count(text: str, dir_name: str) -> int:
    """Count real content words.

    Removes chrome — code fences, HTML comments, table separator rows — and one
    leading title line that merely echoes the directory name (the tell-tale of
    an auto-generated ``# backend`` stub). Everything else counts, including
    informative headings (``# excluded — see GOO-151``) and table cells, which
    are genuine content.
    """
    text = _HTML_COMMENT_RE.sub(" ", text)
    words = 0
    in_fence = False
    title_seen = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line:
            continue
        if _TABLE_SEP_RE.match(line):  # |---|---| separator
            continue
        heading = line.lstrip("#").strip() if line.startswith("#") else line
        if line.startswith("# ") and not title_seen:
            title_seen = True
            if heading.lower() == dir_name.lower():  # bare echo title, not content
                continue
        words += len(_WORD_RE.findall(heading))
    return words


def check_file(path: Path) -> list[str]:
    """Return a list of human-readable problems with ``path`` (empty == clean)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"could not read file: {exc}"]

    problems: list[str] = []
    lowered = text.lower()

    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            problems.append(
                f'contains placeholder boilerplate: "{phrase}" — '
                "describe this directory instead, or delete the file"
            )

    if SCAFFOLD_MARKER in text:
        n = text.count(SCAFFOLD_MARKER)
        problems.append(
            f"has {n} un-filled scaffold marker(s) ({SCAFFOLD_MARKER} ... -->) — "
            "replace each with real content before committing"
        )

    # Only bother with the prose floor if nothing louder already fired; a stub
    # that also tripped a banned phrase doesn't need a second, vaguer complaint.
    if not problems:
        words = _body_word_count(text, path.parent.name)
        if words < MIN_BODY_WORDS:
            problems.append(
                f"almost no content ({words} body words, need >= {MIN_BODY_WORDS}) — "
                "a directory doc should explain what lives here and why"
            )

    return problems


# --- Entry point ------------------------------------------------------------


def main(argv: list[str]) -> int:
    ignore_globs = _load_ignore_globs()

    if argv:
        targets = [Path(a) for a in argv if Path(a).name in DOC_FILENAMES]
    else:
        targets = _git_tracked_docs()

    targets = [t for t in targets if not _is_skipped(t, ignore_globs)]

    if not targets:
        print("dir-docs: no directory docs to check.")
        return 0

    failures: dict[Path, list[str]] = {}
    for path in sorted(set(targets)):
        problems = check_file(path)
        if problems:
            failures[path] = problems

    if not failures:
        print(f"dir-docs: {len(targets)} directory doc(s) OK.")
        return 0

    print("dir-docs: placeholder / empty documentation found.\n")
    for path, problems in failures.items():
        print(f"  {path.as_posix()}")
        for p in problems:
            print(f"      - {p}")
    print(
        f"\n{len(failures)} file(s) failed. Fix the content or remove the file. "
        "Scaffold real docs with: python3 scripts/docs/gen_dir_readme.py --dir <path>"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
