"""Route-table assertions for the create-message deprecation (audit C4).

Three public POST create-message routes coexist, but only the flat
``POST /api/v2/messages`` (``create_message_standalone``) is called by any
client — it is canonical. The two nested variants have no live callers and are
marked ``deprecated=True`` in their decorators for a deprecation window (not
deleted yet — they are wire-visible public API; removal follows in a cleanup
PR). These tests pin the deprecation flags to the route table so the state is
regression-guarded and the canonical route stays un-deprecated.
"""

from __future__ import annotations

import pytest

from src.api.threads.threads import router as threads_router
from src.api.threads.workspaces import router as workspaces_router
from src.api.threads.workspaces import standalone_router as workspaces_standalone_router

pytestmark = pytest.mark.unit


def _post_route(router, path_suffix):
    """Return the single POST route whose path ends with ``path_suffix``."""
    matches = [
        r
        for r in router.routes
        if getattr(r, "path", "").endswith(path_suffix)
        and "POST" in getattr(r, "methods", set())
    ]
    assert len(matches) == 1, f"expected exactly one POST {path_suffix}, got {matches}"
    return matches[0]


class TestCreateMessageRouteDeprecation:
    def test_nested_thread_create_route_is_deprecated(self) -> None:
        """POST /api/v2/threads/{thread_id}/messages is deprecated (C4)."""
        route = _post_route(threads_router, "/{thread_id}/messages")
        assert route.deprecated is True

    def test_nested_workspace_create_route_is_deprecated(self) -> None:
        """The deeply-nested workspace create route is deprecated (C4)."""
        route = _post_route(
            workspaces_router,
            "/{workspace_id}/conversations/{conversation_id}/threads/{thread_id}/messages",
        )
        assert route.deprecated is True

    def test_flat_create_route_is_canonical_not_deprecated(self) -> None:
        """The flat POST /api/v2/messages route is canonical and NOT deprecated."""
        route = _post_route(workspaces_standalone_router, "/messages")
        # deprecated is either None (default) or False — never True.
        assert not route.deprecated
