"""Contract tests for the code-owned agent tool registry."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from langchain_core.tools import tool

from src.services.agent.tool_registry import (
    AgentIntent,
    AgentSubgraph,
    ToolDescriptor,
    ToolPolicyTag,
    ToolRegistry,
)


@tool
def alpha_tool(value: str) -> str:
    """Return the input unchanged."""
    return value


@tool
def beta_tool(value: str) -> str:
    """Return the input unchanged."""
    return value


def _descriptor(
    *,
    name: str = "alpha_tool",
    tool_object=alpha_tool,
    intents: frozenset[AgentIntent] = frozenset({AgentIntent.GENERAL}),
    subgraphs: frozenset[AgentSubgraph] = frozenset(),
    policy_tags: frozenset[ToolPolicyTag] = frozenset(),
    enabled: bool = True,
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        tool=tool_object,
        intents=intents,
        subgraphs=subgraphs,
        policy_tags=policy_tags,
        enabled=enabled,
    )


@pytest.mark.unit
class TestToolRegistry:
    def test_returns_one_tool_object_per_descriptor_in_declaration_order(self):
        registry = ToolRegistry(
            [_descriptor(name="beta_tool", tool_object=beta_tool), _descriptor()]
        )

        assert registry.all_tools() == (beta_tool, alpha_tool)

    def test_indexes_known_intents_and_subgraphs(self):
        registry = ToolRegistry(
            [
                _descriptor(
                    intents=frozenset({AgentIntent.RESEARCH}),
                    subgraphs=frozenset({AgentSubgraph.RESEARCH}),
                ),
                _descriptor(
                    name="beta_tool",
                    tool_object=beta_tool,
                    intents=frozenset({AgentIntent.WRITING}),
                    subgraphs=frozenset({AgentSubgraph.WRITING}),
                ),
            ]
        )

        assert [item.name for item in registry.descriptors_for_intent("research")] == [
            "alpha_tool"
        ]
        assert [item.name for item in registry.descriptors_for_subgraph("writing")] == [
            "beta_tool"
        ]
        assert registry.descriptors_for_intent("unknown") == ()
        assert registry.descriptors_for_subgraph("unknown") == ()

    def test_policy_tags_are_queryable(self):
        registry = ToolRegistry(
            [
                _descriptor(
                    policy_tags=frozenset(
                        {
                            ToolPolicyTag.DESTRUCTIVE,
                            ToolPolicyTag.SLOW,
                            ToolPolicyTag.NO_OUTER_RETRY,
                        }
                    )
                )
            ]
        )

        assert registry.has_policy("alpha_tool", ToolPolicyTag.DESTRUCTIVE)
        assert registry.has_policy("alpha_tool", ToolPolicyTag.SLOW)
        assert registry.has_policy("alpha_tool", ToolPolicyTag.NO_OUTER_RETRY)
        assert not registry.has_policy("missing", ToolPolicyTag.DESTRUCTIVE)

    def test_descriptor_metadata_is_immutable_and_snapshot_is_stable(self):
        descriptor = _descriptor(policy_tags=frozenset({ToolPolicyTag.SLOW}))
        registry = ToolRegistry([descriptor])

        with pytest.raises(FrozenInstanceError):
            descriptor.name = "renamed"  # type: ignore[misc]

        assert (
            registry.metadata_snapshot()
            == ToolRegistry([descriptor]).metadata_snapshot()
        )
        assert set(registry.metadata_snapshot()) == {"version", "hash"}

    def test_rejects_duplicate_names_and_invalid_descriptor_contracts(self):
        with pytest.raises(ValueError, match="duplicate"):
            ToolRegistry([_descriptor(), _descriptor(tool_object=beta_tool)])

        with pytest.raises(ValueError, match="must match"):
            ToolRegistry([_descriptor(name="not_the_tool_name")])

        with pytest.raises(TypeError, match="AgentIntent"):
            ToolRegistry([_descriptor(intents=frozenset({"general"}))])  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="no_outer_retry"):
            ToolRegistry(
                [_descriptor(policy_tags=frozenset({ToolPolicyTag.NO_OUTER_RETRY}))]
            )
