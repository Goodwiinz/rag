from pathlib import Path


def test_data_prompt_forbids_explaining_untyped_edges() -> None:
    prompt = (
        Path(__file__).parents[3]
        / "src/services/agent/subgraphs/AGENTS_data.md"
    ).read_text()
    assert "Only state the relationship label returned by the graph" in prompt
    assert "Do not infer why two entities are related" in prompt
