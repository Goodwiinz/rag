"""Tests for LLM response cache organization scoping."""

import asyncio


def test_cache_key_differs_per_organization():
    from src.services.infrastructure.llm_response_cache import LLMResponseCache

    cache = LLMResponseCache()
    h_org_a = cache._generate_query_hash(
        "hello", "gpt-4o", 0.7, organization_id="org-a"
    )
    h_org_b = cache._generate_query_hash(
        "hello", "gpt-4o", 0.7, organization_id="org-b"
    )
    h_no_org = cache._generate_query_hash("hello", "gpt-4o", 0.7)
    assert h_org_a != h_org_b
    assert h_org_a != h_no_org


def test_get_does_not_return_entry_set_by_other_organization():
    from src.services.infrastructure.llm_response_cache import LLMResponseCache

    async def scenario():
        cache = LLMResponseCache()
        await cache.set(
            query="what is rag",
            response_content="org a answer",
            model="gpt-4o",
            temperature=0.7,
            organization_id="org-a",
        )
        hit = await cache.get(
            query="what is rag",
            model="gpt-4o",
            temperature=0.7,
            use_semantic=False,
            organization_id="org-b",
        )
        assert hit is None
        own = await cache.get(
            query="what is rag",
            model="gpt-4o",
            temperature=0.7,
            use_semantic=False,
            organization_id="org-a",
        )
        assert own is not None and own["content"] == "org a answer"

    asyncio.run(scenario())


def test_semantic_match_is_organization_scoped():
    """Org-B semantic get must never return an entry set by org-A.

    Both queries resolve to the SAME embedding vector so similarity is
    maximal — isolation must come purely from the index structure.
    """
    from src.services.infrastructure.llm_response_cache import (
        LLMCacheConfig,
        LLMResponseCache,
    )

    class _SameEmbeddingService:
        def embed(self, text):
            return [1.0, 0.0, 0.0]

    async def scenario():
        cache = LLMResponseCache(config=LLMCacheConfig(use_redis=False))
        cache._embedding_service = _SameEmbeddingService()  # type: ignore[assignment]
        await cache.set(
            query="what is retrieval augmented generation",
            response_content="org a answer",
            model="gpt-4o",
            temperature=0.7,
            organization_id="org-a",
        )
        # Near-identical text (different hash → skips exact tier, forces semantic)
        cross_tenant = await cache.get(
            query="what is retrieval augmented generation?",
            model="gpt-4o",
            temperature=0.7,
            use_semantic=True,
            organization_id="org-b",
        )
        assert cross_tenant is None

        own_org = await cache.get(
            query="what is retrieval augmented generation?",
            model="gpt-4o",
            temperature=0.7,
            use_semantic=True,
            organization_id="org-a",
        )
        assert own_org is not None
        assert own_org["cache_type"] == "semantic"
        assert own_org["content"] == "org a answer"

    asyncio.run(scenario())
