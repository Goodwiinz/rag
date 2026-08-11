from pathlib import Path


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
    assert (
        "none was returned within the requested depth, limit, and tool scope" in prompt
    )
    assert "Never assert global nonexistence from a bounded or empty result" in prompt
    assert "When a relationship doesn't exist" not in prompt
    assert (
        "exact headings `Returned neighborhood` and `Organization graph totals`"
        in prompt
    )
    assert (
        "Never describe organization-graph counts or distributions as returned "
        "neighborhood instances" in prompt
    )
    assert "Use a factual ledger, not narrative characterization" in prompt
    assert "network, community, colleague, research area, or context" in prompt
    assert "reproduce every returned type and count under its tool scope" in prompt
    assert "Do not reduce it to a “most common” summary" in prompt
    assert "exact `source --TYPE--> target` rows" in prompt
