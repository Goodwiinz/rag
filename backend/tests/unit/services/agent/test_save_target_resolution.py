"""A missing save target must be resolved, not handed back to the user.

Live on dev (synthetic ``writing_draft``, 2026-07-27), 5 runs out of 5 —
"Write a short note summarizing the key ideas behind RAG and save it to my
library." finished with ``tool_executions=0`` and this reply::

    I can write it, but I need a save location first: which project should I
    put the note in?

Nothing was saved and no error was raised.

Three things had to line up for that, and all three are covered here:

1. ``list_projects`` was bound to the research subgraph only, so the writing
   executor had no tool that could answer "which project?" — asking was the
   only move left to it. This is the load-bearing fix; the prompt wording
   below is useless without it.
2. ``AGENTS_writing.md`` explicitly sanctioned the question ("The only thing
   you may need to ask for is the save destination"), and the driver protocol
   is concatenated *before* ``SHARED_AGENT_RULES`` in
   ``_build_writing_system_prompt``, so the model met the permission first.
3. The rule that would have stopped it lived only in
   ``render_plan_directive``, which returns ``None`` for an empty plan — and
   ``planner_node`` returns early unless ``page_context["type"] ==
   "project"``, so in plain chat the plan is always ``[]``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_WRITING_PROTOCOL = (
    Path(__file__).resolve().parents[4]
    / "src"
    / "services"
    / "agent"
    / "subgraphs"
    / "AGENTS_writing.md"
)


class TestWritingCanActuallyResolveAProject:
    """The fix that matters: the tool has to be reachable from writing."""

    def test_list_projects_is_bound_to_the_writing_subgraph(self) -> None:
        from src.services.agent.tools import TOOL_REGISTRY

        names = {d.name for d in TOOL_REGISTRY.descriptors_for_subgraph("writing")}

        assert "list_projects" in names, (
            "create_project_note/create_draft need a project_id; without "
            "list_projects the writing executor can only ask the user for it"
        )

    def test_list_projects_stays_available_to_research(self) -> None:
        """Widening the binding must not move the tool off its original graph."""
        from src.services.agent.tools import TOOL_REGISTRY

        names = {d.name for d in TOOL_REGISTRY.descriptors_for_subgraph("research")}

        assert "list_projects" in names

    def test_binding_adds_no_destructive_surface(self) -> None:
        """list_projects is read-only — it must not start raising interrupts."""
        from src.services.agent._nodes_tools import DESTRUCTIVE_TOOLS

        assert "list_projects" not in DESTRUCTIVE_TOOLS


class TestTheProtocolNoLongerSanctionsAsking:
    def test_writing_protocol_does_not_bless_asking_for_a_destination(self) -> None:
        text = _WRITING_PROTOCOL.read_text()

        assert (
            "The only thing you may need to ask for is the **save destination**"
            not in text
        ), "the driver protocol is read before SHARED_AGENT_RULES and wins ties"

    def test_writing_protocol_points_at_list_projects(self) -> None:
        assert "list_projects" in _WRITING_PROTOCOL.read_text()


class TestSharedRulesTeachResolution:
    def test_rules_name_list_projects_as_the_resolution_step(self) -> None:
        from src.services.agent._prompts import SHARED_AGENT_RULES

        assert "Resolving a save target" in SHARED_AGENT_RULES
        assert "list_projects FIRST" in SHARED_AGENT_RULES

    def test_asking_first_is_named_and_forbidden(self) -> None:
        """Pin the observed failure phrasing so the rule targets real behaviour."""
        from src.services.agent._prompts import SHARED_AGENT_RULES

        section = SHARED_AGENT_RULES.split("## Resolving a save target", 1)[1]
        section = section.split("\n## ", 1)[0]

        assert "which project should I put this in?" in section
        assert "Never" in section

    def test_the_write_waits_for_the_project_id(self) -> None:
        """create_project is destructive → the graph suspends on the interrupt.

        Telling the model to create and write "in the same turn" invites it to
        narrate both as done, which is the fake-success shape this codebase
        keeps producing.
        """
        from src.services.agent._prompts import SHARED_AGENT_RULES

        section = SHARED_AGENT_RULES.split("## Resolving a save target", 1)[1]
        section = section.split("\n## ", 1)[0]

        assert "in the same turn" not in section
        assert "project_id comes back" in section


class TestGuidanceIsNotCoupledToAPlan:
    """Why the shared rules are a fix site rather than the plan directive."""

    def test_an_empty_plan_renders_no_directive(self) -> None:
        from src.services.agent.planner import render_plan_directive

        assert render_plan_directive([]) is None
        assert render_plan_directive(None) is None
