"""Regression guard: every AsyncSession coroutine call in files.py is awaited.

An unawaited ``db.rollback()`` / ``db.refresh()`` on an AsyncSession returns a
coroutine that is never scheduled: the rollback silently never happens (the
error path re-raises with the transaction still dirty) and the refresh no-ops.
Four such sites shipped in backend/src/api/documents/files.py; this test parses
the module AST and fails if any ``db.<coroutine-method>(...)`` call is not
wrapped in ``await``, so the class of bug cannot regress.

Pure-AST test: no app imports, runs without langgraph/libpq.
"""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

FILES_PY = (
    Path(__file__).resolve().parents[2] / "src" / "api" / "documents" / "files.py"
)

# AsyncSession methods that return coroutines and MUST be awaited.
COROUTINE_METHODS = {
    "commit",
    "rollback",
    "refresh",
    "flush",
    "execute",
    "delete",
    "merge",
    "close",
    "get",
    "get_one",
    "scalar",
    "scalars",
    "stream",
    "stream_scalars",
}


def _unawaited_db_calls(tree: ast.AST) -> list[str]:
    """Return "line: code" entries for db.<coro>() calls not wrapped in await."""
    awaited_calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            awaited_calls.add(id(node.value))

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "db"
            and func.attr in COROUTINE_METHODS
            and id(node) not in awaited_calls
        ):
            offenders.append(f"line {node.lineno}: db.{func.attr}(...)")
    return offenders


def test_all_async_db_calls_awaited():
    tree = ast.parse(FILES_PY.read_text())
    offenders = _unawaited_db_calls(tree)
    assert not offenders, (
        "Unawaited AsyncSession coroutine call(s) in files.py — the operation "
        f"silently never runs: {offenders}"
    )
