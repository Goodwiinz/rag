"""
Celery tasks for document processing
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict

from celery import Task, current_app

from src.core.config import settings
from src.core.database import SessionLocal, get_db
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.entity import Entity, ExtractionMethod
from src.models.graph import (
    BatchEntityRequest,
    CreateEntityRequest,
    CreateRelationshipRequest,
)
from src.models.graph import EntityType as GraphEntityType
from src.models.graph import ExtractionMethod as GraphExtractionMethod
from src.models.graph import RelationshipType as GraphRelationshipType
from src.models.processing import JobStatus, ProcessingJob
from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service
from src.services.processing.llm_entity_extraction import LLMEntityExtractionService
from src.services.processing.processing_service import ProcessingPipeline
from src.services.search.fulltext_search_service import fulltext_search_service
from src.tasks.celery_app import celery_app
from src.tasks.replay_guard import claim_job_for_processing

logger = logging.getLogger(__name__)

# Extraction methods produced by the synchronous ingestion pipeline
# (ProcessingPipeline -> EntityExtractionService: spaCy NER + regex). Curated
# (MANUAL) and LLM (OPENAI) entities use other methods and must never be
# clobbered when this pipeline replays; scope the delete-before-insert to these.
_PIPELINE_EXTRACTION_METHODS = (ExtractionMethod.SPACY, ExtractionMethod.REGEX)


def _reset_pipeline_entities(db, document_id) -> int:
    """Delete this pipeline's own auto-extracted entities for a document.

    Makes the entity-extraction stage idempotent under acks_late redelivery: a
    crash mid-run can leave a partial spaCy/regex entity set from the previous
    attempt, so we drop those rows before re-inserting the fresh set
    (delete-before-insert, the same pattern the figure stage uses). Only rows
    written by this pipeline (SPACY/REGEX) are removed; MANUAL/OPENAI entities
    are preserved. Returns the number of rows deleted.
    """
    return (
        db.query(Entity)
        .filter(
            Entity.document_id == document_id,
            Entity.extraction_method.in_(_PIPELINE_EXTRACTION_METHODS),
        )
        .delete(synchronize_session=False)
    )


def _sync_document_to_kb_blocking(document) -> str | None:
    """Push a document to DO KB from a synchronous Celery task.

    DO KB (DigitalOcean Knowledge Base) is the retrieval backend after Qdrant
    was dropped. ``sync_document_to_kb`` is async and needs an async session,
    while these tasks hold a sync ``SessionLocal`` — bridge the sync-loaded ORM
    object into a fresh ``AsyncSessionLocal`` via ``merge()`` (synchronous in
    SQLAlchemy 2.0 — do NOT await), mirroring ``api/agent/tools_impl.py``.

    Returns the data-source uuid, or ``None`` when DO KB is disabled or the
    sync fails. Never raises — ingestion must not fail on a KB outage.
    """

    async def _run() -> str | None:
        from src.core.database import AsyncSessionLocal
        from src.services.do_kb import sync_document_to_kb

        async with AsyncSessionLocal() as kb_db:
            # merge() is synchronous in SQLAlchemy 2.0; awaiting it raises.
            merged = kb_db.merge(document)
            return await sync_document_to_kb(kb_db, merged)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "DO KB sync failed for document %s: %s",
            getattr(document, "id", "?"),
            exc,
        )
        return None
    finally:
        loop.close()


class ProcessingTask(Task):
    """Base class for processing tasks"""

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(f"Task {task_id} completed successfully")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"Task {task_id} failed: {str(exc)}")

        # Update job status if this is a processing job
        if args and len(args) > 0:
            job_id = args[0]
            db = SessionLocal()
            try:
                job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()

                if job:
                    job.fail_job(str(exc))
                    db.commit()
            except Exception as e:
                logger.error(f"Failed to update job status: {str(e)}")
            finally:
                db.close()


def _map_llm_entity_type_to_graph(llm_type: str) -> GraphEntityType:
    """Map LLM extraction type string to graph EntityType."""
    mapping = {
        "PERSON": GraphEntityType.PERSON,
        "ORGANIZATION": GraphEntityType.ORGANIZATION,
        "LOCATION": GraphEntityType.LOCATION,
        "CONCEPT": GraphEntityType.CONCEPT,
        "TECHNOLOGY": GraphEntityType.TECHNOLOGY,
        "RESEARCH": GraphEntityType.RESEARCH,
        "MODEL": GraphEntityType.PRODUCT,
        "DATASET": GraphEntityType.PRODUCT,
        "METHOD": GraphEntityType.CONCEPT,
        "METRIC": GraphEntityType.OTHER,
        "TOPIC": GraphEntityType.TOPIC,
        "EVENT": GraphEntityType.EVENT,
    }
    return mapping.get(llm_type.strip().upper(), GraphEntityType.OTHER)


def _safe_relationship_type(raw_type: str) -> GraphRelationshipType:
    if not raw_type:
        return GraphRelationshipType.RELATED_TO

    normalized = str(raw_type).strip().upper().replace("-", "_").replace(" ", "_")
    if not normalized:
        return GraphRelationshipType.RELATED_TO

    # Backward-compatible alias for extractor outputs.
    if normalized == "LEADS":
        normalized = "MANAGES"

    try:
        return GraphRelationshipType(normalized)
    except ValueError:
        return GraphRelationshipType.RELATED_TO


@current_app.task(base=ProcessingTask, bind=True, name="process_document_ingestion")
def process_document_ingestion(self, job_id: str):
    """Process complete document ingestion pipeline"""
    db = SessionLocal()
    try:
        # Get job and document
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = (
            db.query(Document)
            .filter(Document.id == job.parameters["document_id"])
            .first()
        )

        if not document:
            raise ValueError(f"Document not found for job {job_id}")

        # Atomic idempotency claim for acks_late redelivery. The Celery app sets
        # task_acks_late, so a worker killed mid-run never acks and the broker
        # redelivers this message. claim_job_for_processing serializes the
        # decision on a row lock: it short-circuits a job that already finished
        # (terminal) or is still running on another worker, and reclaims only one
        # whose worker died mid-run (stale RUNNING). A reclaim safely re-runs the
        # pipeline because every stage is idempotent — text/metadata are
        # overwritten, figure rows use delete-before-insert, DO KB sync reuses
        # the existing data source, the Neo4j path upserts, and the Postgres
        # entity writes below are replaced (not appended) per run.
        claim = claim_job_for_processing(
            db,
            job,
            worker_id=self.request.id,
            celery_task_id=self.request.id,
        )
        if not claim.proceed:
            logger.info(
                "Job %s not claimable (%s); skipping redelivered ingestion run",
                job_id,
                claim.reason,
            )
            return {
                "status": job.status.value,
                "document_id": str(document.id),
                "skipped": claim.reason,
            }

        # Initialize processing service
        processing_service = ProcessingPipeline(db)

        # Update document status (claim already moved the job to RUNNING).
        document.update_processing_status(ProcessingStatus.PROCESSING)
        db.commit()

        # Step 1: Text Extraction
        job.update_progress("Extracting text content", 20)
        db.commit()

        # Run async function in a managed event loop
        text_extraction_result = asyncio.run(
            processing_service.process_text_extraction(document)
        )

        if text_extraction_result["text_content"]:
            document.content_text = text_extraction_result["text_content"]
            document.content_summary = text_extraction_result["summary"]

            # Add metadata
            document.add_metadata("word_count", text_extraction_result["word_count"])
            document.add_metadata(
                "character_count", text_extraction_result["character_count"]
            )
        db.commit()

        # Step 1b: Figure extraction (optional, flag-gated; never fails ingestion)
        if (
            settings.FIGURE_EXTRACTION_ENABLED
            and document.document_type == DocumentType.PDF
        ):
            try:
                from src.services.processing.figure_extraction_service import (
                    extract_figures_for_document,
                    merge_captions_into_text,
                )

                job.update_progress("Extracting figures", 35)
                db.commit()
                fig_result = extract_figures_for_document(db, document)
                if fig_result.get("captions_text"):
                    document.content_text = merge_captions_into_text(
                        document.content_text, fig_result["captions_text"]
                    )
                db.commit()
            except Exception as fig_err:  # optional step, mirrors Neo4j tolerance above
                db.rollback()
                logger.warning(
                    f"Figure extraction failed for document {document.id}: {fig_err}"
                )

        # Step 2: Entity Extraction
        job.update_progress("Extracting entities", 50)
        db.commit()

        if document.content_text:
            # Run entity extraction in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                entities = loop.run_until_complete(
                    processing_service.process_entity_extraction(
                        document, document.content_text
                    )
                )
            finally:
                loop.close()

            # Replay-safe write: drop any spaCy/regex entities left by a prior
            # crashed run for this document before inserting the fresh set, so an
            # acks_late reclaim replaces rather than duplicates them. The delete
            # and the inserts commit in one transaction (all-or-nothing).
            _reset_pipeline_entities(db, document.id)
            for entity in entities:
                db.add(entity)
            db.commit()

            # Index entities into Neo4j knowledge graph
            job.update_progress("Indexing knowledge graph", 60)
            db.commit()

            try:
                from src.services.knowledge_graph.knowledge_graph_service import (
                    knowledge_graph_service,
                )

                kg_indexed = 0
                for entity in entities:
                    entity_id = knowledge_graph_service.create_entity_node(
                        entity_text=entity.name,
                        entity_type=(
                            entity.entity_type.value
                            if hasattr(entity.entity_type, "value")
                            else str(entity.entity_type)
                        ),
                        document_id=str(document.id),
                        confidence=entity.confidence_score or 0.8,
                        organization_id=(
                            str(document.organization_id)
                            if document.organization_id
                            else None
                        ),
                    )
                    if entity_id:
                        kg_indexed += 1
                logger.info(
                    f"Indexed {kg_indexed}/{len(entities)} entities into Neo4j for document {document.id}"
                )
            except Exception as e:
                logger.warning(
                    f"Neo4j indexing failed for document {document.id}: {e}. "
                    "Entities are still available in PostgreSQL."
                )

        # Step 3: Embedding Generation — push the document to DO KB, the
        # retrieval backend (replaces the dead Qdrant write). Idempotent and
        # gated by DO_KB_ENABLED; a None result (KB disabled/outage) is a clean
        # no-op so ingestion still completes.
        job.update_progress("Generating embeddings", 75)
        db.commit()

        if document.content_text:
            ds_uuid = _sync_document_to_kb_blocking(document)
            if ds_uuid:
                document.is_embedded = True
        db.commit()

        # Step 4: Generate Search Vector
        job.update_progress("Creating search index", 90)
        db.commit()

        # Update search vector for full-text search
        search_vector_ok = False
        try:
            fulltext_search_service.update_document_search_vector(str(document.id), db)
            search_vector_ok = True
            logger.info(f"Updated search vector for document {document.id}")
        except Exception as e:
            logger.warning(
                f"Failed to update search vector for document {document.id}: {e}"
            )

        # Step 5: Finalize
        job.update_progress("Finalizing", 95)
        db.commit()

        # Mark document as processed. is_indexed must reflect ACTUAL full-text
        # searchability: if the search-vector build above failed the document has
        # no tsvector and the primary full-text retrieval can never surface it —
        # claiming is_indexed=True there is a silent partial index (the doc looks
        # ready but is unreachable). Tie the flag to the real outcome so a
        # re-index can be triggered for the not-yet-searchable docs.
        document.update_processing_status(ProcessingStatus.COMPLETED)
        document.is_indexed = search_vector_ok
        db.commit()

        # Complete job
        job.complete_job(
            result={
                "text_extracted": bool(document.content_text),
                "entities_found": len(entities) if "entities" in locals() else 0,
                # is_embedded is the source of truth (set after DO KB sync).
                # embedding_id is the dead Qdrant vector-id column (always NULL
                # now), so bool(embedding_id) always reported False.
                "embedding_generated": bool(document.is_embedded),
                "search_indexed": search_vector_ok,
                "word_count": text_extraction_result.get("word_count", 0),
            }
        )
        db.commit()

        logger.info(f"Successfully processed document {document.id}")

        return {
            "status": "completed",
            "document_id": str(document.id),
            "processing_time": job.duration_seconds,
        }

    except Exception as e:
        logger.error(f"Document ingestion failed for job {job_id}: {str(e)}")

        # Roll back first: if the failure came from a DB op the session is
        # poisoned (PendingRollbackError), so the queries/commit below to write
        # the FAILED status would themselves throw and get swallowed — leaving
        # the document stuck in PROCESSING (never FAILED), which then blocks
        # content-hash dedup from ever re-uploading it.
        db.rollback()

        # Update document and job status
        try:
            document = (
                db.query(Document)
                .filter(Document.id == job.parameters["document_id"])
                .first()
            )

            if document:
                document.update_processing_status(ProcessingStatus.FAILED, str(e))

            if job:
                job.fail_job(str(e))
            db.commit()

        except Exception as update_error:
            logger.error(f"Failed to update failure status: {str(update_error)}")

        raise

    finally:
        db.close()


@current_app.task(base=ProcessingTask, bind=True, name="extract_text_content")
def extract_text_content(self, job_id: str):
    """Extract text content from document"""
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = (
            db.query(Document)
            .filter(Document.id == job.parameters["document_id"])
            .first()
        )

        if not document:
            raise ValueError(f"Document not found for job {job_id}")

        # Start job
        job.start_job(worker_id=self.request.id)
        db.commit()

        # Extract text. process_text_extraction is async — run it in a managed
        # event loop (mirrors the process_document task and extract_entities).
        # Calling it without asyncio.run returned a coroutine, so the next line
        # (result["text_content"]) raised "'coroutine' object is not
        # subscriptable" and this task failed on every document.
        processing_service = ProcessingPipeline(db)
        result = asyncio.run(processing_service.process_text_extraction(document))

        # Update document
        document.content_text = result["text_content"]
        document.content_summary = result["summary"]

        # Add metadata
        document.add_metadata("word_count", result["word_count"])
        document.add_metadata("character_count", result["character_count"])
        db.commit()

        # Complete job
        job.complete_job(result=result)
        db.commit()

        return result

    except Exception as e:
        logger.error(f"Text extraction failed for job {job_id}: {str(e)}")
        # Roll back a possibly-poisoned session before writing fail state.
        db.rollback()
        if job:
            job.fail_job(str(e))
            db.commit()
        raise

    finally:
        db.close()


@current_app.task(base=ProcessingTask, bind=True, name="extract_entities")
def extract_entities(self, job_id: str):
    """Extract entities from document text"""
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = (
            db.query(Document)
            .filter(Document.id == job.parameters["document_id"])
            .first()
        )

        if not document:
            raise ValueError(f"Document not found for job {job_id}")

        if not document.content_text:
            raise ValueError("No text content available for entity extraction")

        # Start job
        job.start_job(worker_id=self.request.id)
        db.commit()

        # Extract entities. asyncio.run creates + manages a fresh loop;
        # get_event_loop().run_until_complete raises "no current event loop"
        # / deprecation on Python 3.10+ in a worker thread.
        service = LLMEntityExtractionService()
        extraction_result = asyncio.run(service.extract_entities(document.content_text))

        # A timeout that skips chunks (or all-chunks-failed) sets
        # ExtractionResult.error while still returning the entities found so far.
        # Surface it instead of reporting unqualified success.
        if extraction_result.error:
            logger.warning(
                "Entity extraction for document %s was partial: %s",
                document.id,
                extraction_result.error,
            )

        # Save entities
        from datetime import datetime

        from src.models.entity import Entity, ExtractionMethod
        from src.services.processing.llm_entity_extraction import map_to_entity_type

        saved_entities = []
        for ent in extraction_result.entities:
            entity = Entity(
                entity_type=map_to_entity_type(ent.type),
                name=ent.name,
                canonical_name=ent.canonical_name,
                aliases=ent.aliases,
                description=ent.description,
                confidence=ent.confidence,
                extraction_method=ExtractionMethod.OPENAI,
                extracted_at=datetime.utcnow(),
                extraction_model="gpt-5-nano",
                document_id=document.id,
                organization_id=document.organization_id,
            )
            db.add(entity)
            saved_entities.append(entity)
        db.commit()

        # Complete job
        job.complete_job(
            result={
                "entities_extracted": len(saved_entities),
                "entity_types": list(
                    set(ent.type for ent in extraction_result.entities)
                ),
                "extraction_error": extraction_result.error,
                "partial": bool(extraction_result.error),
            }
        )
        db.commit()

        return {
            "entities_extracted": len(saved_entities),
            "entities": [e.to_dict() for e in saved_entities],
        }

    except Exception as e:
        logger.error(f"Entity extraction failed for job {job_id}: {str(e)}")
        # Roll back a possibly-poisoned session before writing fail state.
        db.rollback()
        if job:
            job.fail_job(str(e))
            db.commit()
        raise

    finally:
        db.close()


@current_app.task(base=ProcessingTask, bind=True, name="generate_embeddings")
def generate_embeddings(self, job_id: str):
    """Generate embeddings for document"""
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = (
            db.query(Document)
            .filter(Document.id == job.parameters["document_id"])
            .first()
        )

        if not document:
            raise ValueError(f"Document not found for job {job_id}")

        if not document.content_text:
            raise ValueError("No text content available for embedding generation")

        # Start job
        job.start_job(worker_id=self.request.id)
        db.commit()

        # Push the document to DO KB (retrieval backend; replaces dead Qdrant).
        ds_uuid = _sync_document_to_kb_blocking(document)

        # Update document
        if ds_uuid:
            document.is_embedded = True
            db.commit()

            # Complete job
            job.complete_job(result={"do_kb_data_source_uuid": ds_uuid})
            db.commit()

            return {"do_kb_data_source_uuid": ds_uuid, "status": "success"}
        else:
            # DO KB disabled or returned nothing — not a failure. Complete the
            # job cleanly rather than raising (there is no other embedding
            # backend now that Qdrant is gone).
            job.complete_job(
                result={"status": "skipped", "reason": "do_kb_unavailable"}
            )
            db.commit()
            return {"status": "skipped", "reason": "do_kb_unavailable"}

    except Exception as e:
        logger.error(f"Embedding generation failed for job {job_id}: {str(e)}")
        # Roll back a possibly-poisoned session before writing fail state.
        db.rollback()
        if job:
            job.fail_job(str(e))
            db.commit()
        raise

    finally:
        db.close()


@current_app.task(base=ProcessingTask, bind=True, name="index_in_graph")
def index_in_graph(self, job_id: str):
    """Index document and entities in knowledge graph"""
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = (
            db.query(Document)
            .filter(Document.id == job.parameters["document_id"])
            .first()
        )

        if not document:
            raise ValueError(f"Document not found for job {job_id}")

        # Start job
        job.start_job(worker_id=self.request.id)
        db.commit()

        # Get entities for this document
        entities = db.query(Entity).filter(Entity.document_id == document.id).all()

        # Index in Neo4j (this would be implemented with actual Neo4j client)
        # For now, simulate the process
        indexed_entities = []
        for entity in entities:
            # Simulate graph indexing
            entity.is_in_knowledge_graph = True
            entity.graph_id = f"neo4j_node_{entity.id}"
            indexed_entities.append(entity)

        db.commit()

        # Mark document as indexed
        document.is_indexed = True
        db.commit()

        # Complete job
        job.complete_job(
            result={"entities_indexed": len(indexed_entities), "document_indexed": True}
        )
        db.commit()

        return {
            "entities_indexed": len(indexed_entities),
            "document_indexed": True,
            "status": "success",
        }

    except Exception as e:
        logger.error(f"Graph indexing failed for job {job_id}: {str(e)}")
        # Roll back a possibly-poisoned session before writing fail state.
        db.rollback()
        if job:
            job.fail_job(str(e))
            db.commit()
        raise

    finally:
        db.close()


@current_app.task(base=ProcessingTask, bind=True, name="kg_extract_entities_job")
def kg_extract_entities_job(self, job_id: str):
    """Extract entities from a document and index them into knowledge graph."""
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Idempotency guard for acks_late redelivery (same pattern as
        # process_document_ingestion above): a worker killed after completion
        # but before the broker ack redelivers the message, which would re-run
        # the full LLM extraction and regress the job COMPLETED -> RUNNING.
        if job.status == JobStatus.COMPLETED:
            logger.info(
                f"Job {job_id} already completed; skipping redelivered KG extraction"
            )
            return {
                "status": "completed",
                "job_id": job_id,
                "skipped": "duplicate_delivery",
            }

        job.start_job(worker_id=self.request.id, celery_task_id=self.request.id)
        db.commit()

        document_ids = []
        if job.parameters:
            if job.parameters.get("document_ids"):
                document_ids = [
                    str(doc_id) for doc_id in job.parameters.get("document_ids", [])
                ]
            elif job.parameters.get("document_id"):
                document_ids = [str(job.parameters.get("document_id"))]
        if not document_ids:
            raise ValueError("Missing document_id(s) in job parameters")

        entities_found_total = 0
        entities_created_total = 0
        relationships_found_total = 0
        relationships_created_total = 0
        errors_total = 0
        extraction_errors_total = 0

        total_docs = len(document_ids)
        for index, document_id in enumerate(document_ids):
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                errors_total += 1
                continue

            content = document.content_text or ""
            if not content.strip():
                errors_total += 1
                continue

            job.update_progress(
                f"Extracting entities ({index + 1}/{total_docs})",
                min(80.0, ((index + 1) / max(total_docs, 1)) * 70.0),
            )
            db.commit()

            service = LLMEntityExtractionService()
            extraction_result = asyncio.run(
                service.extract_entities(content, timeout_seconds=300.0)
            )
            if extraction_result.error:
                extraction_errors_total += 1
                logger.warning(
                    "Entity extraction partial for document %s in KG job: %s",
                    document.id,
                    extraction_result.error,
                )

            extracted_entities = extraction_result.entities
            extracted_relationships = extraction_result.relationships
            entities_found_total += len(extracted_entities)
            relationships_found_total += len(extracted_relationships)

            create_requests = []
            for ent in extracted_entities:
                create_requests.append(
                    CreateEntityRequest(
                        name=ent.name,
                        entity_type=_map_llm_entity_type_to_graph(ent.type),
                        confidence_score=min(1.0, max(0.0, ent.confidence)),
                        extraction_method=GraphExtractionMethod.LLM_EXTRACTION,
                        position=None,
                        context=ent.description,
                        metadata={
                            "source": "background_extraction_job",
                            "document_id": str(document.id),
                            "aliases": ent.aliases,
                        },
                        source_document_id=str(document.id),
                        organization_id=(
                            str(document.organization_id)
                            if document.organization_id
                            else None
                        ),
                    )
                )

            entity_result = knowledge_graph_service.create_entities_batch(
                BatchEntityRequest(
                    entities=create_requests,
                    relationships=[],
                    upsert=True,
                    document_id=str(document.id),
                )
            )

            entities_created_total += len(entity_result.created_entities)
            errors_total += len(entity_result.errors)

            # Map created graph node IDs by entity name. Relationships from the
            # LLM extractor reference entity names (already remapped to the kept
            # merged entity's name in _resolve_relationships), so a name lookup
            # is sufficient to resolve endpoints to the nodes just created.
            created_id_by_name = {}
            for created in entity_result.created_entities:
                created_id_by_name[created.name.strip().lower()] = created.id

            relationship_requests = []
            for relationship in extracted_relationships:
                source_entity_id = created_id_by_name.get(
                    relationship.source.strip().lower()
                )
                target_entity_id = created_id_by_name.get(
                    relationship.target.strip().lower()
                )
                if not source_entity_id or not target_entity_id:
                    continue

                confidence = min(1.0, max(0.0, float(relationship.confidence)))
                evidence = relationship.evidence
                relationship_requests.append(
                    CreateRelationshipRequest(
                        source_entity_id=source_entity_id,
                        target_entity_id=target_entity_id,
                        relationship_type=_safe_relationship_type(
                            relationship.relationship_type
                        ),
                        strength=confidence,
                        confidence_score=confidence,
                        context=evidence,
                        evidence=[evidence] if evidence else [],
                        metadata={
                            "source": "background_extraction_job",
                            "document_id": str(document.id),
                        },
                        source_document_id=str(document.id),
                        organization_id=(
                            str(document.organization_id)
                            if document.organization_id
                            else None
                        ),
                    )
                )

            if relationship_requests:
                relationship_result = knowledge_graph_service.create_entities_batch(
                    BatchEntityRequest(
                        entities=[],
                        relationships=relationship_requests,
                        upsert=True,
                        document_id=str(document.id),
                    )
                )
                relationships_created_total += len(
                    relationship_result.created_relationships
                )
                errors_total += len(relationship_result.errors)

        job.update_progress("Finalizing extraction job", 90)

        result = {
            "document_ids": document_ids,
            "entities_found": entities_found_total,
            "entities_created": entities_created_total,
            "relationships_found": relationships_found_total,
            "relationships_created": relationships_created_total,
            "errors": errors_total,
            "extraction_errors": extraction_errors_total,
        }

        # Honest outcome: if NOTHING was created and something errored (all
        # documents missing/empty, or every KG write failed), completing the job
        # reports a false success to anything polling job status. Fail it so the
        # total failure is visible; a legitimately-empty run (no creates, no
        # errors) still completes.
        total_created = entities_created_total + relationships_created_total
        total_errors = errors_total + extraction_errors_total
        if total_created == 0 and total_errors > 0:
            job.fail_job(
                f"KG extraction created no entities or relationships "
                f"({total_errors} errors across {total_docs} documents)",
                error_type="extraction_failed",
            )
            db.commit()
            return {"status": "failed", "job_id": job_id, "result": result}

        job.complete_job(result=result)
        db.commit()
        return {"status": "completed", "job_id": job_id}
    except Exception as e:
        # Roll back a possibly-poisoned session before writing fail state.
        db.rollback()
        if "job" in locals() and job:
            job.fail_job(str(e), error_type=type(e).__name__)
            db.commit()
        raise
    finally:
        db.close()


@current_app.task(base=ProcessingTask, bind=True, name="kg_merge_entities_job")
def kg_merge_entities_job(self, job_id: str):
    """Merge duplicate entity groups into suggested primary entities."""
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        groups = (job.parameters or {}).get("groups", [])
        if not groups:
            raise ValueError("No groups provided for merge job")

        job.start_job(worker_id=self.request.id, celery_task_id=self.request.id)
        db.commit()

        success_count = 0
        failure_count = 0

        total_groups = len(groups)
        for index, group in enumerate(groups):
            group_entities = group.get("entities", [])
            primary_id = group.get("suggested_primary")
            if not primary_id or not group_entities:
                failure_count += 1
                continue

            duplicate_ids = [
                e.get("id")
                for e in group_entities
                if e.get("id") and e.get("id") != primary_id
            ]
            step_message = f"Merging group {index + 1}/{total_groups}"
            job.update_progress(
                step_message, min(90.0, ((index + 1) / max(total_groups, 1)) * 85.0)
            )
            db.commit()

            try:
                for duplicate_id in duplicate_ids:
                    relationships = knowledge_graph_service.get_relationships(
                        duplicate_id
                    )
                    for rel in relationships:
                        create_request = CreateRelationshipRequest(
                            source_entity_id=(
                                primary_id
                                if rel.source_entity_id == duplicate_id
                                else rel.source_entity_id
                            ),
                            target_entity_id=(
                                primary_id
                                if rel.target_entity_id == duplicate_id
                                else rel.target_entity_id
                            ),
                            relationship_type=_safe_relationship_type(
                                getattr(
                                    rel.relationship_type,
                                    "value",
                                    rel.relationship_type,
                                )
                            ),
                            strength=rel.strength,
                            confidence_score=rel.confidence_score,
                            context=rel.context,
                            evidence=rel.evidence or [],
                            metadata=rel.metadata or {},
                            source_document_id=rel.source_document_id,
                        )
                        try:
                            knowledge_graph_service.create_relationship(create_request)
                        except Exception as rel_error:
                            # Duplicate-relationship inserts are expected while
                            # re-pointing edges onto the primary; log at debug so
                            # a genuine create failure isn't fully invisible.
                            logger.debug(
                                "Skipped relationship insert during entity merge: %s",
                                rel_error,
                                exc_info=True,
                            )

                    knowledge_graph_service.delete_entity(duplicate_id)

                success_count += 1
            except Exception as merge_error:
                # A group that fails to merge was previously counted but never
                # logged, so the cause was invisible while the job still reported
                # COMPLETED. Log which group failed and why.
                failure_count += 1
                logger.warning(
                    "Failed to merge entity group %s/%s (primary %s): %s",
                    index + 1,
                    total_groups,
                    primary_id,
                    merge_error,
                    exc_info=True,
                )

        job.update_progress("Finalizing merge job", 95)
        job.complete_job(
            result={
                "total_groups": total_groups,
                "merged_groups": success_count,
                "failed_groups": failure_count,
            }
        )
        db.commit()
        return {"status": "completed", "job_id": job_id}
    except Exception as e:
        # Roll back a possibly-poisoned session before writing fail state.
        db.rollback()
        if "job" in locals() and job:
            job.fail_job(str(e), error_type=type(e).__name__)
            db.commit()
        raise
    finally:
        db.close()


# Terminal ProcessingJob states (mirrors ProcessingJob.is_finished). Everything
# else — PENDING, QUEUED, RUNNING, RETRYING — is non-terminal and sweepable.
_TERMINAL_PROCESSING_STATUSES = frozenset(
    {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
)
_NON_TERMINAL_PROCESSING_STATUSES = [
    status for status in JobStatus if status not in _TERMINAL_PROCESSING_STATUSES
]


@current_app.task(name="src.tasks.processing_tasks.sweep_stuck_processing_jobs")
def sweep_stuck_processing_jobs() -> dict:
    """Fail non-terminal processing_jobs rows that stopped making progress.

    Audit P1.4b / D7: ``cleanup_old_jobs`` below only ever deletes TERMINAL
    rows, so a job whose worker died (OOM-kill, pod eviction, crash between
    status writes) sat in pending/queued/running/retrying forever, invisibly
    "in progress" to the UI.

    ``updated_at`` is bumped by every progress write, and Celery's hard time
    limit is 600s — so a non-terminal row silent for
    ``PROCESSING_JOB_STUCK_AFTER_SECONDS`` (default 30 min, ≥3× the max legal
    task runtime) is definitively stuck and is marked FAILED with an explicit
    sweep message. Conservative by design: mark-failed only, never re-enqueue
    (the task may have partially executed). Known edge: with acks_late a
    QUEUED row swept during an extreme (>30 min) broker backlog can still be
    picked up later — its start_job/complete writes simply overwrite the
    sweep, so the job self-heals; the sweep is logged either way.

    Flag-gated by SWEEPERS_ENABLED (values-controllable kill switch).
    """
    from src.core.config import get_settings

    settings_local = get_settings()
    if not settings_local.SWEEPERS_ENABLED:
        logger.info("sweep_stuck_processing_jobs: skipped (SWEEPERS_ENABLED=false)")
        return {"skipped": "sweepers-disabled"}

    threshold_seconds = settings_local.PROCESSING_JOB_STUCK_AFTER_SECONDS
    # Naive-UTC cutoff matches this model's BaseModel timestamps
    # (default/onupdate=datetime.utcnow) and cleanup_old_jobs' convention.
    cutoff = datetime.utcnow() - timedelta(seconds=threshold_seconds)

    db = SessionLocal()
    try:
        stuck_jobs = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.status.in_(_NON_TERMINAL_PROCESSING_STATUSES),
                ProcessingJob.updated_at < cutoff,
                ProcessingJob.is_deleted == False,  # noqa: E712
            )
            .limit(200)
            .all()
        )

        for job in stuck_jobs:
            prior_status = job.status.value if job.status else "unknown"
            last_update = job.updated_at.isoformat() if job.updated_at else "unknown"
            logger.warning(
                "sweep_stuck_processing_jobs: failing job %s (type=%s, was=%s, "
                "last update %s, threshold %ss)",
                job.id,
                job.job_type.value if job.job_type else "unknown",
                prior_status,
                last_update,
                threshold_seconds,
            )
            job.fail_job(
                f"Swept as stuck: status '{prior_status}' with no update since "
                f"{last_update} (threshold {threshold_seconds}s; Celery hard "
                "time limit is 600s)",
                error_type="StuckJobSweep",
            )

        db.commit()
        result = {"swept": len(stuck_jobs)}
        logger.info("sweep_stuck_processing_jobs: %s", result)
        return result
    except Exception as e:
        db.rollback()
        logger.error(f"Stuck-job sweep failed: {str(e)}")
        raise
    finally:
        db.close()


@current_app.task
def cleanup_old_jobs():
    """Cleanup old processing jobs"""
    db = SessionLocal()
    try:
        # Delete jobs older than 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        old_jobs = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.created_at < cutoff_date,
                ProcessingJob.status.in_(
                    [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
                ),
            )
            .all()
        )

        for job in old_jobs:
            db.delete(job)

        db.commit()
        logger.info(f"Cleaned up {len(old_jobs)} old processing jobs")

        return {"cleaned_jobs": len(old_jobs)}

    except Exception as e:
        logger.error(f"Job cleanup failed: {str(e)}")
        raise

    finally:
        db.close()


# Periodic tasks
from celery.schedules import crontab

# Merge (not assign) — every task module shares one app.conf.beat_schedule, so a
# full `= {...}` here is clobbered by whichever module Celery imports last
# (include order in celery_app.py). .update() lets all modules' schedules coexist.
current_app.conf.beat_schedule.update(
    {
        "cleanup-old-jobs": {
            "task": "src.tasks.processing_tasks.cleanup_old_jobs",
            "schedule": crontab(hour=2, minute=0),  # Run daily at 2 AM
        },
    }
)
