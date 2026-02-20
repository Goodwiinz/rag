"""Tests deterministic tie-break ordering in hybrid fusion ranking."""

from datetime import datetime, timezone

from src.models.search_schemas import (
    SearchFilter,
    SearchQuery,
    SearchResult,
    SearchType,
)
from src.services.search.hybrid_search_service import (
    HybridSearchService,
    RawSearchResult,
    SearchSourceResult,
    SearchSourceType,
)


def _make_search_result(document_id: str, updated_at: datetime) -> SearchResult:
    return SearchResult(
        document_id=document_id,
        title=f"Title {document_id}",
        document_type="text",
        content_preview="preview",
        snippets=[],
        relevance_score=1.0,
        file_size_bytes=1,
        created_at=updated_at,
        updated_at=updated_at,
        processing_status="completed",
        tags=[],
        is_public=False,
        uploaded_by_user_id="user-1",
        organization_id="org-1",
        metadata={},
    )


def _raw_result(
    document_id: str,
    source_type: SearchSourceType,
    updated_at: datetime,
) -> RawSearchResult:
    return RawSearchResult(
        document_id=document_id,
        source_type=source_type,
        relevance_score=1.0,
        metadata={"source": source_type.value},
        search_result=_make_search_result(document_id, updated_at),
    )


def test_hybrid_ranking_is_stable_for_equal_scores() -> None:
    service = HybridSearchService()

    # Keep fused score equal for all documents so tie-break rules decide final order.
    service._normalize_score = lambda score, source_type: 1.0  # type: ignore[assignment]
    service._calculate_recency_boost = lambda search_result: 0.0  # type: ignore[assignment]

    t_new = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
    t_old = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    source_results = {
        # Insert vector first to prove sort is not relying on insertion order.
        SearchSourceType.VECTOR: SearchSourceResult(
            source_type=SearchSourceType.VECTOR,
            results=[
                _raw_result("vec-a", SearchSourceType.VECTOR, t_old),
                _raw_result("doc-b", SearchSourceType.VECTOR, t_new),
                _raw_result("doc-a", SearchSourceType.VECTOR, t_new),
            ],
            search_time_ms=1.0,
            total_available=3,
            success=True,
        ),
        SearchSourceType.FULLTEXT: SearchSourceResult(
            source_type=SearchSourceType.FULLTEXT,
            results=[_raw_result("ft-a", SearchSourceType.FULLTEXT, t_old)],
            search_time_ms=1.0,
            total_available=1,
            success=True,
        ),
    }

    request = SearchQuery(
        query="deterministic ranking",
        search_type=SearchType.HYBRID,
        limit=10,
        offset=0,
    )

    fused_results = service._fuse_search_results(source_results, request)

    assert [result.document_id for result in fused_results] == [
        "ft-a",  # higher source quality tier
        "doc-a",  # same tier + timestamp as doc-b -> lexicographic fallback
        "doc-b",
        "vec-a",  # same tier, older timestamp
    ]


def test_final_filtering_respects_selected_document_ids() -> None:
    service = HybridSearchService()
    now = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)

    r1 = _raw_result("doc-allow-1", SearchSourceType.FULLTEXT, now)
    r2 = _raw_result("doc-blocked", SearchSourceType.VECTOR, now)

    request = SearchQuery(
        query="deterministic filters",
        search_type=SearchType.HYBRID,
        limit=10,
        offset=0,
        filters=SearchFilter(document_ids=["doc-allow-1"]),
    )

    filtered = service._apply_final_filtering([r1, r2], request, "org-1")

    assert [result.document_id for result in filtered] == ["doc-allow-1"]
