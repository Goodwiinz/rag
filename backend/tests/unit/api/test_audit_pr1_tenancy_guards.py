"""PR1 (audit R6-H2/H4/H5, R5-M7/M8, R6-L2/L10) regression guards.

Behavioral where cheap (config validators, graph service fail-closed),
source-guards where the code path needs live infra (Neo4j, route wiring).
"""

import ast
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# R6-H4 — ENVIRONMENT gates read Settings, not os.getenv
# ---------------------------------------------------------------------------


def test_config_prod_gates_fire_without_process_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulates a deployment supplying ENVIRONMENT only via .env / init value.

    Before the fix the validators read os.getenv("ENVIRONMENT") and silently
    accepted weak secrets in production.
    """
    import os
    import sys

    sys.path.insert(0, str(BACKEND_ROOT))
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    from src.core.config import Settings

    # Hermetic production baseline: unrelated validators must not fire before
    # the secret gates we're asserting on (full-suite runs leak LOG_LEVEL /
    # DATABASE_URL-class vars into the process env; SUPABASE_DB_URL is pinned
    # empty because _override_database_url_from_supabase lets an env value
    # beat our explicit DATABASE_URL).
    base: dict[str, Any] = dict(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql://u:p@db.example.com:5432/db",
        SUPABASE_DB_URL="",
        CORS_ORIGIN_REGEX="",
        NEO4J_URI="neo4j://neo4j.example.com:7687",
        NEO4J_PASSWORD="n" * 24,
    )

    with pytest.raises(Exception, match="JWT_SECRET_KEY"):
        Settings(SECRET_KEY="s" * 40, JWT_SECRET_KEY="", **base)

    with pytest.raises(Exception, match="SECRET_KEY"):
        Settings(SECRET_KEY="", JWT_SECRET_KEY="j" * 40, **base)

    # Dev still auto-generates instead of raising.
    s = Settings(
        ENVIRONMENT="development",
        JWT_SECRET_KEY="j" * 40,
        DATABASE_URL="postgresql://u:p@localhost/db",
        SUPABASE_DB_URL="",
    )
    assert s.SECRET_KEY


def test_config_has_no_os_getenv_environment_reads() -> None:
    source = (BACKEND_ROOT / "src/core/config.py").read_text()
    assert 'os.getenv("ENVIRONMENT"' not in source
    assert 'info.data.get("ENVIRONMENT"' in source


# ---------------------------------------------------------------------------
# R6-H2 — LLM cache keys are tenant- and system-prompt-scoped
# ---------------------------------------------------------------------------


def test_chat_cache_query_includes_tenant_and_system_prompt() -> None:
    source = (BACKEND_ROOT / "src/api/research/chat.py").read_text()
    assert "tenant_scope" in source
    assert "current_user.organization_id" in source
    assert "system_prompt_hash" in source
    # The scope must be part of cache_query before both cache.get and cache.set
    get_pos = source.find("llm_response_cache.get")
    set_pos = source.find("llm_response_cache.set")
    scope_pos = source.find('cache_query = f"{tenant_scope}')
    assert 0 < scope_pos < get_pos < set_pos


# ---------------------------------------------------------------------------
# R6-H5 — citation graph is org-partitioned end to end
# ---------------------------------------------------------------------------


def test_citation_graph_read_requires_organization_id() -> None:
    import sys

    sys.path.insert(0, str(BACKEND_ROOT))
    from src.services.research.citation_graph_service import CitationGraphService

    svc = CitationGraphService()
    with pytest.raises(ValueError, match="organization_id"):
        # Must fail closed BEFORE any driver/connection work.
        import asyncio

        asyncio.run(svc.get_citation_graph(project_id=None, document_id=None))


def _service_source(rel: str) -> str:
    return (BACKEND_ROOT / rel).read_text()


def test_citation_graph_queries_carry_org_scope() -> None:
    source = _service_source("src/services/research/citation_graph_service.py")
    # Sync writes tenant properties onto the node...
    assert "c.organization_id = $organization_id" in source
    assert "c.project_id = $project_id" in source
    # ...reads anchor every branch inside the caller's partition...
    assert "start.organization_id = $organization_id" in source
    # ...and traversal results are post-filtered so pre-existing foreign
    # nodes can never reach the payload.
    assert 'r.get("organization_id") == organization_id' in source


def test_citation_graph_route_passes_org() -> None:
    source = (BACKEND_ROOT / "src/api/research/citations.py").read_text()
    get_call = source[source.find("graph_service.get_citation_graph") :]
    assert "organization_id=str(current_user.organization_id)" in get_call[:400]


# ---------------------------------------------------------------------------
# R5-M7 — relationship delete honors the same org partition as reads
# ---------------------------------------------------------------------------


def test_delete_relationship_signature_and_scope() -> None:
    import inspect
    import sys

    sys.path.insert(0, str(BACKEND_ROOT))
    from src.services.knowledge_graph.knowledge_graph_service import (
        KnowledgeGraphService,
    )

    sig = inspect.signature(KnowledgeGraphService.delete_relationship)
    assert "organization_id" in sig.parameters

    source = _service_source("src/services/knowledge_graph/knowledge_graph_service.py")
    delete_block = source[
        source.find("def delete_relationship") : source.find(
            "def find_related_entities"
        )
    ]
    # Uses the shared two-endpoint scope helper (org-preferred), not a bare
    # source_document_id IN-list that arXiv entities can never match.
    assert "_two_endpoint_scope(" in delete_block
    assert "$relationship_id" in delete_block


# ---------------------------------------------------------------------------
# R5-M8 — analytics endpoint passes the org partition, not just doc ids
# ---------------------------------------------------------------------------


def test_analytics_route_passes_organization_id() -> None:
    source = (BACKEND_ROOT / "src/api/search/knowledge_graph.py").read_text()
    call = source[source.find("knowledge_graph_service.get_graph_analytics") :]
    assert "organization_id=str(current_user.organization_id)" in call[:400]


# ---------------------------------------------------------------------------
# R6-L10 — message-citation document fetch excludes soft-deleted rows
# ---------------------------------------------------------------------------


def test_message_citation_document_fetch_is_delete_aware() -> None:
    source = (
        BACKEND_ROOT / "src/services/research/message_citation_service.py"
    ).read_text()
    block = source[source.find("async def _get_document") :]
    assert "Document.is_deleted == False" in block[:900]
    assert "organization_id" in block[:900]


# ---------------------------------------------------------------------------
# R6-L2 — title enrichment cannot leak deleted/foreign documents' titles
# ---------------------------------------------------------------------------


def test_title_enrichment_query_is_scoped() -> None:
    source = (BACKEND_ROOT / "src/services/search/hybrid_search_service.py").read_text()
    block = source[source.find("def _enrich_titles_from_db") :]
    assert "NOT is_deleted" in block[:1600]
    assert "organization_id = :organization_id" in block[:1600]
