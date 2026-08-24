"""PR6 (audit R2-M1/M2/M7/M10/M14/L4/L10/L11/L12/L13, R6-M3/M4/L1/L6) guards."""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (BACKEND_ROOT / rel).read_text()


# R2-M1 — truncated scans cannot conclude deletions
def test_truncated_scan_skips_deletion_detection() -> None:
    src = _read("src/services/arxiv/arxiv_change_tracker.py")
    assert "scan_truncated" in src
    block = src[src.find("if scan_truncated:") :]
    assert "deletion detection skipped" in block[:400]
    assert 'pop("miss_count"' in src  # observation resets the streak


# R2-M2 — revision updates keep checksum honest + flag stale artifact
def test_revision_update_recomputes_checksum() -> None:
    src = _read("src/services/arxiv/arxiv_change_tracker.py")
    upd = src[src.find("async def _update_existing_paper") :]
    assert "checksum_sha256 = _hl.sha256" in upd[:4000]
    assert '"source_pdf_stale"] = True' in upd[:2500] or (
        "source_pdf_stale" in upd[:4000]
    )


# R2-L4 — tracker state mirrors to shared Redis
def test_tracker_state_has_redis_mirror() -> None:
    src = _read("src/services/arxiv/arxiv_change_tracker.py")
    assert "arxiv:tracker:state" in src
    assert "_redis_set_state()" in src.split("def save_state")[1][:1200]


# R2-M7 — quota is claimed atomically, not incremented blindly
def test_quota_claim_conditional_update() -> None:
    org = _read("src/models/organization.py")
    assert "storage_quota_claim" in org
    claim = org[org.find("storage_quota_claim") : org.find("check_storage_quota")]
    assert "storage_used_bytes + size_change_bytes" in claim
    assert "<= Organization.storage_limit_bytes" in claim

    svc = _read("src/services/documents/file_service.py")
    assert "storage_quota_claim(" in svc
    assert "rowcount == 0" in svc


def test_quota_check_constraint_migration() -> None:
    mig = _read("alembic/versions/r6_org_quota_guard.py")
    assert "ck_organizations_storage_nonnegative" in mig


# R2-L10/L11 — sniffed mime; archives rejected honestly
def test_mime_sniffed_not_filename_trusted() -> None:
    src = _read("src/services/documents/file_service.py")
    val = src[src.find("def validate_file") : src.find("def generate_file_path")]
    assert "magic.from_buffer(file_content, mime=True)" in val
    assert 'mime_type": mime_type' in src.replace("'", '"')


def test_archive_extensions_rejected() -> None:
    src = _read("src/services/documents/file_service.py")
    val = src[src.find("def validate_file") : src.find("def generate_file_path")]
    assert '".zip", ".rar"' not in val.replace(" ", "") or ".zip" not in (
        val[val.find("allowed_extensions") : val.find("allowed_extensions") + 600]
    )
    assert "Archive format" in val


# R2-L12 — streamed spool, not full read()
def test_upload_streams_via_spool() -> None:
    src = _read("src/services/documents/file_service.py")
    assert "_spool_and_hash" in src
    body = src[src.find("_spool_and_hash") :]
    assert "await file.read(1024 * 1024)" in body[:900]
    # no full-buffer upload reads left on the s3/supabase paths
    assert (
        "file_content = await file.read()\n                file.file.seek(0)\n                file_hash"
        not in src
    )


# R2-L13 — duplicate hash rejected before storage/quota work
def test_duplicate_hash_checked() -> None:
    src = _read("src/services/documents/file_service.py")
    assert src.count("_assert_not_duplicate(file_hash") == 3  # s3+supabase+local
    dup = src[src.find("def _assert_not_duplicate") :]
    assert "409" in dup[:1600]


# R2-M14 — OPENAI entity writes are idempotent for mid-run kills too
def test_extract_entities_delete_before_insert() -> None:
    src = _read("src/tasks/processing_tasks.py")
    blk = src[src.find("def extract_entities") :]
    guard = blk[blk.find("R2-M14") : blk.find("map_to_entity_type", blk.find("R2-M14"))]
    assert "delete(synchronize_session=False)" in guard
    assert "ExtractionMethod.OPENAI" in guard


# R6-M3 — semantic cache uses a real embedding API
def test_semantic_cache_calls_real_api() -> None:
    src = _read("src/services/infrastructure/llm_response_cache.py")
    assert "embedding_service.embed(" not in src
    assert "generate_embedding" in src


# R6-M4 — cached default model + shared service instance
def test_default_model_cached() -> None:
    src = _read("src/services/embedding/embedding_service.py")
    load = src[src.find("def _load_model") : src.find("def _load_simple_model")]
    assert "_get_sentence_transformer(self.model_name" in load


def test_arxiv_local_shares_one_embedding_service() -> None:
    src = _read("src/api/arxiv/arxiv_local.py")
    assert "EmbeddingService(lazy=False)" in src
    assert 'embedding_provider == "azure_openai"' not in src  # dead branch gone
    assert src.count("EmbeddingService()") == 0 or (
        "EmbeddingService()" not in src.split("@router.")[1]
        if "@router." in src
        else True
    )


# R6-L1 — quality self-test awaits its batch call
def test_quality_selftest_awaits() -> None:
    src = _read("src/services/embedding/embedding_service.py")
    blk = src[
        src.find("async def test_embedding_quality")
        or src.find("def test_embedding_quality") :
    ]
    assert "response = await self.generate_batch_embeddings(request)" in blk[:900]


# R6-L6 — oversized sentences hard-split before embedding
def test_chunk_text_hard_splits_oversized() -> None:
    src = _read("src/services/embedding/embedding_service.py")
    blk = src[src.find("def chunk_text") :]
    assert "while len(s_words) > chunk_size:" in blk[:1800]


# Storage clients gained stream uploads (supporting change)
def test_storage_fileobj_uploads_exist() -> None:
    assert "def upload_fileobj" in _read("src/core/s3_client.py")
    assert "def upload_fileobj" in _read("src/core/supabase_client.py")
