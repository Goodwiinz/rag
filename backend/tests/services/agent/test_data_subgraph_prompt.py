import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.services.agent.subgraphs.data_agent import data_llm_node


def test_data_prompt_forbids_explaining_untyped_edges() -> None:
    prompt = (
        Path(__file__).parents[3] / "src/services/agent/subgraphs/AGENTS_data.md"
    ).read_text()
    assert "Only state the relationship label returned by the graph" in prompt
    assert "Do not infer why two entities are related" in prompt


def test_data_prompt_separates_graph_scopes_and_grounding_claims() -> None:
    prompt = (
        Path(__file__).parents[3] / "src/services/agent/subgraphs/AGENTS_data.md"
    ).read_text()
    assert "use the returned entity id" in prompt
    assert "get the canonical id" not in prompt
    assert "Keep tool scopes separate" in prompt
    assert "returned-neighborhood counts separately" in prompt
    assert "requested depth or result limit does not prove an exact hop" in prompt
    assert "Do not infer canonicality, uniqueness, or completeness" in prompt
    assert "Enumerate only entity and relationship rows actually returned" in prompt
    assert "Distributions are qualified aggregates" in prompt


@pytest.mark.unit
@pytest.mark.asyncio
async def test_data_synthesis_keeps_neighborhood_and_org_aggregates_separate() -> None:
    neighborhood = {
        "scope": "entity_neighborhood",
        "center_entity_id": "entity-1",
        "requested_max_depth": 2,
        "result_limit": 10,
        "connected_entities": [
            {"id": "entity-1", "name": "Atlas"},
            {"id": "entity-2", "name": None},
        ],
        "relationships": [{"source": "entity-1", "target": "entity-2"}],
        "total_entities": 2,
        "total_relationships": 1,
        "returned_entity_count": 2,
        "returned_relationship_count": 1,
    }
    graph_stats = {
        "scope": "organization_graph",
        "total_entities": 8,
        "total_relationships": 7,
        "entity_type_distribution": {"MODEL": 3},
        "relationship_type_distribution": {"RELATED_TO": 4},
    }
    captured: dict = {}

    async def fake_ainvoke(messages, config=None):
        captured["messages"] = messages
        system_text = "\n".join(
            str(message.content)
            for message in messages
            if isinstance(message, SystemMessage)
        )
        payloads = [
            json.loads(message.content)
            for message in messages
            if isinstance(message, ToolMessage)
        ]
        contract_is_grounded = (
            "Keep tool scopes separate" in system_text
            and "Do not infer canonicality, uniqueness, or completeness" in system_text
            and {payload["scope"] for payload in payloads}
            == {"entity_neighborhood", "organization_graph"}
        )
        if not contract_is_grounded:
            return AIMessage(
                content=(
                    "The complete exact-hop graph has 8 canonical unique entities, "
                    "including unreturned Orion."
                )
            )
        return AIMessage(
            content=(
                "Returned neighborhood: 2 entities and 1 relationship; the returned "
                "named entity is Atlas. Organization graph totals: 8 entities and 7 "
                "relationships. The organization-level aggregate reports 3 MODEL "
                "entities; it does not identify any unreturned members."
            )
        )

    bound_llm = MagicMock()
    bound_llm.ainvoke = fake_ainvoke
    llm = MagicMock()
    llm.bind_tools.return_value = bound_llm
    settings = SimpleNamespace(
        AGENT_LIGHTWEIGHT_SYNTHESIS=True,
        AGENT_PARALLEL_TOOL_CALLS=False,
    )
    state = {
        "messages": [
            HumanMessage(content="Summarize the neighborhood and graph overview."),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "neighborhood-call",
                        "name": "explore_entity_neighborhood",
                        "args": {"entity_id": "entity-1"},
                    }
                ],
            ),
            ToolMessage(
                content=json.dumps(neighborhood),
                tool_call_id="neighborhood-call",
                name="explore_entity_neighborhood",
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "stats-call", "name": "get_graph_stats", "args": {}}
                ],
            ),
            ToolMessage(
                content=json.dumps(graph_stats),
                tool_call_id="stats-call",
                name="get_graph_stats",
            ),
        ]
    }

    with (
        patch("src.core.config.get_settings", return_value=settings),
        patch("src.services.agent.llm_factory.build_synthesis_llm", return_value=llm),
    ):
        result = await data_llm_node(state, config={})

    response = str(result["messages"][0].content)
    assert "Returned neighborhood: 2 entities and 1 relationship" in response
    assert "Organization graph totals: 8 entities and 7 relationships" in response
    assert "Atlas" in response
    assert "organization-level aggregate" in response
    assert "does not identify any unreturned members" in response
    assert "Orion" not in response
    for unsupported_claim in ("canonical", "unique", "complete", "exact-hop"):
        assert unsupported_claim not in response.lower()
    assert captured["messages"]
