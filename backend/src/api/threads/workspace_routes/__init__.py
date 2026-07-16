"""
Workspace API routers, split by resource (Task 4.2).

The former ``backend/src/api/threads/workspaces.py`` was a single 2,517-line
module exporting two ``APIRouter`` objects — ``router`` (nested
``/api/v2/workspaces/...`` paths) and ``standalone_router`` (flat
``/api/v2/...`` paths used by the frontend). This package splits the route
handlers by resource (workspaces, members, conversations, threads, messages,
collections) plus two shared modules (``dependencies``, ``presenters``) for
the cross-handler access helpers and response serializers.

This module composes the per-resource routers back into the same two router
objects, in the same route-registration order as the original file, so the
public wire contract (path/method/status/response_model/deprecated + route
match order) is unchanged. See
``backend/tests/unit/api/test_workspace_route_contract.py`` for the pinned
contract.

Composition uses ``router.routes.extend(...)`` rather than
``router.include_router(...)``: each per-resource router already carries the
final absolute prefix (``/api/v2/workspaces`` or ``/api/v2``) and matching
tags, so its ``.routes`` are already fully-resolved ``APIRoute`` objects.
Extending the list preserves those routes byte-for-byte (methods, paths,
tags, response models, status codes, deprecated flags) and keeps
``router.routes``/``standalone_router.routes`` a flat list the contract test
can walk directly — ``include_router`` would double the prefix (each
sub-router already has it) and wrap entries instead of flattening them.
"""

from fastapi import APIRouter

from . import collections as _collections
from . import conversations as _conversations
from . import members as _members
from . import messages as _messages
from . import threads as _threads
from . import workspaces as _workspaces

router = APIRouter(prefix="/api/v2/workspaces", tags=["workspaces"])
router.routes.extend(_workspaces.router.routes)
router.routes.extend(_members.router.routes)
router.routes.extend(_conversations.router.routes)
router.routes.extend(_threads.router.routes)
router.routes.extend(_messages.router.routes)
router.routes.extend(_collections.router.routes)

standalone_router = APIRouter(prefix="/api/v2", tags=["workspaces-flat"])
standalone_router.routes.extend(_conversations.standalone_router.routes)
standalone_router.routes.extend(_threads.standalone_router.routes)
standalone_router.routes.extend(_messages.standalone_router.routes)
# list_threads_standalone registers here (after messages, before collections)
# to match the original file's definition order — see threads.py docstring.
standalone_router.routes.extend(_threads.standalone_list_router.routes)
standalone_router.routes.extend(_collections.standalone_router.routes)

__all__ = ["router", "standalone_router"]
