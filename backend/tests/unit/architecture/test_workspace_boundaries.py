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

  (a) Transaction-boundary ownership per route module, tracked against the PR
      3 Task 3.2 migration (``MIGRATED_TO_UOW``). PR 3 moved the *single*
      request commit up from the leaf services to the route/use-case layer,
      one resource at a time (the middleware autobegins the request session,
      so ``db.begin()`` would conflict — a migrated handler ends with exactly
      one ``await db.commit()``). So:
        * A module NOT yet in ``MIGRATED_TO_UOW`` still owns nothing — zero
          ``commit``/``rollback``/``flush``/``refresh``, the pre-move baseline.
        * A migrated module may own ``commit`` only — at most one per handler
          (a second in one handler is a double-commit bug) and at least one in
          the module (proof it actually migrated). It still owns no
          ``rollback``/``flush``/``refresh``: those stay with the
          middleware-owned session (which rolls back the request on the error
          path when a handler raises after a flush but before its commit).
  (b) No resource module (``workspaces``, ``members``, ``conversations``,
      ``threads``, ``messages``, ``collections``) imports another resource
      module's internals — cross-handler helpers must go through the two
      shared modules (``dependencies``, ``presenters``), never sideways.
  (c) The package (``workspace_routes/__init__.py``) and the compatibility
      shim (``backend/src/api/threads/workspaces.py``) both still resolve
      ``router``/``standalone_router`` to the same composed ``APIRouter``
      objects.
  (d) PR 3 Task 3.3 ratchet: no ``src/services/threads/*_service.py`` function
      calls ``commit()`` except the documented ``chat_service.py`` allowlist
      (direct owners + delegate-boundary commits). Leaf services are wholly
      flush-only — the route (or a ChatService delegate) owns the request
      commit.

RATCHET: ``MIGRATED_TO_UOW`` only ever grows, and only in the same commit that
adds a module's handler-end commits + flips its leaf service to flush-only. A
``commit`` in an unmigrated module, a second commit in any one handler, or any
``rollback``/``flush``/``refresh`` in a route module is a regression, full
stop. "Exactly one commit per *mutating* handler" is enforced as "≤1 per
handler, ≥1 per module": a static AST walk can't classify which handlers
mutate (read-only handlers legitimately own zero), so the guard pins the
double-commit ceiling and the migrated-module floor rather than a per-handler
exact count.
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
# moving these out of routers and into one-service-method-owns-one-txn; PR 3
# then moved the single ``commit`` back UP to the route layer per resource.
FORBIDDEN_SESSION_METHODS = frozenset({"commit", "rollback", "flush", "refresh"})

# The only session method a migrated route module may own. rollback/flush/
# refresh never move to the route layer — the middleware-owned session handles
# rollback at the request boundary.
_MIGRATED_ALLOWED = frozenset({"commit"})

# Route modules (stems) whose handlers own their single handler-end commit
# (PR 3 Task 3.2). PR 3 Task 3.3 completed the migration: this now equals the
# full resource-module set (see test_migration_is_complete). Twin of
# ``MIGRATED_ROUTE_MODULES`` in
# ``tests/unit/services/threads/test_transaction_ownership.py``.
MIGRATED_TO_UOW: frozenset[str] = RESOURCE_MODULES

# Leaf persistence services under src/services/threads/ — everything except
# chat_service.py must be flush-only after PR 3 (the route / a ChatService
# delegate owns the request commit).
SERVICES_DIR = BACKEND_DIR / "src" / "services" / "threads"

# The ONLY functions in src/services/threads/ permitted to call commit() after
# PR 3 Task 3.3 — all in chat_service.py. Every other service function is
# flush-only. Each entry carries its removal condition:
#
#   * Direct transaction owners (out of scope for the 4.3 consolidation): they
#     own their commit until a later explicit pass moves it up. Remove when
#     that pass lands.
#   * Delegate-boundary commits (delegate-then-commit): they delegate to a
#     now-flush-only leaf and own the request commit for ChatService's own
#     callers (the legacy src/api/threads/{conversations,threads}.py routes
#     issue no commit of their own; the three collection delegates are
#     currently caller-less but kept faithful). Remove each when its caller
#     owns the commit or the delegate itself is deleted.
CHAT_SERVICE_COMMIT_ALLOWLIST: frozenset[str] = frozenset(
    {
        # direct owners
        "create_message",
        "create_assistant_message",
        "bulk_update_threads",
        "bulk_delete_threads",
        # delegate-boundary commits
        "create_workspace",
        "update_workspace",
        "delete_workspace",
        "create_conversation",
        "update_conversation",
        "delete_conversation",
        "update_thread",
        "delete_thread",
        "update_message_feedback",
        "delete_message",
        "create_collection",
        "add_documents_to_collection",
        "remove_documents_from_collection",
    }
)


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


def _session_call_attrs(node: ast.AST) -> list[str]:
    """Bare FORBIDDEN_SESSION_METHODS attr names called anywhere under node.

    Route handlers contain no nested defs, so an ``ast.walk`` from a top-level
    handler counts exactly that handler's own session calls.
    """
    return [
        c.func.attr
        for c in ast.walk(node)
        if isinstance(c, ast.Call)
        and isinstance(c.func, ast.Attribute)
        and c.func.attr in FORBIDDEN_SESSION_METHODS
    ]


def _top_level_functions(tree: ast.Module) -> list[ast.AST]:
    return [
        n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


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
    """(a) Route-module transaction ownership, tracked against MIGRATED_TO_UOW."""

    def test_guard_scans_a_meaningful_number_of_files(self) -> None:
        files = _route_module_files()
        assert len(files) >= 8, (
            f"Only found {len(files)} files under {ROUTES_DIR} — the "
            "workspace_routes package moved and this guard needs updating."
        )

    def test_migration_is_complete(self) -> None:
        """PR 3 Task 3.3: every resource route module owns its commit — the
        migration is done, so MIGRATED_TO_UOW is exactly the resource-module
        set. The per-resource-flip "unmigrated resource" branch is gone; the
        only routes owning nothing now are the shared/composition modules."""
        assert MIGRATED_TO_UOW == RESOURCE_MODULES, (
            "MIGRATED_TO_UOW must equal RESOURCE_MODULES once PR 3 is complete; "
            f"symmetric diff: {sorted(MIGRATED_TO_UOW ^ RESOURCE_MODULES)}."
        )

    @pytest.mark.parametrize("path", _route_module_files(), ids=lambda p: p.name)
    def test_module_owns_no_transaction_boundary(self, path: Path) -> None:
        tree = _parse(path)

        if path.stem not in MIGRATED_TO_UOW:
            # Shared/composition modules (dependencies, presenters, __init__):
            # not resource modules, never mutate, own no transaction. (Every
            # resource module is migrated now — there is no unmigrated-resource
            # case left.)
            hits = _forbidden_session_calls(tree)
            assert not hits, (
                f"{path} is a shared/composition route module but owns a "
                f"transaction boundary: {hits}. Only the six resource handlers "
                "own commits; dependencies/presenters/__init__ must not."
            )
            return

        # Migrated module (PR 3 Task 3.2): commit only, ≤1 per handler, ≥1 total.
        all_attrs = _session_call_attrs(tree)
        illegal = sorted(set(all_attrs) - _MIGRATED_ALLOWED)
        assert not illegal, (
            f"{path} is migrated to UoW but owns {illegal} — a migrated route "
            "may only call commit() (rollback/flush/refresh stay with the "
            "middleware-owned session)."
        )
        assert "commit" in all_attrs, (
            f"{path} is in MIGRATED_TO_UOW but owns no commit() — either it was "
            "appended prematurely or a handler-end commit is missing."
        )
        for func in _top_level_functions(tree):
            commits = [a for a in _session_call_attrs(func) if a == "commit"]
            assert len(commits) <= 1, (
                f"{path}::{getattr(func, 'name', '?')} calls commit() "
                f"{len(commits)}× — a mutating handler owns EXACTLY ONE commit "
                "at its end; a second is a double-commit bug."
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


# The five leaf persistence services IN SCOPE for PR 3's UoW refactor. Other
# ``*_service.py`` under this package (``thread_summarization_service`` — sync
# SQLAlchemy per its own contract, ``thread_message_search_service``,
# ``thread_event_service``, ``stream_service``) are OUT of scope and own their
# own transactions legitimately, so this ratchet deliberately does not scan
# them. ``chat_service.py`` is handled separately (it keeps an allowlist).
LEAF_SERVICE_MODULES: tuple[str, ...] = (
    "workspace_service.py",
    "conversation_service.py",
    "thread_service.py",
    "message_service.py",
    "collection_service.py",
)


def _commit_functions(tree: ast.Module) -> dict[str, int]:
    """Top-level/class functions -> count of ``.commit()`` calls in their own
    scope. Only ``commit`` (not the other txn methods) — TASK 3.3 is about who
    owns the *commit*."""
    out: dict[str, int] = {}
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        n = sum(
            1
            for c in ast.walk(func)
            if isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute)
            and c.func.attr == "commit"
        )
        if n:
            out[func.name] = out.get(func.name, 0) + n
    return out


class TestServicesDoNotCommitExceptChatServiceAllowlist:
    """(d) PR 3 Task 3.3 ratchet: none of the five in-scope leaf persistence
    services (``LEAF_SERVICE_MODULES``) call ``commit()`` at all, and
    ``chat_service.py`` calls it only in the documented allowlist.

    Complements the per-function LEAF_TXN freeze in
    ``tests/unit/services/threads/test_transaction_ownership.py``: that pins
    each known function's footprint; this catches a commit sneaking into a NEW
    service helper the freeze doesn't enumerate yet. Leaf services are wholly
    flush-only; ChatService keeps its direct-owner + delegate-boundary commits.
    """

    def test_guard_scans_all_service_modules(self) -> None:
        for name in (*LEAF_SERVICE_MODULES, "chat_service.py"):
            assert (SERVICES_DIR / name).is_file(), (
                f"{SERVICES_DIR / name} not found — the in-scope service module "
                "moved/renamed and this ratchet needs updating."
            )

    @pytest.mark.parametrize("name", LEAF_SERVICE_MODULES, ids=lambda n: n)
    def test_leaf_service_is_flush_only(self, name: str) -> None:
        path = SERVICES_DIR / name
        committers = _commit_functions(_parse(path))
        assert not committers, (
            f"{path} calls commit() in {sorted(committers)} — every leaf "
            "persistence service is flush-only after PR 3; the route (or a "
            "ChatService delegate) owns the request commit. If a new function "
            "legitimately needs to own a commit, that is a deliberate ownership "
            "decision to document, not a silent regression."
        )

    def test_chat_service_commits_only_in_the_allowlist(self) -> None:
        committers = set(_commit_functions(_parse(SERVICES_DIR / "chat_service.py")))
        unexpected = committers - CHAT_SERVICE_COMMIT_ALLOWLIST
        assert not unexpected, (
            f"ChatService function(s) {sorted(unexpected)} call commit() but are "
            "not in CHAT_SERVICE_COMMIT_ALLOWLIST. Either it is a direct owner / "
            "delegate-boundary commit (add it, with its removal condition) or it "
            "should delegate the commit to its caller."
        )

    def test_allowlist_has_no_stale_entries(self) -> None:
        committers = set(_commit_functions(_parse(SERVICES_DIR / "chat_service.py")))
        stale = CHAT_SERVICE_COMMIT_ALLOWLIST - committers
        assert not stale, (
            f"CHAT_SERVICE_COMMIT_ALLOWLIST lists {sorted(stale)} which no longer "
            "call commit() — a delegate's commit was removed (removal condition "
            "met?); drop it from the allowlist in the same change."
        )
