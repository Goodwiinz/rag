"""Architectural regression guard for the Task 4.2/4.3 workspace route split.

``backend/src/api/threads/workspaces.py`` used to be a single 2,517-line
router. Task 4.2 split it by resource into
``backend/src/api/threads/workspace_routes/`` (``workspaces.py``,
``members.py``, ``conversations.py``, ``threads.py``, ``messages.py``,
``collections.py``, plus the shared ``dependencies.py``/``presenters.py``
helpers, composed by ``__init__.py``). Task 4.3 then moved every mutation
into ``src/services/threads/*_service.py`` so each service method owns one
transaction boundary and routers only orchestrate HTTP <-> service calls.

This test encodes the rule the split ACTUALLY established today, not the
plan's original aspiration. In particular, the plan text also floated
banning ``select()``/model imports from route modules outright — that is
not what 4.3 did: ``workspace_routes/messages.py`` still issues a
``select(ChatMessage)...selectinload(...)`` re-query after
``create_message``/``create_message_standalone`` to eager-load citation and
attachment document metadata for the response (those two handlers are
explicitly out of scope per the 4.3 docstring and amendment A3 — they
already delegate mutation to ``ChatService.create_message``, this is a
read-only re-fetch, not a transaction). Enforcing a blanket select()/model-
import ban here would fail on legitimate, already-reviewed code, so this
guard only checks what the split is actually load-bearing on:

  (a) No route module calls ``.commit()``/``.rollback()``/``.flush()``/
      ``.refresh()`` (transaction-boundary ownership moved to the service
      layer wholesale — the codebase today has zero such calls in this
      package, so this is a straight ratchet: any future ``db.commit()``
      creeping back into a route handler is a regression, full stop).
  (b) No resource module (``workspaces``, ``members``, ``conversations``,
      ``threads``, ``messages``, ``collections``) imports another resource
      module's internals — cross-handler helpers must go through the two
      shared modules (``dependencies``, ``presenters``), never sideways.
  (c) The package (``workspace_routes/__init__.py``) and the compatibility
      shim (``backend/src/api/threads/workspaces.py``) both still resolve
      ``router``/``standalone_router`` to the same composed ``APIRouter``
      objects.

RATCHET: if a future change legitimately needs a route handler to own a
commit, or needs a resource module to reach into another resource module,
that is a new decision to make explicitly (and to re-document here) — it
must not happen silently.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

BACKEND_DIR = Path(__file__).resolve().parents[3]
ROUTES_DIR = BACKEND_DIR / "src" / "api" / "threads" / "workspace_routes"

# The per-resource modules split out of the original monolith. Each may only
# reach sideways into the two shared modules below, never into a sibling
# resource module.
RESOURCE_MODULES = frozenset(
    {"workspaces", "members", "conversations", "threads", "messages", "collections"}
)
SHARED_MODULES = frozenset({"dependencies", "presenters"})

# db-session methods that own a transaction boundary. 4.3's whole point was
# moving these out of routers and into one-service-method-owns-one-txn.
FORBIDDEN_SESSION_METHODS = frozenset({"commit", "rollback", "flush", "refresh"})


def _route_module_files() -> list[Path]:
    return sorted(p for p in ROUTES_DIR.glob("*.py") if p.name != "__pycache__")


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _forbidden_session_calls(tree: ast.Module) -> list[str]:
    """Method names among FORBIDDEN_SESSION_METHODS called anywhere in tree."""
    hits = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in FORBIDDEN_SESSION_METHODS
        ):
            hits.append(f"{node.func.attr}() at line {node.lineno}")
    return hits


def _relative_import_targets(tree: ast.Module) -> set[str]:
    """Module-level names reached via `from .x import y` / `from . import x`."""
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            if node.module:
                targets.add(node.module)
            else:
                targets.update(alias.name for alias in node.names)
    return targets


class TestNoRouterOwnedTransactions:
    """(a) Routers never call commit/rollback/flush/refresh (Task 4.3)."""

    def test_guard_scans_a_meaningful_number_of_files(self) -> None:
        files = _route_module_files()
        assert len(files) >= 8, (
            f"Only found {len(files)} files under {ROUTES_DIR} — the "
            "workspace_routes package moved and this guard needs updating."
        )

    @pytest.mark.parametrize("path", _route_module_files(), ids=lambda p: p.name)
    def test_module_owns_no_transaction_boundary(self, path: Path) -> None:
        hits = _forbidden_session_calls(_parse(path))
        assert not hits, (
            f"{path} calls a transaction-boundary method the Task 4.3 split "
            f"moved into src/services/threads/: {hits}. Route handlers must "
            "delegate commit/rollback/flush/refresh to a service method."
        )


class TestNoSidewaysResourceImports:
    """(b) Resource modules reach only dependencies/presenters, never a sibling."""

    def test_guard_scans_all_resource_modules(self) -> None:
        found = {p.stem for p in _route_module_files()}
        missing = RESOURCE_MODULES - found
        assert not missing, (
            f"Expected resource modules {sorted(missing)} not found under "
            f"{ROUTES_DIR} — this guard needs updating."
        )

    @pytest.mark.parametrize("resource_name", sorted(RESOURCE_MODULES), ids=lambda n: n)
    def test_resource_module_does_not_import_a_sibling(
        self, resource_name: str
    ) -> None:
        path = ROUTES_DIR / f"{resource_name}.py"
        targets = _relative_import_targets(_parse(path))
        siblings = targets & (RESOURCE_MODULES - {resource_name})
        assert not siblings, (
            f"{path} imports sibling resource module(s) {sorted(siblings)} "
            "directly. Cross-handler helpers belong in dependencies.py "
            "(scope/access) or presenters.py (response shaping) — the two "
            "shared modules every resource module is allowed to import."
        )


class TestCompositionExportsStillResolve:
    """(c) The package and the compatibility shim still export the same routers."""

    def test_package_init_declares_public_routers(self) -> None:
        tree = _parse(ROUTES_DIR / "__init__.py")
        all_values: set[str] = set()
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
                )
                and isinstance(node.value, (ast.List, ast.Tuple))
            ):
                all_values.update(
                    elt.value
                    for elt in node.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                )
        assert {"router", "standalone_router"} <= all_values, (
            f"{ROUTES_DIR / '__init__.py'} must keep exporting `router` and "
            "`standalone_router` in __all__."
        )

    def test_shim_and_package_resolve_to_the_same_router_objects(self) -> None:
        from fastapi import APIRouter

        from src.api.threads import workspace_routes as package
        from src.api.threads import workspaces as shim

        for name in ("router", "standalone_router"):
            package_obj = getattr(package, name)
            shim_obj = getattr(shim, name)
            assert isinstance(
                package_obj, APIRouter
            ), f"workspace_routes.{name} is no longer an APIRouter"
            assert shim_obj is package_obj, (
                f"backend/src/api/threads/workspaces.py `{name}` no longer "
                "re-exports the same composed router object from "
                "workspace_routes — the compatibility export broke."
            )
            assert shim_obj.routes, f"workspace_routes.{name} has no routes composed"
