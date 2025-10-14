"""
Celery tasks for document processing
"""

import os
import sys
import logging
import asyncio
from typing import Dict, Any
from datetime import datetime, timedelta
from celery import Task

# Add src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from celery import Celery, current_app

# Create Celery app
celery_app = Celery(
    'multimodal_rag',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0',
    include=['src.tasks.processing_tasks']
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.core.database import get_db
from src.models.document import Document, ProcessingStatus
from src.models.processing import ProcessingJob, JobStatus
from src.models.entity import Entity
from src.services.processing_service import ProcessingPipeline

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
                job = db.query(ProcessingJob).filter(
                    ProcessingJob.id == job_id
                ).first()

                if job:
                    job.fail_job(str(exc))
                    db.commit()
            except Exception as e:
                logger.error(f"Failed to update job status: {str(e)}")
            finally:
                db.close()

@current_app.task(base=ProcessingTask, bind=True)
def process_document_ingestion(self, job_id: str):
    """Process complete document ingestion pipeline"""
    db = SessionLocal()
    try:
        # Get job and document
        job = db.query(ProcessingJob).filter(
            ProcessingJob.id == job_id
        ).first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = db.query(Document).filter(
            Document.id == job.parameters["document_id"]
        ).first()

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
            document.add_metadata("character_count", text_extraction_result["character_count"])
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

        # Step 4: Finalize
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
                "entities_found": len(entities) if 'entities' in locals() else 0,
                "embedding_generated": bool(document.embedding_id),
                "word_count": text_extraction_result.get("word_count", 0)
            }
        )
        db.commit()

        logger.info(f"Successfully processed document {document.id}")

        return {
            "status": "completed",
            "document_id": str(document.id),
            "processing_time": job.duration_seconds
        }

    except Exception as e:
        logger.error(f"Document ingestion failed for job {job_id}: {str(e)}")

        # Update document and job status
        try:
            document = db.query(Document).filter(
                Document.id == job.parameters["document_id"]
            ).first()

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
        job = db.query(ProcessingJob).filter(
            ProcessingJob.id == job_id
        ).first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = db.query(Document).filter(
            Document.id == job.parameters["document_id"]
        ).first()

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
        job = db.query(ProcessingJob).filter(
            ProcessingJob.id == job_id
        ).first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = db.query(Document).filter(
            Document.id == job.parameters["document_id"]
        ).first()

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
        job.complete_job(result={
            "entities_extracted": len(saved_entities),
            "entity_types": list(set(e.entity_type.value for e in saved_entities))
        })
        db.commit()

        return {
            "entities_extracted": len(saved_entities),
            "entities": [e.to_dict() for e in saved_entities]
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
        job = db.query(ProcessingJob).filter(
            ProcessingJob.id == job_id
        ).first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = db.query(Document).filter(
            Document.id == job.parameters["document_id"]
        ).first()

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
        job = db.query(ProcessingJob).filter(
            ProcessingJob.id == job_id
        ).first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = db.query(Document).filter(
            Document.id == job.parameters["document_id"]
        ).first()

        if not document:
            raise ValueError(f"Document not found for job {job_id}")

        # Start job
        job.start_job(worker_id=self.request.id)
        db.commit()

        # Get entities for this document
        entities = db.query(Entity).filter(
            Entity.document_id == document.id
        ).all()

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
        job.complete_job(result={
            "entities_indexed": len(indexed_entities),
            "document_indexed": True
        })
        db.commit()

        return {
            "entities_indexed": len(indexed_entities),
            "document_indexed": True,
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Graph indexing failed for job {job_id}: {str(e)}")
        if job:
            job.fail_job(str(e))
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

        old_jobs = db.query(ProcessingJob).filter(
            ProcessingJob.created_at < cutoff_date,
            ProcessingJob.status.in_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED])
        ).all()

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
    'cleanup-old-jobs': {
        'task': 'src.tasks.processing_tasks.cleanup_old_jobs',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
    },
}