import hashlib
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from src.models.document import ProcessingStatus
from src.services.evidence import source_loader


def _document(
    source_id: UUID,
    *,
    organization_id: UUID,
    title: str = "Source",
    content_text: str | None = "supported claim in this source",
    processing_status: ProcessingStatus = ProcessingStatus.COMPLETED,
    checksum_sha256: str | None = None,
    is_deleted: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=source_id,
        organization_id=organization_id,
        title=title,
        content_text=content_text,
        processing_status=processing_status,
        checksum_sha256=checksum_sha256,
        is_deleted=is_deleted,
    )


def _db_with_documents(*documents: SimpleNamespace) -> Mock:
    db = Mock(spec=Session)
    query = db.query.return_value
    query.filter.return_value = query
    query.all.return_value = list(documents)
    return db


def test_excerpt_is_a_contiguous_bounded_source_substring() -> None:
    content = "A" * 13_000 + " target evidence phrase " + "B" * 13_000

    excerpt = source_loader.ClaimExcerptSelector().select("target evidence", content)

    assert excerpt in content
    assert len(excerpt) <= 12_000
    assert "target evidence phrase" in excerpt


def test_excerpt_falls_back_to_source_prefix_without_overlap() -> None:
    content = "unrelated source text " * 1_000

    excerpt = source_loader.ClaimExcerptSelector().select("quantum gravity", content)

    assert excerpt == content[:12_000]


def test_excerpt_scores_casefolded_claim_terms_and_prefers_earliest_window() -> None:
    content = "ALPHA " + "x" * 5_995 + "alpha " + "beta " + "y" * 12_000

    excerpt = source_loader.ClaimExcerptSelector().select("Alpha beta", content)

    assert excerpt == content[:12_000]


def test_source_types_expose_classifier_payload_and_revisions() -> None:
    source_id = uuid4()
    source = source_loader.EvidenceSource(
        source_id=source_id,
        title="Source",
        excerpt="A relevant excerpt",
        content_hash="hash",
    )
    loaded = source_loader.EvidenceSourceSet(
        sources=(source,), withdrawn_source_ids=(str(uuid4()),)
    )

    assert source.classifier_input() == {
        "source_id": source_id,
        "excerpt": "A relevant excerpt",
        "content_hash": "hash",
    }
    assert source.revision == f"{source_id}:hash"
    assert loaded.revisions == [
        f"{source_id}:hash",
        f"{loaded.withdrawn_source_ids[0]}:withdrawn",
    ]


def test_loader_scopes_query_and_preserves_requested_order() -> None:
    organization_id = uuid4()
    first = _document(uuid4(), organization_id=organization_id, title="First")
    second = _document(uuid4(), organization_id=organization_id, title="Second")
    db = _db_with_documents(first, second)

    loaded = source_loader.EvidenceSourceLoader().load(
        db,
        organization_id=organization_id,
        source_ids=[second.id, first.id],
        claim="supported claim",
    )

    assert [source.source_id for source in loaded.sources] == [second.id, first.id]
    filters = db.query.return_value.filter.call_args.args
    assert any(argument.left.key == "organization_id" for argument in filters)
    assert all(argument.left.key != "is_deleted" for argument in filters)


def test_loader_rejects_duplicate_ids_before_query() -> None:
    organization_id = uuid4()
    source_id = uuid4()
    db = Mock(spec=Session)

    with pytest.raises(source_loader.DuplicateSourceIdsError):
        source_loader.EvidenceSourceLoader().load(
            db,
            organization_id=organization_id,
            source_ids=[source_id, source_id],
            claim="claim",
        )

    db.query.assert_not_called()


def test_loader_fails_closed_without_org() -> None:
    db = Mock(spec=Session)

    with pytest.raises(source_loader.SourceSetNotFoundError):
        source_loader.EvidenceSourceLoader().load(
            db, organization_id=None, source_ids=[uuid4()], claim="claim"
        )

    db.query.assert_not_called()


def test_loader_rejects_missing_or_cross_tenant_rows_without_identifying_id() -> None:
    organization_id = uuid4()
    requested = [uuid4(), uuid4()]
    db = _db_with_documents(_document(requested[0], organization_id=organization_id))

    with pytest.raises(source_loader.SourceSetNotFoundError) as error:
        source_loader.EvidenceSourceLoader().load(
            db,
            organization_id=organization_id,
            source_ids=requested,
            claim="claim",
        )

    assert str(requested[1]) not in str(error.value)


def test_loader_rejects_a_returned_cross_tenant_row() -> None:
    organization_id = uuid4()
    foreign_organization_id = uuid4()
    source_id = uuid4()
    db = _db_with_documents(
        _document(source_id, organization_id=foreign_organization_id)
    )

    with pytest.raises(source_loader.SourceSetNotFoundError) as error:
        source_loader.EvidenceSourceLoader().load(
            db,
            organization_id=organization_id,
            source_ids=[source_id],
            claim="claim",
        )

    assert str(source_id) not in str(error.value)


def test_loader_counts_soft_deleted_sources_but_never_classifies_them() -> None:
    organization_id = uuid4()
    active = _document(uuid4(), organization_id=organization_id, title="Active")
    deleted = _document(
        uuid4(), organization_id=organization_id, title="Deleted", is_deleted=True
    )
    db = _db_with_documents(active, deleted)

    loaded = source_loader.EvidenceSourceLoader().load(
        db,
        organization_id=organization_id,
        source_ids=[active.id, deleted.id],
        claim="claim",
    )

    assert [source.source_id for source in loaded.sources] == [active.id]
    assert loaded.withdrawn_source_ids == (str(deleted.id),)


@pytest.mark.parametrize(
    ("processing_status", "content_text"),
    [
        (ProcessingStatus.PROCESSING, "claim text"),
        (ProcessingStatus.COMPLETED, "   \n\t"),
        (ProcessingStatus.COMPLETED, None),
    ],
)
def test_loader_rejects_incomplete_or_blank_content_before_payloads(
    processing_status: ProcessingStatus, content_text: str | None
) -> None:
    organization_id = uuid4()
    source_id = uuid4()
    db = _db_with_documents(
        _document(
            source_id,
            organization_id=organization_id,
            processing_status=processing_status,
            content_text=content_text,
        )
    )

    with pytest.raises(source_loader.SourceNotReadyError):
        source_loader.EvidenceSourceLoader().load(
            db,
            organization_id=organization_id,
            source_ids=[source_id],
            claim="claim",
        )


def test_loader_hashes_current_content_even_when_uploaded_checksum_is_stale() -> None:
    organization_id = uuid4()
    stored_hash = _document(
        uuid4(),
        organization_id=organization_id,
        content_text="stored checksum content",
        checksum_sha256="stored-hash",
    )
    computed_hash = _document(
        uuid4(),
        organization_id=organization_id,
        content_text="computed checksum content",
        checksum_sha256="  ",
    )
    db = _db_with_documents(stored_hash, computed_hash)

    loaded = source_loader.EvidenceSourceLoader().load(
        db,
        organization_id=organization_id,
        source_ids=[stored_hash.id, computed_hash.id],
        claim="checksum content",
    )

    assert (
        loaded.sources[0].content_hash
        == hashlib.sha256(stored_hash.content_text.encode("utf-8")).hexdigest()
    )
    assert loaded.sources[1].content_hash == (
        "f0a3ddf786e1fe1ac9060c678917fb5d83d5d0008669310cb3ed1d1a1e8f9bdd"
    )


def test_current_content_hash_hashes_utf8_content_and_fails_closed() -> None:
    content = "révision café"
    assert (
        source_loader.current_content_hash(content)
        == hashlib.sha256(content.encode("utf-8")).hexdigest()
    )
    assert source_loader.current_content_hash(None) is None
    assert source_loader.current_content_hash("") is None
    assert source_loader.current_content_hash("  \n\t") is None


def test_loader_revision_changes_when_extracted_content_changes_without_checksum_update() -> (
    None
):
    organization_id = uuid4()
    original = "original extracted text"
    document = _document(
        uuid4(),
        organization_id=organization_id,
        content_text=original,
        checksum_sha256="uploaded-file-checksum",
    )
    db = _db_with_documents(document)

    first = source_loader.EvidenceSourceLoader().load(
        db,
        organization_id=organization_id,
        source_ids=[document.id],
        claim="extracted text",
    )

    document.content_text = "revised extracted text"
    second = source_loader.EvidenceSourceLoader().load(
        db,
        organization_id=organization_id,
        source_ids=[document.id],
        claim="extracted text",
    )

    assert first.revisions != second.revisions
    assert (
        second.sources[0].content_hash
        == hashlib.sha256(document.content_text.encode("utf-8")).hexdigest()
    )


def test_loader_rejects_all_withdrawn_sources() -> None:
    organization_id = uuid4()
    deleted = _document(uuid4(), organization_id=organization_id, is_deleted=True)
    db = _db_with_documents(deleted)

    with pytest.raises(source_loader.NoActiveSourcesError):
        source_loader.EvidenceSourceLoader().load(
            db,
            organization_id=organization_id,
            source_ids=[deleted.id],
            claim="claim",
        )
