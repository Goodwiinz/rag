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
        async def generate_embedding(self, request):
            from src.models.vector import EmbeddingResponse

            return EmbeddingResponse(
                embedding=[1.0, 0.0, 0.0],
                model="test",
                dimension=3,
                processing_time=0.0,
            )

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


def test_semantic_match_requires_compatible_generation_settings():
    """Semantic hits must preserve the response-generation contract."""
    from src.models.vector import EmbeddingResponse
    from src.services.infrastructure.llm_response_cache import (
        LLMCacheConfig,
        LLMResponseCache,
    )

    class _SameEmbeddingService:
        async def generate_embedding(self, request):
            return EmbeddingResponse(
                embedding=[1.0, 0.0, 0.0],
                model="test",
                dimension=3,
                processing_time=0.0,
            )

    async def semantic_hit_for(**get_overrides):
        cache = LLMResponseCache(config=LLMCacheConfig(use_redis=False))
        cache._embedding_service = _SameEmbeddingService()  # type: ignore[assignment]
        await cache.set(
            query="explain retrieval augmented generation",
            response_content="cached answer",
            model="gpt-4o",
            temperature=0.2,
            metadata={"rag_enabled": False},
            organization_id="org-a",
        )
        get_args = {
            "query": "explain retrieval augmented generation?",
            "model": "gpt-4o",
            "temperature": 0.2,
            "use_semantic": True,
            "organization_id": "org-a",
        }
        get_args.update(get_overrides)
        return await cache.get(
            **get_args,
        )

    async def scenario():
        assert await semantic_hit_for(model="gpt-4o-mini") is None
        assert await semantic_hit_for(temperature=0.7) is None

    asyncio.run(scenario())


def test_non_rag_semantic_lookup_rejects_rag_entries():
    """A context-dependent RAG answer must not satisfy a plain semantic lookup."""
    from src.models.vector import EmbeddingResponse
    from src.services.infrastructure.llm_response_cache import (
        LLMCacheConfig,
        LLMResponseCache,
    )

    class _SameEmbeddingService:
        async def generate_embedding(self, request):
            return EmbeddingResponse(
                embedding=[1.0, 0.0, 0.0],
                model="test",
                dimension=3,
                processing_time=0.0,
            )

    async def scenario():
        cache = LLMResponseCache(config=LLMCacheConfig(use_redis=False))
        cache._embedding_service = _SameEmbeddingService()  # type: ignore[assignment]
        await cache.set(
            query="what does this paper conclude",
            response_content="context-dependent answer",
            model="gpt-4o",
            temperature=0.7,
            metadata={"rag_enabled": True},
            organization_id="org-a",
        )
        hit = await cache.get(
            query="what does this paper conclude?",
            model="gpt-4o",
            temperature=0.7,
            use_semantic=True,
            organization_id="org-a",
        )
        assert hit is None

    asyncio.run(scenario())


def test_compute_embedding_uses_generate_embedding():
    """_compute_embedding must call the real EmbeddingService API.

    EmbeddingService has no embed() — only async generate_embedding(
    EmbeddingRequest). Calling a missing method raised AttributeError,
    was swallowed, and permanently disabled the semantic tier.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from src.services.infrastructure.llm_response_cache import (
        LLMCacheConfig,
        LLMResponseCache,
    )

    async def scenario():
        cache = LLMResponseCache(config=LLMCacheConfig(use_redis=False))
        fake_service = MagicMock()
        fake_service.generate_embedding = AsyncMock(
            return_value=MagicMock(embedding=[0.1, 0.2])
        )
        with patch.object(
            cache, "_get_embedding_service", AsyncMock(return_value=fake_service)
        ):
            vec = await cache._compute_embedding("hello")
        assert vec == [0.1, 0.2]
        fake_service.generate_embedding.assert_awaited_once()
        # request arg carries the text
        args = fake_service.generate_embedding.await_args
        assert args.args[0].text == "hello"

    asyncio.run(scenario())
