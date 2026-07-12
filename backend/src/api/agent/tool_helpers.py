"""Backward-compatibility shim — implementation moved to the service layer.

Shared tool helper functions have no HTTP concerns; they now live in
``src.services.agent.tool_helpers`` (audit finding B1). This module keeps
the legacy ``src.api.agent.tool_helpers`` import path working for callers
that still reference it (notably ``execute.py``).

Same mechanics as the sibling ``tools_impl`` shim: explicit re-imports for
static analysis, ``__getattr__`` for stale direct-load module objects, and a
``sys.modules`` swap so the legacy path is *identical* to the canonical
module and ``mock.patch`` on the legacy path keeps working.

New code must import from ``src.services.agent.tool_helpers`` directly.
"""

import sys
from typing import Any

from src.services.agent import tool_helpers as _impl
from src.services.agent.tool_helpers import (  # noqa: F401
    _ARXIV_ID_RE,
    _escape_like,
    _link_documents_to_project,
    _log_resource_access_denied,
    _resolve_document_id,
    _resolve_project_id,
    _sanitize_metadata,
    _verify_project_ownership,
)


def __getattr__(name: str) -> Any:  # pragma: no cover — normal imports bypass this
    return getattr(_impl, name)


# Alias the legacy module path to the canonical module (see tools_impl shim).
sys.modules[__name__] = _impl
