"""
Threads API routes for workspaces, threads, thread search, and conversations

CRITICAL: Router ordering matters!
threads_router MUST be included BEFORE workspaces_standalone_router in main.py
because threads_router has /bulk/* routes that need higher priority.
"""

from .conversations import router as conversations_router
from .thread_search import router as thread_search_router
from .threads import (
    check_bulk_archive_rate_limit,
    check_bulk_delete_rate_limit,
    check_bulk_rate_limit,
    check_bulk_resolve_rate_limit,
    check_bulk_summarize_rate_limit,
)
from .threads import router as threads_router
from .workspaces import router as workspaces_router
from .workspaces import standalone_router as workspaces_standalone_router

__all__ = [
    "workspaces_router",
    "workspaces_standalone_router",
    "threads_router",
    "thread_search_router",
    "conversations_router",
    "check_bulk_rate_limit",
    "check_bulk_resolve_rate_limit",
    "check_bulk_archive_rate_limit",
    "check_bulk_summarize_rate_limit",
    "check_bulk_delete_rate_limit",
]
