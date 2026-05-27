"""Phase 9.D — project_report.html template renders with sample data.

Smoke-test the Jinja template directly (no FastAPI / no DB) so the
test runs fast and stays focused on template correctness.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


@pytest.fixture
def env() -> Environment:
    templates_dir = Path(__file__).parent.parent.parent.parent / "templates"
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


@pytest.mark.unit
def test_template_renders_with_full_payload(env: Environment) -> None:
    template = env.get_template("project_report.html")
    html = template.render(
        project={
            "id": "5ed25258-5ad2-4b06-9678-4a4abe5ecac1",
            "name": "ML in Health Care",
            "description": "Recent papers on machine learning in healthcare.",
            "created_at": "2026-04-01T00:00:00+00:00",
        },
        documents=[
            {
                "id": "uuid-doc-1",
                "title": "Privacy-preserving ML for healthcare",
                "filename": "2303.15563.pdf",
                "status": "indexed",
                "added_at": "2026-05-01T12:00:00",
            }
        ],
        notes=[
            {
                "id": "uuid-note-1",
                "title": "Reading list",
                "content": "Top 5 papers to read this week.",
                "created_at": "2026-05-02T09:00:00",
            }
        ],
        threads=[
            {
                "thread_id": "297509eb-6ee5-4d00-9202-849cfaa189d0",
                "latest_turn": 3,
                "updated_at": "2026-05-12T01:00:00",
                "user_query": "find recent transformer papers",
                "intent": "research",
                "tools_used": ["search_arxiv", "ingest_arxiv_papers"],
                "tool_executions_count": 3,
            }
        ],
        generated_at="2026-05-12T02:00:00",
        ledger_enabled=True,
    )

    # Smoke-test the structure
    assert "<!DOCTYPE html>" in html
    assert "ML in Health Care" in html
    assert "Privacy-preserving ML for healthcare" in html
    assert "Reading list" in html
    assert "find recent transformer papers" in html
    assert "search_arxiv, ingest_arxiv_papers" in html
    # Counts in the stat strip
    assert ">1<" in html  # at least one stat shows "1"


@pytest.mark.unit
def test_template_renders_with_no_data_and_ledger_disabled(env: Environment) -> None:
    """Empty project + ledger off → template falls back to friendly empty
    states without crashing."""
    template = env.get_template("project_report.html")
    html = template.render(
        project={
            "id": "uuid-empty",
            "name": "Empty project",
            "description": "",
            "created_at": None,
        },
        documents=[],
        notes=[],
        threads=[],
        generated_at="2026-05-12T02:00:00",
        ledger_enabled=False,
    )
    assert "Empty project" in html
    assert "No documents in this project yet." in html
    assert "No notes yet." in html
    assert "Iteration ledger disabled" in html


@pytest.mark.unit
def test_template_escapes_html_in_user_data(env: Environment) -> None:
    """User-supplied content (titles, queries, note bodies) must not bleed
    raw HTML into the report."""
    template = env.get_template("project_report.html")
    html = template.render(
        project={
            "id": "x",
            "name": "<script>alert(1)</script>",
            "description": "<img src=x onerror=alert(1)>",
            "created_at": None,
        },
        documents=[],
        notes=[],
        threads=[],
        generated_at="2026-05-12T02:00:00",
        ledger_enabled=False,
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
