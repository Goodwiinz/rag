"""R2-H9 + R2-H10: hybrid score normalization and cross-source fusion identity.

H9: HybridSearchService._normalize_score() assumed fulltext relevance_score
topped out at 50 (it's actually ts_rank_cd()*10, naturally ~0-1), crushing
fused scores to ~0.001-0.02 and starving the confidence gate.

H10: KG results were fused on the Neo4j entity uuid instead of the entity's
source Document uuid, so a KG hit could never merge with a fulltext hit on
the same document -> source_count always 1 -> coverage always 0.0 ->
INSUFFICIENT_EVIDENCE on every populated hybrid response.

These are coupled: the confidence gate runs before the coverage gate, so
fixing H9 alone flips NO_MATCH -> INSUFFICIENT_EVIDENCE.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from src.models.search_schemas import (
    DocumentType,
    SearchQuery,
    SearchResult,
    SearchSortOrder,
    SearchType,
)
from src.services.search.hybrid_search_service import (
    HybridSearchService,
    RawSearchResult,
    SearchSourceResult,
    SearchSourceType,
)


def _search_query(query: str) -> SearchQuery:
    return SearchQuery(
        query=query,
        search_type=SearchType.HYBRID,
        limit=10,
        offset=0,
        sort_order=SearchSortOrder.RELEVANCE,
        filters=None,
    )


def _search_result(document_id: str, relevance_score: float) -> SearchResult:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    return SearchResult(
        document_id=document_id,
        title=f"Title {document_id}",
        document_type=DocumentType.TEXT,
        content_preview="preview",
        snippets=[],
        relevance_score=relevance_score,
        file_size_bytes=1,
        created_at=now,
        updated_at=now,
        processing_status="completed",
        tags=[],
        is_public=False,
        uploaded_by_user_id="user-1",
        organization_id="org-1",
        metadata={},
    )


# ---------------------------------------------------------------------------
# H9: _normalize_score scale
# ---------------------------------------------------------------------------


def test_normalize_score_fulltext_undoes_sql_x10_and_clamps() -> None:
    svc = HybridSearchService()

    # fulltext_search_service returns ts_rank_cd(...) * 10; a strong match in
    # the "typical 0.5-1.0" range should normalize to a meaningful fraction,
    # not the old ~0.001-0.02 (score/50.0).
    normalized = svc._normalize_score(0.8, SearchSourceType.FULLTEXT)
    assert normalized == 0.08
    assert normalized > 0.8 / 50.0  # meaningfully bigger than the old bug

    # Clamps outlier raw scores instead of exceeding 1.0.
    assert svc._normalize_score(25.0, SearchSourceType.FULLTEXT) == 1.0


def test_normalize_score_knowledge_graph_is_already_0_to_1() -> None:
    svc = HybridSearchService()

    # KG entity confidence is already a 0-1 score — must NOT be re-divided
    # by 10 (that was the old "assumes max score of 10" bug).
    assert svc._normalize_score(0.8, SearchSourceType.KNOWLEDGE_GRAPH) == 0.8
    assert svc._normalize_score(1.5, SearchSourceType.KNOWLEDGE_GRAPH) == 1.0


# ---------------------------------------------------------------------------
# H10: KG results fuse on the entity's source_document_id, not the entity id
# ---------------------------------------------------------------------------


def test_kg_search_maps_to_source_document_id_not_entity_id() -> None:
    svc = HybridSearchService()

    entity_with_doc = SimpleNamespace(
        id="entity-uuid-1",
        name="Marie Curie",
        confidence_score=0.9,
        context="discovered radium",
        source_document_id="doc-abc",
    )
    entity_without_doc = SimpleNamespace(
        id="entity-uuid-2",
        name="Orphan Entity",
        confidence_score=0.9,
        context="",
        source_document_id=None,
    )

    with patch(
        "src.services.knowledge_graph.knowledge_graph_service.knowledge_graph_service"
        ".search_entities",
        return_value=[entity_with_doc, entity_without_doc],
    ):
        result = svc._execute_knowledge_graph_search(
            _search_query("who discovered radium"),
            user_id="user-1",
            organization_id="org-1",
        )

    assert result.success
    # Only the entity with a real source document becomes evidence; the
    # entity-only id is never fabricated into a document_id.
    assert [r.document_id for r in result.results] == ["doc-abc"]
    assert all(r.document_id != "entity-uuid-1" for r in result.results)
    assert all(r.document_id != "entity-uuid-2" for r in result.results)


def test_kg_search_preserves_explicit_zero_confidence() -> None:
    """`confidence_score or 0.8` would promote an explicit 0.0 to 0.8 —
    only a missing (None) confidence should default."""
    svc = HybridSearchService()

    zero_confidence_entity = SimpleNamespace(
        id="entity-uuid-3",
        name="Low Confidence Entity",
        confidence_score=0.0,
        context="",
        source_document_id="doc-zero-conf",
    )

    with patch(
        "src.services.knowledge_graph.knowledge_graph_service.knowledge_graph_service"
        ".search_entities",
        return_value=[zero_confidence_entity],
    ):
        result = svc._execute_knowledge_graph_search(
            _search_query("who is this"),
            user_id="user-1",
            organization_id="org-1",
        )

    assert result.results[0].relevance_score == 0.0


def test_kg_only_hit_is_dropped_not_returned_as_a_standalone_result() -> None:
    """P1 follow-up: Entity.source_document_id is set only ON CREATE and never
    updated on MATCH (entities are MERGEd across documents), so it can point
    at a stale or deleted document. That's tolerable as a corroboration boost
    for a document another source already verified, but not as the sole
    source of a returned result — a KG-only document_id must never surface on
    its own.
    """
    svc = HybridSearchService()

    source_results = {
        SearchSourceType.KNOWLEDGE_GRAPH: SearchSourceResult(
            source_type=SearchSourceType.KNOWLEDGE_GRAPH,
            results=[
                RawSearchResult(
                    document_id="doc-only-in-kg",
                    source_type=SearchSourceType.KNOWLEDGE_GRAPH,
                    relevance_score=0.9,
                    metadata={"source": "knowledge_graph"},
                    search_result=_search_result("doc-only-in-kg", 0.9),
                )
            ],
            search_time_ms=1.0,
            total_available=1,
            success=True,
        ),
    }

    request = _search_query("who discovered radium")
    fused = svc._fuse_search_results(source_results, request)

    assert fused == []


# ---------------------------------------------------------------------------
# Coupled: fusion + coverage/confidence behave sanely with mixed sources
# ---------------------------------------------------------------------------


def test_fusion_merges_kg_and_fulltext_hits_on_same_document() -> None:
    svc = HybridSearchService()

    source_results = {
        SearchSourceType.FULLTEXT: SearchSourceResult(
            source_type=SearchSourceType.FULLTEXT,
            results=[
                RawSearchResult(
                    document_id="doc-abc",
                    source_type=SearchSourceType.FULLTEXT,
                    relevance_score=0.8,  # post SQL x10, "typical" strong match
                    metadata={"source": "fulltext"},
                    search_result=_search_result("doc-abc", 0.8),
                )
            ],
            search_time_ms=1.0,
            total_available=1,
            success=True,
        ),
        SearchSourceType.KNOWLEDGE_GRAPH: SearchSourceResult(
            source_type=SearchSourceType.KNOWLEDGE_GRAPH,
            results=[
                RawSearchResult(
                    document_id="doc-abc",  # same document, mapped via H10 fix
                    source_type=SearchSourceType.KNOWLEDGE_GRAPH,
                    relevance_score=0.9,
                    metadata={"source": "knowledge_graph"},
                    search_result=_search_result("doc-abc", 0.9),
                )
            ],
            search_time_ms=1.0,
            total_available=1,
            success=True,
        ),
    }

    request = _search_query("who discovered radium")
    fused = svc._fuse_search_results(source_results, request)

    assert len(fused) == 1
    doc = fused[0]
    assert doc.document_id == "doc-abc"
    assert doc.metadata["source_count"] == 2
    assert set(doc.metadata["original_sources"]) == {"fulltext", "knowledge_graph"}
    # Diversity boost only fires because both sources landed on the same doc.
    assert doc.metadata["boost_factors"].get("diversity", 0.0) > 0.0


def test_confidence_and_coverage_gate_pass_for_multi_source_batch() -> None:
    svc = HybridSearchService()

    results = [
        _search_result("doc-abc", 0.6),
    ]
    results[0].metadata = {
        "source_count": 2,
        "original_sources": ["fulltext", "knowledge_graph"],
    }

    confidence = svc._calculate_deterministic_confidence(results)
    coverage = svc._calculate_deterministic_coverage(results)

    assert confidence >= 0.2  # clears the NO_MATCH confidence gate
    assert coverage >= 0.5  # clears the INSUFFICIENT_EVIDENCE coverage gate


def test_coverage_does_not_hard_fail_on_fulltext_only_results() -> None:
    """KG only activates for entity-indicator queries, so most hybrid
    results are legitimately fulltext-only. That must not zero out coverage
    (the H10 bug) — a fulltext-backed result IS evidence on its own.
    """
    svc = HybridSearchService()

    results = [_search_result("doc-1", 0.5), _search_result("doc-2", 0.5)]
    for r in results:
        r.metadata = {"source_count": 1, "original_sources": ["fulltext"]}

    coverage = svc._calculate_deterministic_coverage(results)
    assert coverage == 1.0


def test_coverage_zero_for_kg_only_results_with_no_fulltext_backing() -> None:
    """A pure KG (entity metadata, no document text) result correctly reads
    as low coverage — it's enrichment, not evidence, even after H10 wires up
    correct document ids.
    """
    svc = HybridSearchService()

    results = [_search_result("doc-1", 0.5)]
    results[0].metadata = {"source_count": 1, "original_sources": ["knowledge_graph"]}

    coverage = svc._calculate_deterministic_coverage(results)
    assert coverage == 0.0
