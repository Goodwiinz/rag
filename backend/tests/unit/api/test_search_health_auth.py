"""R5-M13: GET /api/v2/search/health must require auth.

``search_health_check`` (thread_search.py) carried no auth dependency, so any
unauthenticated caller could hit it and enumerate the raw GIN index DDL
(``pg_indexes.indexdef``) for the threads/chat_messages tables plus FTS
liveness — a schema-disclosure leak. Fixed by adding
``Depends(get_current_user)`` (same convention as the WS status endpoints
fixed for R4-M5, see test_realtime_status_auth.py) and trimming the response
to index names + a boolean rather than the raw DDL text.

Verified statically via the FastAPI dependency graph, matching
test_realtime_status_auth.py's approach — no live server/DB needed.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable

import pytest

from src.core.dependencies import get_current_user

pytestmark = pytest.mark.unit


def _has_current_user_dependency(fn: Callable[..., Any]) -> bool:
    for param in inspect.signature(fn).parameters.values():
        default = param.default
        if default is inspect._empty:
            continue
        dependency = getattr(default, "dependency", None)
        if dependency is get_current_user:
            return True
    return False


def test_search_health_requires_auth() -> None:
    from src.api.threads.thread_search import search_health_check

    assert _has_current_user_dependency(search_health_check)


def test_search_health_does_not_echo_raw_index_ddl_source() -> None:
    """Defense-in-depth: pin that the handler stopped building an
    ``indexdef``-keyed dict (the raw DDL text) even if someone reintroduces
    an auth bypass later — the disclosure was of the DDL string itself.
    """
    import inspect as _inspect

    from src.api.threads import thread_search as mod

    source = _inspect.getsource(mod.search_health_check)
    assert '"definition": row.indexdef' not in source
    assert '"gin": True' in source
