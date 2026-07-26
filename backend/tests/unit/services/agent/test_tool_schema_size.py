"""Tool schemas must not carry the RunnableConfig TypedDict.

``config: RunnableConfig | None = None`` looks equivalent to
``config: RunnableConfig`` but is not: LangChain strips the bare annotation
from the generated schema and does **not** strip the union form. The whole
RunnableConfig TypedDict therefore leaked into all 21 tools — measured at
32,781 of 45,023 schema bytes (73%) — and every ``bind_tools`` call shipped it
on every agent turn, roughly 8k wasted input tokens, plus a phantom parameter
the model could hallucinate into a call.
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.unit


def _schemas() -> list[dict]:
    from langchain_core.utils.function_calling import convert_to_openai_tool

    from src.services.agent.tools import ALL_TOOLS

    return [convert_to_openai_tool(t) for t in ALL_TOOLS]


def test_no_tool_exposes_config_as_a_parameter() -> None:
    offenders = [
        s["function"]["name"]
        for s in _schemas()
        if "config" in s["function"]["parameters"].get("properties", {})
    ]
    assert not offenders, (
        f"{offenders} leak RunnableConfig into the LLM-visible schema — "
        "annotate as bare `RunnableConfig`, not `RunnableConfig | None`"
    )


def test_total_schema_stays_small() -> None:
    """Ceiling well under the pre-fix 45,023 bytes, with room to add tools."""
    total = sum(len(json.dumps(s)) for s in _schemas())
    assert (
        total < 20_000
    ), f"tool schemas total {total} bytes; this ships on every bind_tools call"


def test_project_id_tells_the_model_it_is_a_uuid() -> None:
    """A live run passed the project NAME and the tool hard-failed.

    The parameter was declared with no description, so nothing in the schema
    said it must be a UUID from list_projects/create_project.
    """
    ingest = next(
        s for s in _schemas() if s["function"]["name"] == "ingest_arxiv_papers"
    )
    desc = ingest["function"]["parameters"]["properties"]["project_id"].get(
        "description", ""
    )
    assert "UUID" in desc
    assert "name" in desc.lower(), "must warn that a project name is not accepted"
