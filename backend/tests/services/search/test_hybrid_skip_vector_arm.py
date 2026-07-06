"""FIX D1: skip the dead vector arm when Qdrant is unconfigured.

When ``settings.QDRANT_URL`` is falsy the vector search path can only fail —
but not before wasting a local sentence-transformers embedding per query
(CPU + OOM risk). ``_route_search_query`` must not include the VECTOR source in
that case, so fulltext (+KG) still run.

These are pure routing tests: no embedding, no Qdrant, no DB.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.services.search.hybrid_search_service import (
    HybridSearchService,
    SearchSourceType,
)


def _hybrid_query():
    q = MagicMock()
    q.query = "machine learning algorithms"
    # Real enum value compared inside _route_search_query.
    from src.models.search_schemas import SearchType

    q.search_type = SearchType.HYBRID
    return q


@pytest.mark.unit
def test_vector_arm_skipped_when_qdrant_url_unset():
    service = HybridSearchService()
    with patch("src.core.config.settings", MagicMock(QDRANT_URL=None)):
        sources = service._route_search_query(_hybrid_query())

    assert SearchSourceType.VECTOR not in sources
    # Fulltext still runs — hybrid search is not neutered.
    assert SearchSourceType.FULLTEXT in sources


@pytest.mark.unit
def test_vector_arm_included_when_qdrant_url_set():
    service = HybridSearchService()
    with patch(
        "src.core.config.settings",
        MagicMock(QDRANT_URL="http://qdrant:6333"),
    ):
        sources = service._route_search_query(_hybrid_query())

    assert SearchSourceType.VECTOR in sources
    assert SearchSourceType.FULLTEXT in sources
