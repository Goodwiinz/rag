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
