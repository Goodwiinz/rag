"""LangGraph agent service."""

# Eagerly import submodules that production code loads lazily, so that
# ``mock.patch("src.services.agent.<submodule>.<attr>", ...)`` can resolve
# the attribute chain via ``pkgutil.resolve_name`` without us having to
# sprinkle ``import`` statements at the top of every test file.
#
# See: the ``graph`` module is consumed through lazy imports inside
# ``src.api.agent.streaming``; without this eager import, patch targets
# like ``src.services.agent.graph.compile_agent_graph`` raise
# ``AttributeError: module 'src.services.agent' has no attribute 'graph'``
# before the function under test ever runs.
from . import graph  # noqa: F401
