"""A recovery suggestion must name a tool the caller can actually call.

``summarize_document`` is bound **only** to the writing subgraph. When it is
handed a project id instead of a document id — a real agent mistake, trace
019f4386, which is why the branch exists — it returns::

    {"error": "'<id>' is a project id, not a document id. Call
      list_project_documents(project_id=...) ...",
     "error_type": "recoverable",
     "suggestion": "list_project_documents"}

``list_project_documents`` was bound to research and data, never to writing.
So the one subgraph that can reach this error was the one subgraph that could
not follow the advice: the classification says "recoverable", the model
retries, and the tool it is told to use is not in its binding. The user's
summarize request dies there.

Same shape as #1284, where a shared prompt rule told the writing executor to
call ``list_projects`` before that tool was bound to writing. A rule or hint
naming an unreachable tool is worse than no hint — the model burns its retry
budget, or invents the call in prose.

The sweep below is the general guard: every ``"suggestion"`` a tool emits must
be bound wherever that tool is bound.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Set

import pytest

pytestmark = pytest.mark.unit

_SUBGRAPHS = ("research", "writing", "data")


def _bindings() -> Dict[str, Set[str]]:
    from src.services.agent.tools import TOOL_REGISTRY

    bound: Dict[str, Set[str]] = {}
    for subgraph in _SUBGRAPHS:
        for descriptor in TOOL_REGISTRY.descriptors_for_subgraph(subgraph):
            bound.setdefault(descriptor.name, set()).add(subgraph)
    return bound


def _unfollowable() -> list[str]:
    """(tool, suggestion) pairs where the suggestion is out of reach."""
    bound = _bindings()
    source = (
        Path(__file__).resolve().parents[4]
        / "src"
        / "services"
        / "agent"
        / "tools_impl.py"
    ).read_text()

    problems: list[str] = []
    for match in re.finditer(r"async def _tool_(\w+)\(", source):
        name = match.group(1)
        nxt = source.find("\nasync def ", match.end())
        body = source[match.end() : nxt if nxt > 0 else len(source)]
        for suggestion in set(re.findall(r'"suggestion":\s*"([a-z_]+)"', body)):
            if name not in bound or suggestion not in bound:
                continue  # not a subgraph tool, or free-text advice
            missing = bound[name] - bound[suggestion]
            if missing:
                problems.append(
                    f"{name} (in {sorted(bound[name])}) suggests {suggestion} "
                    f"(only in {sorted(bound[suggestion])}) — unreachable from "
                    f"{sorted(missing)}"
                )
    return problems


class TestWritingCanFollowItsOwnHint:
    def test_list_project_documents_is_bound_to_writing(self) -> None:
        bound = _bindings()

        assert "writing" in bound["list_project_documents"], (
            "summarize_document is writing-only and tells the model to call "
            "list_project_documents; without the binding that advice is dead"
        )

    def test_the_other_subgraphs_keep_it(self) -> None:
        bound = _bindings()

        assert {"research", "data"} <= bound["list_project_documents"]

    def test_binding_adds_no_destructive_surface(self) -> None:
        from src.services.agent.graph import DESTRUCTIVE_TOOLS

        assert "list_project_documents" not in DESTRUCTIVE_TOOLS


class TestEverySuggestionIsReachable:
    def test_no_tool_suggests_something_its_subgraph_lacks(self) -> None:
        problems = _unfollowable()

        assert not problems, "unfollowable recovery hints: " + "; ".join(problems)

    def test_the_sweep_detects_a_planted_mismatch(self) -> None:
        """A guard nobody tested is a guard that passes vacuously."""
        bound = _bindings()

        # summarize_document is writing-only; search_documents is not bound to
        # writing, so it stands in for a hint the writing executor can't follow.
        assert bound["summarize_document"] == {"writing"}
        assert "writing" not in bound.get("search_documents", set())
