"""Advice that names a tool must name one the caller can reach.

``summarize_document`` is bound **only** to the writing subgraph. Handed a
project id instead of a document id — a real agent mistake, trace 019f4386,
which is why the branch exists — it answers with prose telling the model to
``Call list_project_documents(project_id=...)``. That tool was bound to
research and data, never to writing, so ``make_filtered_tool_node`` replied
"not available in this context" and the summarize request died there.

Same shape as #1284, where a shared prompt rule told the writing executor to
call ``list_projects`` before that tool was bound to writing.

**What reaches the model.** Message prose always does. A tool's own
``suggestion`` field did *not* until ``classify_error_from_payload`` was
changed to honour tool declarations — before that, ``_nodes_tools`` rebuilt
the ToolMessage and the field was dropped (the tool returned
``error_type="recoverable", suggestion="list_project_documents"`` and the
model received ``{"error": "…", "error_type": "fatal"}``). Now that declared
suggestions are delivered, the guards below cover all three channels: message
prose, the ``TOOL_ERROR_HINTS`` table, and declared ``suggestion`` literals.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Set

import pytest

pytestmark = pytest.mark.unit

_AGENT = Path(__file__).resolve().parents[4] / "src" / "services" / "agent"


def _subgraph_names() -> List[str]:
    """Derived, so a new subgraph cannot silently fall out of coverage."""
    from src.services.agent.tool_registry import AgentSubgraph

    return [s.value for s in AgentSubgraph]


def _bindings() -> Dict[str, Set[str]]:
    from src.services.agent.tools import TOOL_REGISTRY

    bound: Dict[str, Set[str]] = {}
    for subgraph in _subgraph_names():
        for descriptor in TOOL_REGISTRY.descriptors_for_subgraph(subgraph):
            bound.setdefault(descriptor.name, set()).add(subgraph)
    return bound


def _unfollowable(
    sources: Iterable[tuple[str, str]] | None = None,
    bound: Dict[str, Set[str]] | None = None,
) -> List[str]:
    """Advice naming a tool the emitting tool's subgraphs cannot call.

    Params are injectable so the guard itself can be tested against planted
    input rather than only against a tree that currently passes.
    """
    bound = _bindings() if bound is None else bound
    if sources is None:
        sources = [
            (p.name, (_AGENT / p.name).read_text())
            for p in (_AGENT / "tools_impl.py", _AGENT / "tools.py")
        ]

    known = set(bound)
    problems: List[str] = []
    for filename, source in sources:
        for match in re.finditer(r"(?:async )?def (?:_tool_)?(\w+)\(", source):
            name = match.group(1)
            if name not in known:
                continue
            nxt = source.find("\ndef ", match.end())
            nxt_async = source.find("\nasync def ", match.end())
            end = min(x for x in (nxt, nxt_async, len(source)) if x > 0)
            # Comments are not delivered to the model — only docstrings, Field
            # descriptions and error strings are. Scanning them would flag the
            # very notes that explain why a tool is *not* named.
            body = "\n".join(
                line
                for line in source[match.end() : end].splitlines()
                if not line.lstrip().startswith("#")
            )
            # Every other tool named anywhere in this tool's error strings.
            named = {
                other
                for other in known
                if other != name and re.search(rf"\b{other}\b", body)
            }
            for other in named:
                missing = bound[name] - bound[other]
                if missing:
                    problems.append(
                        f"{filename}:{name} (in {sorted(bound[name])}) points at "
                        f"{other} (only in {sorted(bound[other])}) — unreachable "
                        f"from {sorted(missing)}"
                    )
    return problems


def _hint_problems() -> List[str]:
    """TOOL_ERROR_HINTS entries survive classification and are delivered."""
    from src.services.agent.error_recovery import TOOL_ERROR_HINTS

    bound = _bindings()
    problems: List[str] = []
    for (tool, _fragment), (_category, hint) in TOOL_ERROR_HINTS.items():
        if tool not in bound:
            continue
        for other in bound:
            if other == tool or not re.search(rf"\b{other}\b", hint):
                continue
            missing = bound[tool] - bound[other]
            if missing:
                problems.append(
                    f"hint for {tool} names {other}, unreachable from {sorted(missing)}"
                )
    return problems


class TestWritingCanFollowItsOwnAdvice:
    def test_list_project_documents_is_bound_to_writing(self) -> None:
        assert "writing" in _bindings()["list_project_documents"], (
            "summarize_document is writing-only and its error tells the model "
            "to call list_project_documents; without the binding that is dead"
        )

    def test_other_subgraphs_keep_it(self) -> None:
        assert {"research", "data"} <= _bindings()["list_project_documents"]

    def test_binding_adds_no_destructive_surface(self) -> None:
        from src.services.agent.graph import DESTRUCTIVE_TOOLS

        assert "list_project_documents" not in DESTRUCTIVE_TOOLS
        assert "list_projects" not in DESTRUCTIVE_TOOLS


def _declared_suggestion_problems() -> List[str]:
    """``"suggestion": "<tool>"`` literals are delivered now — check them too."""
    bound = _bindings()
    problems: List[str] = []
    for filename in ("tools_impl.py", "tools.py"):
        source = (_AGENT / filename).read_text()
        for match in re.finditer(r"(?:async )?def (?:_tool_)?(\w+)\(", source):
            name = match.group(1)
            if name not in bound:
                continue
            nxt = source.find("\ndef ", match.end())
            nxt_async = source.find("\nasync def ", match.end())
            end = min(x for x in (nxt, nxt_async, len(source)) if x > 0)
            body = source[match.end() : end]
            for suggested in re.findall(r'"suggestion":\s*"([a-z_]+)"', body):
                if suggested not in bound:
                    continue
                missing = bound[name] - bound[suggested]
                if missing:
                    problems.append(
                        f"{filename}:{name} declares suggestion {suggested}, "
                        f"unreachable from {sorted(missing)}"
                    )
    return problems


class TestDeliveredHintsAreReachable:
    def test_no_declared_suggestion_names_an_unreachable_tool(self) -> None:
        problems = _declared_suggestion_problems()

        assert not problems, "; ".join(problems)

    def test_no_tool_error_hint_names_an_unreachable_tool(self) -> None:
        assert not _hint_problems(), "; ".join(_hint_problems())

    def test_no_tool_message_points_at_an_unreachable_tool(self) -> None:
        problems = _unfollowable()

        assert not problems, "unfollowable advice: " + "; ".join(problems)


class TestTheGuardActuallyGuards:
    """A guard nobody tested is a guard that passes vacuously."""

    def test_it_flags_a_planted_mismatch(self) -> None:
        planted = [
            (
                "fake.py",
                "async def _tool_summarize_document(x):\n"
                '    return {"error": "Call list_project_documents first."}\n',
            )
        ]
        bound = {"summarize_document": {"writing"}, "list_project_documents": {"data"}}

        problems = _unfollowable(planted, bound)

        assert problems, "the sweep must catch advice its subgraph cannot follow"
        assert "list_project_documents" in problems[0]

    def test_it_stays_quiet_when_the_tool_is_reachable(self) -> None:
        planted = [
            (
                "fake.py",
                "async def _tool_summarize_document(x):\n"
                '    return {"error": "Call list_project_documents first."}\n',
            )
        ]
        bound = {
            "summarize_document": {"writing"},
            "list_project_documents": {"data", "writing"},
        }

        assert _unfollowable(planted, bound) == []
