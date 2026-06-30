"""
Unit tests for EvidenceCacheService key generation.
"""

import hashlib

from src.services.evidence.cache import EvidenceCacheService


def test_generate_meter_cache_key_is_stable_and_order_independent():
    """Meter cache key should use deterministic hashing over sorted source IDs."""
    cache_service = EvidenceCacheService.__new__(EvidenceCacheService)

    claim_hash = "abc123"
    model_version = "gpt-4o-mini-2024-07-18"
    source_ids_a = ["id3", "id1", "id2"]
    source_ids_b = ["id2", "id3", "id1"]
    org_id = "org-aaa"

    key_a = cache_service._generate_meter_cache_key(
        claim_hash, source_ids_a, model_version, org_id
    )
    key_b = cache_service._generate_meter_cache_key(
        claim_hash, source_ids_b, model_version, org_id
    )

    expected_hash = hashlib.sha256("id1|id2|id3".encode("utf-8")).hexdigest()[:16]

    assert key_a == key_b
    assert expected_hash in key_a


def test_meter_cache_key_isolates_by_organization():
    """Same claim/source/model for two orgs must yield distinct cache keys."""
    cache_service = EvidenceCacheService.__new__(EvidenceCacheService)

    claim_hash = "abc123"
    model_version = "gpt-4o-mini-2024-07-18"
    source_ids = ["id1", "id2", "id3"]

    key_org_a = cache_service._generate_meter_cache_key(
        claim_hash, source_ids, model_version, "org-aaa"
    )
    key_org_b = cache_service._generate_meter_cache_key(
        claim_hash, source_ids, model_version, "org-bbb"
    )

    assert key_org_a != key_org_b
    assert "org-aaa" in key_org_a
    assert "org-bbb" in key_org_b
