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

    key_a = cache_service._generate_meter_cache_key(claim_hash, source_ids_a, model_version)
    key_b = cache_service._generate_meter_cache_key(claim_hash, source_ids_b, model_version)

    expected_hash = hashlib.sha256("id1|id2|id3".encode("utf-8")).hexdigest()[:16]

    assert key_a == key_b
    assert expected_hash in key_a
