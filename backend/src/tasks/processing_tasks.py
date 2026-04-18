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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.core.database import get_db
from src.tasks.celery_app import celery_app
from src.models.document import Document, ProcessingStatus
from src.models.entity import Entity
from src.models.graph import (
    BatchEntityRequest,
    CreateEntityRequest,
    CreateRelationshipRequest,
    EntityType as GraphEntityType,
    ExtractionMethod as GraphExtractionMethod,
    RelationshipType as GraphRelationshipType,
)
from src.models.processing import JobStatus, ProcessingJob
from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service
from src.services.processing.entity_extraction_service import (
    EntityExtractionService,
    EntityType as ProcessingEntityType,
)
from src.services.processing.processing_service import ProcessingPipeline
from src.services.search.fulltext_search_service import fulltext_search_service

logger = logging.getLogger(__name__)

# Database session for tasks
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


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


def _map_processing_entity_type_to_graph(
    entity_type: ProcessingEntityType,
) -> GraphEntityType:
    mapping = {
        "person": GraphEntityType.PERSON,
        "organization": GraphEntityType.ORGANIZATION,
        "location": GraphEntityType.LOCATION,
        "product": GraphEntityType.PRODUCT,
        "concept": GraphEntityType.CONCEPT,
        "date": GraphEntityType.DATE,
        "number": GraphEntityType.OTHER,
        "email": GraphEntityType.EMAIL,
        "phone": GraphEntityType.PHONE,
        "url": GraphEntityType.URL,
        "custom": GraphEntityType.OTHER,
    }
    return mapping.get(entity_type.value, GraphEntityType.OTHER)


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


@current_app.task(base=ProcessingTask, bind=True)
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

        # Initialize processing service
        processing_service = ProcessingPipeline(db)

        # Start job
        job.start_job(worker_id=self.request.id)
        db.commit()

        # Update document status
        document.update_processing_status(ProcessingStatus.PROCESSING)
        db.commit()

        # Step 1: Text Extraction
        job.update_progress("Extracting text content", 20)
        db.commit()

        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            text_extraction_result = loop.run_until_complete(
                processing_service.process_text_extraction(document)
            )
        finally:
            loop.close()

        if text_extraction_result["text_content"]:
            document.content_text = text_extraction_result["text_content"]
            document.content_summary = text_extraction_result["summary"]

            # Add metadata
            document.add_metadata("word_count", text_extraction_result["word_count"])
            document.add_metadata(
                "character_count", text_extraction_result["character_count"]
            )
        db.commit()

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
                        entity_type=entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type),
                        document_id=str(document.id),
                        confidence=entity.confidence_score or 0.8,
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

        # Step 3: Embedding Generation
        job.update_progress("Generating embeddings", 75)
        db.commit()

        if document.content_text:
            # Run embedding generation in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                embedding_id = loop.run_until_complete(
                    processing_service.process_embedding_generation(
                        document, document.content_text
                    )
                )
            finally:
                loop.close()

            if embedding_id:
                document.embedding_id = embedding_id
                document.is_embedded = True
        db.commit()

        # Step 4: Generate Search Vector
        job.update_progress("Creating search index", 90)
        db.commit()

        # Update search vector for full-text search
        try:
            fulltext_search_service.update_document_search_vector(str(document.id), db)
            logger.info(f"Updated search vector for document {document.id}")
        except Exception as e:
            logger.warning(
                f"Failed to update search vector for document {document.id}: {e}"
            )

        # Step 5: Finalize
        job.update_progress("Finalizing", 95)
        db.commit()

        # Mark document as processed
        document.update_processing_status(ProcessingStatus.COMPLETED)
        document.is_indexed = True
        db.commit()

        # Complete job
        job.complete_job(
            result={
                "text_extracted": bool(document.content_text),
                "entities_found": len(entities) if "entities" in locals() else 0,
                "embedding_generated": bool(document.embedding_id),
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


@current_app.task(base=ProcessingTask, bind=True)
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

        # Extract text
        processing_service = ProcessingPipeline(db)
        result = processing_service.process_text_extraction(document)

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
        if job:
            job.fail_job(str(e))
            db.commit()
        raise

    finally:
        db.close()


@current_app.task(base=ProcessingTask, bind=True)
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

        # Extract entities
        processing_service = ProcessingPipeline(db)
        entities = processing_service.process_entity_extraction(
            document, document.content_text
        )

        # Save entities
        saved_entities = []
        for entity in entities:
            db.add(entity)
            saved_entities.append(entity)
        db.commit()

        # Complete job
        job.complete_job(
            result={
                "entities_extracted": len(saved_entities),
                "entity_types": list(set(e.entity_type.value for e in saved_entities)),
            }
        )
        db.commit()

        return {
            "entities_extracted": len(saved_entities),
            "entities": [e.to_dict() for e in saved_entities],
        }

    except Exception as e:
        logger.error(f"Entity extraction failed for job {job_id}: {str(e)}")
        if job:
            job.fail_job(str(e))
            db.commit()
        raise

    finally:
        db.close()


@current_app.task(base=ProcessingTask, bind=True)
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

        # Generate embeddings
        processing_service = ProcessingPipeline(db)
        embedding_id = processing_service.process_embedding_generation(
            document, document.content_text
        )

        # Update document
        if embedding_id:
            document.embedding_id = embedding_id
            document.is_embedded = True
            db.commit()

            # Complete job
            job.complete_job(result={"embedding_id": embedding_id})
            db.commit()

            return {"embedding_id": embedding_id, "status": "success"}
        else:
            raise ValueError("Failed to generate embeddings")

    except Exception as e:
        logger.error(f"Embedding generation failed for job {job_id}: {str(e)}")
        if job:
            job.fail_job(str(e))
            db.commit()
        raise

    finally:
        db.close()


@current_app.task(base=ProcessingTask, bind=True)
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

        job.start_job(worker_id=self.request.id, celery_task_id=self.request.id)
        db.commit()

        extractor = EntityExtractionService()
        document_ids = []
        if job.parameters:
            if job.parameters.get("document_ids"):
                document_ids = [str(doc_id) for doc_id in job.parameters.get("document_ids", [])]
            elif job.parameters.get("document_id"):
                document_ids = [str(job.parameters.get("document_id"))]
        if not document_ids:
            raise ValueError("Missing document_id(s) in job parameters")

        entities_found_total = 0
        entities_created_total = 0
        relationships_found_total = 0
        relationships_created_total = 0
        errors_total = 0

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

            extracted_entities, extracted_relationships = extractor.extract_entities_and_relationships_from_text(
                document, content
            )
            entities_found_total += len(extracted_entities)
            relationships_found_total += len(extracted_relationships)

            create_requests = []
            for ent in extracted_entities:
                create_requests.append(
                    CreateEntityRequest(
                        name=ent.name,
                        entity_type=_map_processing_entity_type_to_graph(ent.entity_type),
                        confidence_score=min(1.0, max(0.0, ent.confidence or 0.8)),
                        extraction_method=GraphExtractionMethod.MANUAL,
                        position=None,
                        context=ent.description,
                        metadata={
                            "source": "background_extraction_job",
                            "document_id": str(document.id),
                        },
                        source_document_id=str(document.id),
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

            # Build a lookup from extracted entity signature to created graph node ID.
            created_entity_id_by_key = {}
            for created in entity_result.created_entities:
                created_key = (
                    created.entity_type.value,
                    created.name.strip().lower(),
                )
                created_entity_id_by_key[created_key] = created.id

            relationship_requests = []
            for relationship in extracted_relationships:
                source_entity = relationship.get("source_entity")
                target_entity = relationship.get("target_entity")
                if not source_entity or not target_entity:
                    continue

                source_graph_type = _map_processing_entity_type_to_graph(source_entity.entity_type)
                target_graph_type = _map_processing_entity_type_to_graph(target_entity.entity_type)

                source_key = (source_graph_type.value, (source_entity.name or "").strip().lower())
                target_key = (target_graph_type.value, (target_entity.name or "").strip().lower())
                source_entity_id = created_entity_id_by_key.get(source_key)
                target_entity_id = created_entity_id_by_key.get(target_key)
                if not source_entity_id or not target_entity_id:
                    continue

                confidence = float(relationship.get("confidence", 0.7))
                confidence = min(1.0, max(0.0, confidence))
                evidence = relationship.get("evidence")
                relationship_requests.append(
                    CreateRelationshipRequest(
                        source_entity_id=source_entity_id,
                        target_entity_id=target_entity_id,
                        relationship_type=_safe_relationship_type(
                            relationship.get("relationship_type", "")
                        ),
                        strength=confidence,
                        confidence_score=confidence,
                        context=evidence,
                        evidence=[evidence] if evidence else [],
                        metadata={
                            "source": "background_extraction_job",
                            "document_id": str(document.id),
                            "pattern_matched": relationship.get("pattern_matched"),
                        },
                        source_document_id=str(document.id),
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
                relationships_created_total += len(relationship_result.created_relationships)
                errors_total += len(relationship_result.errors)

        job.update_progress("Finalizing extraction job", 90)

        job.complete_job(
            result={
                "document_ids": document_ids,
                "entities_found": entities_found_total,
                "entities_created": entities_created_total,
                "relationships_found": relationships_found_total,
                "relationships_created": relationships_created_total,
                "errors": errors_total,
            }
        )
        db.commit()
        return {"status": "completed", "job_id": job_id}
    except Exception as e:
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

            duplicate_ids = [e.get("id") for e in group_entities if e.get("id") and e.get("id") != primary_id]
            step_message = f"Merging group {index + 1}/{total_groups}"
            job.update_progress(step_message, min(90.0, ((index + 1) / max(total_groups, 1)) * 85.0))
            db.commit()

            try:
                for duplicate_id in duplicate_ids:
                    relationships = knowledge_graph_service.get_relationships(duplicate_id)
                    for rel in relationships:
                        create_request = CreateRelationshipRequest(
                            source_entity_id=primary_id if rel.source_entity_id == duplicate_id else rel.source_entity_id,
                            target_entity_id=primary_id if rel.target_entity_id == duplicate_id else rel.target_entity_id,
                            relationship_type=_safe_relationship_type(
                                getattr(rel.relationship_type, "value", rel.relationship_type)
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
                        except Exception:
                            # Ignore duplicate relationship insertion errors
                            pass

                    knowledge_graph_service.delete_entity(duplicate_id)

                success_count += 1
            except Exception:
                failure_count += 1

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
        if "job" in locals() and job:
            job.fail_job(str(e), error_type=type(e).__name__)
            db.commit()
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

current_app.conf.beat_schedule = {
    "cleanup-old-jobs": {
        "task": "src.tasks.processing_tasks.cleanup_old_jobs",
        "schedule": crontab(hour=2, minute=0),  # Run daily at 2 AM
    },
}
