"""Inventory ratchet for the enqueue-before-commit race class (PR 1, Task 1.1).

The failure mode: a request handler enqueues a Celery task (``.delay(...)`` /
``.apply_async(...)`` / ``send_task(...)``) *before* it commits the row the
worker will read, so a fast worker can pick up the job and find no row (or a
stale one). ``documents.py`` deliberately orders enqueue-then-commit to avoid
orphan rows on broker failure, which trades that orphan risk for this race —
the ``enqueue_after_commit`` helper (Task 1.2) resolves both.

This test walks ``backend/src`` with stdlib ``ast`` and, for every function
that contains BOTH a raw Celery enqueue call AND a ``*.commit()`` call, asserts
the enqueue is not positionally before a commit. A site is exempt when it either
routes through ``enqueue_after_commit(...)`` (which fires post-commit by design)
or carries a ``# enqueue-before-commit: <justification>`` comment on the enqueue
line or the line directly above it.

Task 1.3 migrated all three original offenders to the post-commit helpers, so
this ratchet is now GREEN and guards against regressions. Measured baseline on
``develop @ 93fb8f7f`` (branch cut point), now all resolved:

    documents.py:1360   process_document_ingestion.delay    -> enqueue_after_commit
    files.py:775        process_document_ingestion.delay    -> enqueue_after_commit
    projects.py:545     kg_extract_entities_job.apply_async -> enqueue_after_commit_apply_async

All three were the same deliberate ``flush → enqueue → await db.commit()`` shape.
If the offender list becomes non-empty again, the ratchet caught a new offender:
route it through ``enqueue_after_commit`` / ``enqueue_after_commit_apply_async``,
or add a ``# enqueue-before-commit: <reason>`` comment.

Deliberately out of scope (tracked separately, the async-only helper can't fix
them): sync ``self.db.commit()`` sites (``processing_service.queue_processing_job``,
etc.) and compensation commits inside ``except``/``finally`` handlers
(``file_service`` reverses a failed upload after its real post-enqueue commit).

Known limitations (accidental blind spots this AST walk does not catch): a
nested-function enqueue whose only commit lives in the enclosing scope (the
nested body is visited as its own scope, so the enclosing commit isn't seen),
and an aliased enqueue where the bound method is stashed first
(``d = task.delay; d(...)``) — the call node is then a plain ``Name``, not a
``.delay`` attribute, so ``_enqueue_kind`` classifies it as neither raw nor
helper. Neither pattern occurs in ``src`` today; if one is introduced, prefer
the helper regardless.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterator

import pytest

pytestmark = pytest.mark.unit

_SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
_JUSTIFY_MARKER = "# enqueue-before-commit:"
# Post-commit enqueue helpers (src/tasks/enqueue.py) — exempt escape hatches:
# both fire their enqueue on ``after_commit``, so a call positioned before a
# commit is correct by construction.
_HELPER_NAMES = {"enqueue_after_commit", "enqueue_after_commit_apply_async"}


def _own_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Yield descendants of ``node`` that belong to its own scope.

    Nested function/lambda bodies are their own scope and are skipped here
    (they are visited separately as their own function nodes), so a nested
    ``.delay()`` is never mis-attributed to the enclosing function.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield child
        yield from _own_nodes(child)


def _enqueue_kind(call: ast.Call) -> str | None:
    """Classify a call node: 'raw' (needs ordering), 'helper' (exempt), or None."""
    func = call.func
    if isinstance(func, ast.Attribute):
        if func.attr in _HELPER_NAMES:
            return "helper"
        if func.attr in ("delay", "apply_async", "send_task"):
            return "raw"
    elif isinstance(func, ast.Name):
        if func.id in _HELPER_NAMES:
            return "helper"
        if func.id == "send_task":
            return "raw"
    return None


def _awaited_commit_lineno(node: ast.AST) -> int | None:
    """Return the line of an ``await <x>.commit()`` call, else None.

    Scoped to *awaited* commits on purpose: the ``enqueue_after_commit`` helper
    (Task 1.2) takes an ``AsyncSession``, so only async-session sites are in this
    ratchet's remit. Sync ``self.db.commit()`` sites carry the same race but need
    a different fix — e.g. ``src/services/processing/processing_service.py:154``
    (``queue_processing_job``), which would need a future sync-session enqueue
    helper and is out of this PR's scope.
    """
    if (
        isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "commit"
    ):
        return node.value.lineno
    return None


def _happy_path_commit_linenos(func: ast.AST) -> list[int]:
    """Awaited-commit line numbers on ``func``'s normal control-flow path.

    Commits inside an ``except`` handler or a ``finally`` block are excluded:
    those are compensation/cleanup commits (e.g. ``file_service`` reverses a
    partially-applied upload after an enqueue failure), not the durability
    commit a worker depends on. Counting them flags a site that already
    enqueues *after* its real commit — a false positive that could only be
    "resolved" by a dishonest justification comment.
    """
    lines: list[int] = []

    def visit(node: ast.AST, in_handler: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(child, ast.Try):
                for n in child.body:
                    visit(n, in_handler)
                for n in child.orelse:
                    visit(n, in_handler)
                for handler in child.handlers:
                    for n in handler.body:
                        visit(n, True)
                for n in child.finalbody:
                    visit(n, True)
                continue
            ln = _awaited_commit_lineno(child)
            if ln is not None and not in_handler:
                lines.append(ln)
            visit(child, in_handler)

    visit(func, False)
    return lines


def _has_justification(src_lines: list[str], lineno: int) -> bool:
    """True if the enqueue line or the line above carries a justified marker."""
    for candidate in (lineno, lineno - 1):
        if 1 <= candidate <= len(src_lines):
            line = src_lines[candidate - 1]
            idx = line.find(_JUSTIFY_MARKER)
            if idx != -1 and line[idx + len(_JUSTIFY_MARKER) :].strip():
                return True
    return False


def _offenders() -> list[str]:
    offenders: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:  # pragma: no cover - src is expected to parse
            continue
        src_lines = source.splitlines()
        rel = path.relative_to(_SRC_ROOT.parent).as_posix()
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            enqueues = [
                (n, k)
                for n in _own_nodes(func)
                if isinstance(n, ast.Call) and (k := _enqueue_kind(n))
            ]
            commit_lines = _happy_path_commit_linenos(func)
            if not enqueues or not commit_lines:
                continue
            last_commit = max(commit_lines)
            for call, kind in enqueues:
                if kind == "helper":
                    continue  # (a) fires post-commit by construction
                if call.lineno >= last_commit:
                    continue  # enqueue is after every commit — the fixed shape
                if _has_justification(src_lines, call.lineno):
                    continue  # (b) explicitly justified pre-commit enqueue
                offenders.append(f"{rel}:{call.lineno}")
    return offenders


def test_no_unjustified_enqueue_before_commit() -> None:
    offenders = _offenders()
    assert not offenders, (
        "Celery enqueue positioned before an awaited commit "
        "(worker-reads-before-commit race). Route through "
        "enqueue_after_commit(...) or add a '# enqueue-before-commit: "
        "<reason>' comment. Offenders:\n  " + "\n  ".join(offenders)
    )
