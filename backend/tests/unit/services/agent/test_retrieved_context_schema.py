"""score_source must survive into AgentExecuteResponse.retrieved_contexts —
it is set by the DO KB path (upstream/rank_proxy/cohere) and was silently
dropped by the response schema (audit 2026-08-07, gap 4)."""

from src.services.agent.schemas import RetrievedContextResponse


def test_score_source_flows_through() -> None:
    rc = RetrievedContextResponse(
        document_id=None,
        title="t",
        content="c",
        score=0.9,
        score_source="cohere",
    )
    assert rc.score_source == "cohere"


def test_score_source_defaults_to_none() -> None:
    rc = RetrievedContextResponse(title="t", content="c", score=0.1)
    assert rc.score_source is None
