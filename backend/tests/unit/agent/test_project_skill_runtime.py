"""Runtime prompt/binding contracts for frozen project skills."""

from types import SimpleNamespace
from unittest.mock import patch


def test_skill_catalog_prompt_is_compact_deterministic_and_instructs_loader_use():
    from src.services.agent.runtime_snapshot import render_project_skill_catalog

    prompt = render_project_skill_catalog(
        [
            {
                "name": "literature-review",
                "description": "Use the project review rubric.",
                "version": 2,
                "content_hash": "a" * 64,
            }
        ]
    )

    assert "literature-review (v2)" in prompt
    assert "load_project_skill(skill_name)" in prompt
    assert "Use the project review rubric." in prompt
    assert "a" * 64 not in prompt


def test_main_loader_binding_requires_enabled_runtime_and_frozen_catalog():
    from src.services.agent._nodes_llm import tools_for_runtime_snapshot

    state = {
        "runtime_snapshot_id": "snapshot-1",
        "project_skill_catalog": [{"name": "literature-review"}],
    }
    with patch(
        "src.services.agent._nodes_llm.get_settings",
        return_value=SimpleNamespace(PROJECT_SKILL_RUNTIME_ENABLED=True),
    ):
        tools = tools_for_runtime_snapshot([], state)
    assert [tool.name for tool in tools] == ["load_project_skill"]

    with patch(
        "src.services.agent._nodes_llm.get_settings",
        return_value=SimpleNamespace(PROJECT_SKILL_RUNTIME_ENABLED=False),
    ):
        assert tools_for_runtime_snapshot([], state) == []
