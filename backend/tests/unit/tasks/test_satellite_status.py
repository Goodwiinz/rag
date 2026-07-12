"""Per-satellite fan-out truth on the ingestion task (audit D1 / P2.1).

The ingestion pipeline fans a document out to Neo4j and DO KB best-effort:
satellite failures are non-fatal and the document still reaches COMPLETED.
Before this fix the outcome was a warn-log only — a Neo4j-failed document was
indistinguishable from a healthy one. Contract under test:

- Neo4j fan-out raising  -> ``neo4j_index_status='failed'``, document still
  COMPLETED (best-effort model preserved), job COMPLETED.
- every entity indexed   -> ``neo4j_index_status='completed'`` +
  ``neo4j_indexed_at`` stamped.
- partial fan-out (``create_entity_node`` returns None for some entities —
  it swallows per-entity failures and never raises) -> ``failed``.
- DO KB enabled + sync returns no uuid -> ``do_kb_sync_status='failed'``.
- DO KB enabled + sync returns a uuid  -> ``do_kb_sync_status='completed'``.
- DO KB disabled -> ``do_kb_sync_status`` stays NULL (never attempted).

Uses the same in-memory SQLite harness as test_replay_idempotency.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit

from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.entity import Entity, EntityType, ExtractionMethod
from src.models.processing import JobStatus, JobType, ProcessingJob
from src.shared.enums import SatelliteSyncStatus
from src.tasks import processing_tasks as pt


@pytest.fixture
def session_factory():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import src.models  # noqa: F401  register every table on Base.metadata
    from src.models.base import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield Session
    finally:
        engine.dispose()


def _seed(session_factory, *, content_text="Ada and Charles."):
    org_id, doc_id, job_id = uuid4(), uuid4(), uuid4()
    db = session_factory()
    db.add(
        Document(
            id=doc_id,
            title="Doc",
            filename="doc.txt",
            file_path="local:///tmp/doc.txt",
            file_size_bytes=10,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=org_id,
            content_text=content_text,
            processing_status=ProcessingStatus.PENDING,
        )
    )
    db.add(
        ProcessingJob(
            id=job_id,
            job_type=JobType.DOCUMENT_INGESTION,
            status=JobStatus.QUEUED,
            organization_id=org_id,
            document_id=doc_id,
            parameters={"document_id": str(doc_id)},
            total_steps=5,
        )
    )
    db.commit()
    db.close()
    return org_id, doc_id, job_id


def _entity(name, doc_id, org_id):
    return Entity(
        entity_type=EntityType.PERSON,
        name=name,
        extraction_method=ExtractionMethod.SPACY,
        extracted_at=datetime.now(timezone.utc),
        confidence=0.9,
        document_id=doc_id,
        organization_id=org_id,
    )


class _FakePipeline:
    def __init__(self, db):
        self.db = db

    async def process_text_extraction(self, document):
        return {
            "text_content": document.content_text,
            "summary": "s",
            "word_count": 5,
            "character_count": 40,
        }

    async def process_entity_extraction(self, document, text):
        return [
            _entity("Ada Lovelace", document.id, document.organization_id),
            _entity("Charles Babbage", document.id, document.organization_id),
        ]


def _stub(monkeypatch, Session, *, kb_uuid=None, do_kb_enabled=False):
    monkeypatch.setattr(pt, "SessionLocal", Session)
    monkeypatch.setattr(pt, "ProcessingPipeline", _FakePipeline)
    monkeypatch.setattr(
        pt, "_sync_document_to_kb_blocking", lambda document, **kw: kb_uuid
    )
    monkeypatch.setattr(
        pt.fulltext_search_service,
        "update_document_search_vector",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(pt.settings, "DO_KB_ENABLED", do_kb_enabled)


def _fetch_doc(session_factory, doc_id):
    db = session_factory()
    try:
        return db.query(Document).filter(Document.id == doc_id).first()
    finally:
        db.close()


def test_neo4j_exception_marks_failed_but_document_completes(
    session_factory, monkeypatch
):
    """A raising Neo4j client records failed truth without failing ingestion."""
    org_id, doc_id, job_id = _seed(session_factory)
    _stub(monkeypatch, session_factory)

    def _boom(**kwargs):
        raise ConnectionError("neo4j down")

    monkeypatch.setattr(pt.knowledge_graph_service, "create_entity_node", _boom)

    result = pt.process_document_ingestion.apply(args=(str(job_id),)).get()
    assert result["status"] == "completed"

    doc = _fetch_doc(session_factory, doc_id)
    assert doc.neo4j_index_status == SatelliteSyncStatus.FAILED.value
    assert doc.neo4j_indexed_at is None
    # Best-effort model preserved: the document still reached COMPLETED.
    assert doc.processing_status == ProcessingStatus.COMPLETED


def test_neo4j_full_fanout_marks_completed_with_timestamp(
    session_factory, monkeypatch
):
    org_id, doc_id, job_id = _seed(session_factory)
    _stub(monkeypatch, session_factory)
    monkeypatch.setattr(
        pt.knowledge_graph_service,
        "create_entity_node",
        lambda **kwargs: f"node-{kwargs['entity_text']}",
    )

    result = pt.process_document_ingestion.apply(args=(str(job_id),)).get()
    assert result["status"] == "completed"

    doc = _fetch_doc(session_factory, doc_id)
    assert doc.neo4j_index_status == SatelliteSyncStatus.COMPLETED.value
    assert doc.neo4j_indexed_at is not None


def test_neo4j_partial_fanout_marks_failed(session_factory, monkeypatch):
    """create_entity_node returns None per-entity on failure (it never raises
    on an outage) — a partial fan-out is a failure, not a warn-logged success."""
    org_id, doc_id, job_id = _seed(session_factory)
    _stub(monkeypatch, session_factory)
    calls = {"n": 0}

    def _every_other(**kwargs):
        calls["n"] += 1
        return "node-1" if calls["n"] == 1 else None

    monkeypatch.setattr(pt.knowledge_graph_service, "create_entity_node", _every_other)

    pt.process_document_ingestion.apply(args=(str(job_id),)).get()

    doc = _fetch_doc(session_factory, doc_id)
    assert doc.neo4j_index_status == SatelliteSyncStatus.FAILED.value
    assert doc.neo4j_indexed_at is None


def test_do_kb_enabled_sync_failure_marks_failed(session_factory, monkeypatch):
    org_id, doc_id, job_id = _seed(session_factory)
    _stub(monkeypatch, session_factory, kb_uuid=None, do_kb_enabled=True)
    monkeypatch.setattr(
        pt.knowledge_graph_service, "create_entity_node", lambda **kw: "n"
    )

    result = pt.process_document_ingestion.apply(args=(str(job_id),)).get()
    assert result["status"] == "completed"

    doc = _fetch_doc(session_factory, doc_id)
    assert doc.do_kb_sync_status == SatelliteSyncStatus.FAILED.value
    assert doc.is_embedded is False
    # Best-effort preserved.
    assert doc.processing_status == ProcessingStatus.COMPLETED


def test_do_kb_enabled_sync_success_marks_completed(session_factory, monkeypatch):
    org_id, doc_id, job_id = _seed(session_factory)
    _stub(monkeypatch, session_factory, kb_uuid="ds-123", do_kb_enabled=True)
    monkeypatch.setattr(
        pt.knowledge_graph_service, "create_entity_node", lambda **kw: "n"
    )

    pt.process_document_ingestion.apply(args=(str(job_id),)).get()

    doc = _fetch_doc(session_factory, doc_id)
    assert doc.do_kb_sync_status == SatelliteSyncStatus.COMPLETED.value
    assert doc.is_embedded is True


def test_do_kb_disabled_leaves_status_null(session_factory, monkeypatch):
    """Disabled DO KB is not an attempt — NULL (never attempted), not failed."""
    org_id, doc_id, job_id = _seed(session_factory)
    _stub(monkeypatch, session_factory, kb_uuid=None, do_kb_enabled=False)
    monkeypatch.setattr(
        pt.knowledge_graph_service, "create_entity_node", lambda **kw: "n"
    )

    pt.process_document_ingestion.apply(args=(str(job_id),)).get()

    doc = _fetch_doc(session_factory, doc_id)
    assert doc.do_kb_sync_status is None


def test_no_content_leaves_both_satellites_null(session_factory, monkeypatch):
    """No text -> no fan-out attempts -> honest NULL on both satellites."""
    org_id, doc_id, job_id = _seed(session_factory, content_text=None)
    _stub(monkeypatch, session_factory, do_kb_enabled=True)

    pt.process_document_ingestion.apply(args=(str(job_id),)).get()

    doc = _fetch_doc(session_factory, doc_id)
    assert doc.neo4j_index_status is None
    assert doc.do_kb_sync_status is None


def test_generate_embeddings_records_outcome(session_factory, monkeypatch):
    """The standalone embeddings task records the same DO KB truth."""
    org_id, doc_id, job_id = _seed(session_factory)
    monkeypatch.setattr(pt, "SessionLocal", session_factory)
    monkeypatch.setattr(pt.settings, "DO_KB_ENABLED", True)
    monkeypatch.setattr(
        pt, "_sync_document_to_kb_blocking", lambda document, **kw: None
    )

    result = pt.generate_embeddings.apply(args=(str(job_id),)).get()
    assert result["status"] == "skipped"

    doc = _fetch_doc(session_factory, doc_id)
    assert doc.do_kb_sync_status == SatelliteSyncStatus.FAILED.value
