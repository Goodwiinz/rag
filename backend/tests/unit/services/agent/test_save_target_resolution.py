"""A missing save target must be resolved, not handed back to the user.

Live on dev (synthetic ``writing_draft``, 2026-07-27), 5 runs out of 5 —
"Write a short note summarizing the key ideas behind RAG and save it to my
library." finished with ``tool_executions=0`` and this reply::

    I can write it, but I need a save location first: which project should I
    put the note in?

Nothing was saved and no error was raised. The model's reasoning was locally
correct: ``SHARED_AGENT_RULES`` only forbade asking for a project_id "when it
is already available in tool history", and on a fresh thread there is no tool
history — so it treated the project as unknowable and asked.

The rule that would have stopped it did exist, but only inside
``render_plan_directive`` ("Do NOT ask the user for document_ids or arXiv IDs
that you can resolve yourself"), which returns ``None`` for an empty plan. And
``planner_node`` returns early unless ``page_context["type"] == "project"``, so
in plain chat the plan is always ``[]`` and that guidance never reaches the
executor at all.

Hence the fix belongs in the shared rules, which are unconditional: a save
target is one read-only ``list_projects`` call away, so asking for it strands
work the user already requested.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestSharedRulesTeachResolution:
    def test_rules_name_list_projects_as_the_resolution_step(self) -> None:
        from src.services.agent._prompts import SHARED_AGENT_RULES

        assert "Resolving a save target" in SHARED_AGENT_RULES
        assert "list_projects FIRST" in SHARED_AGENT_RULES

    def test_rules_cover_the_no_match_case(self) -> None:
        """Resolution must not dead-end when the user has no suitable project."""
        from src.services.agent._prompts import SHARED_AGENT_RULES

        assert "create_project" in SHARED_AGENT_RULES

    def test_asking_first_is_named_and_forbidden(self) -> None:
        """The observed failure phrasing, so the rule targets the real behaviour."""
        from src.services.agent._prompts import SHARED_AGENT_RULES

        section = SHARED_AGENT_RULES.split("## Resolving a save target", 1)[1]
        section = section.split("## ", 1)[0]

        assert "which project should I put this in?" in section
        assert "Never" in section


class TestGuidanceIsNotCoupledToAPlan:
    """Why the shared rules are the fix site rather than the plan directive."""

    def test_an_empty_plan_renders_no_directive(self) -> None:
        from src.services.agent.planner import render_plan_directive

        assert render_plan_directive([]) is None
        assert render_plan_directive(None) is None

    def test_shared_rules_are_unconditional_text(self) -> None:
        """No plan, no page context, no tool history — the rule still applies."""
        from src.services.agent._prompts import SHARED_AGENT_RULES

        assert isinstance(SHARED_AGENT_RULES, str)
        assert "Resolving a save target" in SHARED_AGENT_RULES
