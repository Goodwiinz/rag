"""
Thread-centric Workspace API endpoints for Terminal Observatory
Provides CRUD operations for Workspaces, Conversations, Threads, Messages, and Collections

Task 4.2 split the former 2,517-line monolithic router into
``workspace_routes/`` by resource (workspaces, members, conversations,
threads, messages, collections). This module is now a compatibility shim:
it re-exports the composed ``router``/``standalone_router`` (imported by
``backend/src/api/threads/__init__.py`` and registered in
``backend/src/main.py``, both unchanged) plus the handful of names external
callers — mainly characterization/regression tests that patch or call
individual handlers directly — still import from this path.
"""

from .workspace_routes import router, standalone_router
from .workspace_routes.members import add_workspace_member
from .workspace_routes.messages import (
    update_message_feedback,
    update_message_standalone,
)
from .workspace_routes.presenters import THREAD_PREVIEW_MAX_CHARS
from .workspace_routes.workspaces import create_workspace

__all__ = [
    "router",
    "standalone_router",
    "THREAD_PREVIEW_MAX_CHARS",
    "create_workspace",
    "add_workspace_member",
    "update_message_feedback",
    "update_message_standalone",
]
