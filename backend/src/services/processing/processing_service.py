"""
Multimodal processing pipeline service
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from celery import Celery
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import get_db
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.entity import Entity, EntityType, ExtractionMethod
from src.models.processing import JobPriority, JobStatus, JobType, ProcessingJob
from src.services.processing.audio_processing_service import AudioProcessingService
from src.services.processing.entity_extraction_service import EntityExtractionService
from src.services.processing.image_processing_service import ImageProcessingService
from src.services.processing.video_processing_service import VideoProcessingService

logger = logging.getLogger(__name__)

# Celery configuration
import ssl as _ssl

celery_app = Celery(
    "rag_processing",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["src.tasks.processing_tasks"],
)

_redis_tls = settings.REDIS_URL.startswith("rediss://")
_ssl_opts = {"ssl_cert_reqs": _ssl.CERT_NONE} if _redis_tls else None

celery_app.conf.update(
    **({"broker_use_ssl": _ssl_opts, "redis_backend_use_ssl": _ssl_opts} if _redis_tls else {}),
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


class ProcessingPipeline:
    """Main processing pipeline for multimodal documents"""

    def __init__(self, db: Session):
        # Import lazily to avoid circular import through src.services.documents.__init__
        from src.services.documents.file_service import FileService

        self.db = db
        self.file_service = FileService(db)
        self.entity_extractor = EntityExtractionService()
        self.image_processor = ImageProcessingService()
        self.audio_processor = AudioProcessingService()
        self.video_processor = VideoProcessingService()

    async def process_document(self, document_id: str, user_id: str) -> ProcessingJob:
        """Start processing for a document"""
        stmt = select(Document).where(
            Document.id == document_id, Document.is_deleted == False
        ).with_for_update()
        document = self.db.execute(stmt).scalar_one_or_none()

        if not document:
            raise ValueError(f"Document {document_id} not found")

        if document.processing_status not in [
            ProcessingStatus.PENDING,
            ProcessingStatus.FAILED,
        ]:
            raise ValueError(f"Document {document_id} is not in a processable state")

        if document.processing_status == ProcessingStatus.PROCESSING:
            raise ValueError(f"Document {document_id} is already being processed")

        # Create processing job
        job = ProcessingJob(
            job_type=JobType.DOCUMENT_INGESTION,
            priority=JobPriority.NORMAL,
            status=JobStatus.PENDING,
            document_id=document_id,
            organization_id=document.organization_id,
            created_by_user_id=user_id,
            parameters={
                "document_id": document_id,
                "document_type": document.document_type.value,
                "file_path": document.file_path,
            },
        )

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        # Queue the job
        self.queue_processing_job(job.id)

        return job

    def queue_processing_job(self, job_id: str):
        """Queue a processing job for execution"""
        job = self.db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()

        if not job:
            logger.error(f"Job {job_id} not found")
            return

        try:
            # Queue job based on type
            if job.job_type == JobType.DOCUMENT_INGESTION:
                task = celery_app.send_task(
                    "process_document_ingestion",
                    args=[job_id],
                    queue="document_processing",
                )
            elif job.job_type == JobType.TEXT_EXTRACTION:
                task = celery_app.send_task(
                    "extract_text_content", args=[job_id], queue="text_processing"
                )
            elif job.job_type == JobType.EMBEDDING_GENERATION:
                task = celery_app.send_task(
                    "generate_embeddings", args=[job_id], queue="vector_processing"
                )
            elif job.job_type == JobType.ENTITY_EXTRACTION:
                task = celery_app.send_task(
                    "extract_entities", args=[job_id], queue="entity_processing"
                )
            elif job.job_type == JobType.GRAPH_INDEXING:
                task = celery_app.send_task(
                    "index_in_graph", args=[job_id], queue="graph_processing"
                )
            else:
                logger.error(f"Unknown job type: {job.job_type}")
                return

            # Update job with task ID
            job.celery_task_id = task.id
            job.queue_job()
            self.db.commit()

            logger.info(f"Queued job {job_id} with task ID {task.id}")

        except Exception as e:
            logger.error(f"Failed to queue job {job_id}: {str(e)}")
            job.fail_job(f"Failed to queue job: {str(e)}")
            # Also fail the associated document so it doesn't stay PENDING forever
            if job.document_id:
                document = self.db.query(Document).filter(Document.id == job.document_id).first()
                if document:
                    document.processing_status = ProcessingStatus.FAILED
                    document.processing_error = f"Failed to queue: {str(e)}"
            self.db.commit()

    async def process_text_extraction(self, document: Document) -> Dict[str, Any]:
        """Extract text content from document"""
        from src.services.documents.storage_utils import local_file_for_document

        try:
            with local_file_for_document(document) as file_path:
                if document.document_type == DocumentType.TEXT:
                    text = self._extract_text_from_text_file(file_path)
                elif document.document_type == DocumentType.PDF:
                    text = self._extract_text_from_pdf(file_path)
                elif document.document_type == DocumentType.SPREADSHEET:
                    text = self._extract_text_from_spreadsheet(file_path)
                elif document.document_type == DocumentType.PRESENTATION:
                    text = self._extract_text_from_presentation(file_path)
                elif document.document_type == DocumentType.IMAGE:
                    text = await self._extract_text_from_image(document)
                elif document.document_type == DocumentType.AUDIO:
                    text = await self._extract_text_from_audio(document)
                elif document.document_type == DocumentType.VIDEO:
                    text = await self._extract_text_from_video(document)
                else:
                    text = ""

            # Generate summary using AI
            summary = await self._generate_text_summary(text) if text else ""

            # Assess text quality
            quality_assessment = (
                self._assess_text_quality(text)
                if text
                else {
                    "quality_score": 0.0,
                    "is_readable": False,
                    "language": "unknown",
                    "word_count": 0,
                    "sentence_count": 0,
                    "has_meaningful_content": False,
                }
            )

            return {
                "text_content": text,
                "summary": summary,
                "word_count": len(text.split()) if text else 0,
                "character_count": len(text) if text else 0,
                "quality_score": quality_assessment["quality_score"],
                "language": quality_assessment["language"],
                "is_readable": quality_assessment["is_readable"],
                "has_meaningful_content": quality_assessment["has_meaningful_content"],
            }

        except Exception as e:
            logger.error(f"Text extraction failed for document {document.id}: {str(e)}")
            raise

    def _extract_text_from_text_file(self, file_path: str) -> str:
        """Extract text from plain text file"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    return f.read()
            except (IOError, OSError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to read text file {file_path}: {e}")
                return ""

    def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file with OCR fallback"""
        try:
            import io

            import fitz  # PyMuPDF
            import pytesseract
            from PIL import Image

            # First attempt: Extract text directly
            text = []
            try:
                doc = fitz.open(file_path)
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    page_text = page.get_text()

                    if page_text.strip():
                        text.append(page_text)
                    else:
                        # If no text found, try OCR
                        pix = page.get_pixmap()
                        img_data = pix.tobytes("png")
                        img = Image.open(io.BytesIO(img_data))
                        ocr_text = pytesseract.image_to_string(img)
                        if ocr_text.strip():
                            text.append(f"[OCR Page {page_num + 1}]\n{ocr_text}")

                doc.close()

            except Exception as pdf_error:
                logger.warning(
                    f"Direct PDF extraction failed, trying OCR: {str(pdf_error)}"
                )
                # Fallback: Convert all pages to images and OCR them
                doc = fitz.open(file_path)
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    ocr_text = pytesseract.image_to_string(img)
                    if ocr_text.strip():
                        text.append(f"[OCR Page {page_num + 1}]\n{ocr_text}")
                doc.close()

            extracted_text = "\n".join(text)

            # Post-process and clean the text
            if extracted_text:
                extracted_text = self._clean_extracted_text(extracted_text)
                logger.info(
                    f"Successfully extracted {len(extracted_text)} characters from PDF"
                )

            return extracted_text

        except Exception as e:
            logger.error(f"PDF extraction failed completely: {str(e)}")
            return ""

    def _clean_extracted_text(self, text: str) -> str:
        """Clean and preprocess extracted text"""
        try:
            import re

            # Remove excessive whitespace
            text = re.sub(r"\s+", " ", text)

            # Remove common PDF artifacts
            text = re.sub(r"\f", "\n", text)  # Form feeds
            text = re.sub(
                r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text
            )  # Control characters

            # Fix common OCR errors
            text = re.sub(r"\|", "I", text)  # Vertical bars to I
            text = re.sub(r"1", "l", text)  # Sometimes 1 is misrecognized as l

            # Normalize line breaks
            text = re.sub(
                r"\n\s*\n", "\n\n", text
            )  # Multiple empty lines to double newline
            text = re.sub(r"\n{3,}", "\n\n", text)  # More than 2 newlines to 2

            # Strip leading/trailing whitespace
            text = text.strip()

            return text

        except Exception as e:
            logger.warning(f"Text cleaning failed: {str(e)}")
            return text

    def _assess_text_quality(self, text: str) -> Dict[str, Any]:
        """Assess the quality of extracted text"""
        try:
            import re

            if not text or len(text.strip()) < 10:
                return {
                    "quality_score": 0.0,
                    "word_count": 0,
                    "character_count": 0,
                    "has_meaningful_text": False,
                    "language": "unknown",
                    "language_detected": "unknown",
                    "is_readable": False,
                    "has_meaningful_content": False,
                    "sentence_count": 0,
                }

            # Basic metrics
            word_count = len(text.split())
            char_count = len(text)

            # Check for meaningful content (not just random characters)
            meaningful_words = 0
            common_words = [
                "the",
                "and",
                "or",
                "but",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "with",
                "by",
            ]
            words = text.lower().split()

            for word in words:
                if len(word) > 2 and word in common_words:
                    meaningful_words += 1

            # Simple language detection (character patterns)
            has_english_chars = bool(re.search(r"[a-zA-Z]", text))
            has_numbers = bool(re.search(r"\d", text))
            has_punctuation = bool(re.search(r"[.,!?;:]", text))

            # Calculate quality score
            quality_score = 0.0
            if word_count > 0:
                quality_score += 0.3  # Has words
            if meaningful_words > 0:
                quality_score += 0.3  # Has meaningful words
            if has_english_chars:
                quality_score += 0.2  # Has English characters
            if has_punctuation:
                quality_score += 0.1  # Has punctuation
            if has_numbers:
                quality_score += 0.1  # Has numbers

            # Detect if it's likely English
            language = (
                "english" if has_english_chars and meaningful_words > 0 else "unknown"
            )

            return {
                "quality_score": min(1.0, quality_score),
                "word_count": word_count,
                "character_count": char_count,
                "has_meaningful_text": meaningful_words > 0,
                "language": language,
                "language_detected": language,  # Keep for backward compatibility
                "is_readable": meaningful_words > 0,
                "has_meaningful_content": meaningful_words > 0,
                "sentence_count": len(text.split(".")) if text else 0,
            }

        except Exception as e:
            logger.warning(f"Text quality assessment failed: {str(e)}")
            return {
                "quality_score": 0.0,
                "word_count": 0,
                "character_count": 0,
                "has_meaningful_text": False,
                "language": "unknown",
                "language_detected": "unknown",
                "is_readable": False,
                "has_meaningful_content": False,
                "sentence_count": 0,
            }

    def _extract_text_from_spreadsheet(self, file_path: str) -> str:
        """Extract text from spreadsheet file"""
        try:
            import pandas as pd

            if file_path.endswith(".csv"):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            return df.to_string()
        except Exception as e:
            logger.error(f"Spreadsheet extraction failed: {str(e)}")
            return ""

    def _extract_text_from_presentation(self, file_path: str) -> str:
        """Extract text from presentation file"""
        try:
            from pptx import Presentation

            prs = Presentation(file_path)
            text = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        text.append(shape.text)
            return "\n".join(text)
        except Exception as e:
            logger.error(f"Presentation extraction failed: {str(e)}")
            return ""

    async def _extract_text_from_image(self, document: Document) -> str:
        """Extract text from image using enhanced image processing"""
        try:
            # Use the enhanced image processing service
            image_results = self.image_processor.process_image(document.file_path)

            # Store image analysis results in document metadata
            document.add_metadata("image_analysis", image_results["image_analysis"])
            document.add_metadata("color_analysis", image_results["color_analysis"])
            document.add_metadata("face_analysis", image_results["face_analysis"])
            document.add_metadata("image_quality", image_results["quality_score"])

            # Return extracted text for further processing
            return image_results["ocr_text"]

        except Exception as e:
            logger.error(
                f"Enhanced image processing failed for document {document.id}: {str(e)}"
            )
            return ""

    async def _extract_text_from_audio(self, document: Document) -> str:
        """Extract text from audio using enhanced speech recognition"""
        try:
            # Use the enhanced audio processing service
            audio_results = self.audio_processor.process_audio(document.file_path)

            # Store audio analysis results in document metadata
            document.add_metadata("audio_metadata", audio_results["metadata"])
            document.add_metadata("audio_quality", audio_results["quality_analysis"])
            document.add_metadata(
                "transcription_info",
                {
                    "language": audio_results["transcription"]["language"],
                    "confidence": audio_results["transcription"]["confidence"],
                    "word_count": audio_results["transcription"]["word_count"],
                },
            )

            # Return extracted text for further processing
            return audio_results["transcription"]["text"]

        except Exception as e:
            logger.error(
                f"Enhanced audio processing failed for document {document.id}: {str(e)}"
            )
            return ""

    async def _extract_text_from_video(self, document: Document) -> str:
        """Extract text from video using enhanced video processing"""
        try:
            # Use the enhanced video processing service
            video_results = self.video_processor.process_video(document.file_path)

            # Store video analysis results in document metadata
            document.add_metadata("video_metadata", video_results["metadata"])
            document.add_metadata("video_quality", video_results["quality_analysis"])
            document.add_metadata("video_content", video_results["content_analysis"])

            # Store audio transcription results if available
            if video_results.get("audio_transcription"):
                transcription = video_results["audio_transcription"]
                document.add_metadata(
                    "audio_transcription",
                    {
                        "text": transcription.get("text", ""),
                        "language": transcription.get("language", "unknown"),
                        "confidence": transcription.get("confidence", 0.0),
                        "word_count": transcription.get("word_count", 0),
                    },
                )

            # Store keyframe information if available
            if video_results.get("keyframes"):
                document.add_metadata(
                    "video_keyframes",
                    {
                        "count": len(video_results["keyframes"]),
                        "analysis": video_results["keyframes"],
                    },
                )

            # Return extracted audio text for further processing
            if video_results.get("audio_transcription", {}).get("text"):
                return video_results["audio_transcription"]["text"]

            return ""

        except Exception as e:
            logger.error(
                f"Enhanced video processing failed for document {document.id}: {str(e)}"
            )
            return ""

    async def _generate_text_summary(self, text: str) -> str:
        """Generate summary of text using AI"""
        try:
            # This would integrate with OpenAI or another LLM
            # For now, return a simple summary
            if len(text) < 100:
                return text

            # Simple extractive summary (first few sentences)
            sentences = text.split(".")
            summary_sentences = sentences[:3]  # First 3 sentences
            return ". ".join(summary_sentences).strip() + "."

        except Exception as e:
            logger.error(f"Summary generation failed: {str(e)}")
            return ""

    async def process_entity_extraction(
        self, document: Document, text: str
    ) -> List[Entity]:
        """Extract entities from text using enhanced entity extraction service"""
        try:
            # Use the enhanced entity extraction service
            entities = self.entity_extractor.extract_entities_from_text(document, text)

            # Get statistics about extracted entities
            stats = self.entity_extractor.get_entity_statistics(entities)
            logger.info(f"Entity extraction stats for document {document.id}: {stats}")

            return entities

        except Exception as e:
            logger.error(
                f"Entity extraction failed for document {document.id}: {str(e)}"
            )
            return []

    async def process_embedding_generation(self, document: Document, text: str) -> str:
        """Generate embeddings for document text using Azure OpenAI"""
        try:
            from datetime import datetime

            import numpy as np

            from src.models.vector import (
                VectorCollectionType,
                VectorEntry,
                VectorMetadata,
            )
            from src.services.infrastructure.azure_openai_service import (
                azure_openai_service,
            )
            from src.services.search.vector_service import vector_service

            # Check if Azure OpenAI embedding service is available
            if not azure_openai_service.is_embedding_available():
                logger.error("Azure OpenAI embedding service is not available")
                return None

            # Split text into chunks (Azure OpenAI has token limits)
            # Split text into chunks (Azure OpenAI has token limits)
            chunk_size = 8000  # characters (roughly ~2000 tokens)
            overlap = 1600  # 20% overlap

            chunks = []
            if len(text) <= chunk_size:
                chunks = [text]
            else:
                stride = chunk_size - overlap
                for i in range(0, len(text), stride):
                    chunk = text[i : i + chunk_size]
                    if chunk.strip():
                        chunks.append(chunk)

            # Generate embeddings for each chunk using Azure OpenAI
            embeddings = []
            chunk_texts = []
            for chunk in chunks:
                if chunk.strip():
                    try:
                        # Get embedding from Azure OpenAI
                        chunk_embeddings = await azure_openai_service.get_embeddings(
                            [chunk]
                        )
                        if chunk_embeddings and len(chunk_embeddings) > 0:
                            embeddings.append(chunk_embeddings[0])
                            chunk_texts.append(chunk)
                    except Exception as e:
                        logger.error(f"Failed to get embedding for chunk: {str(e)}")
                        continue

            if embeddings:
                # Average embeddings to create document-level embedding
                final_embedding = np.mean(embeddings, axis=0)
                embedding_id = str(uuid.uuid4())

                # Create metadata for the vector
                metadata = VectorMetadata(
                    document_id=str(document.id),
                    organization_id=str(document.organization_id),
                    content_type=document.document_type.value,
                    source_type="document",
                    timestamp=datetime.utcnow(),
                )

                # Create vector entry
                vector_entry = VectorEntry(
                    id=embedding_id,
                    vector=final_embedding.tolist(),
                    text=text[:1000],  # Store first 1000 chars as preview
                    metadata=metadata,
                )

                # Store in Qdrant
                result = vector_service.insert_vectors(
                    collection_type=VectorCollectionType.DOCUMENTS,
                    vectors=[vector_entry],
                )

                if result.success:
                    logger.info(
                        f"Successfully stored embedding for document {document.id} in Qdrant using Azure OpenAI"
                    )
                    return embedding_id
                else:
                    logger.error(f"Failed to store embedding in Qdrant: {result.error}")
                    return None

            logger.warning(f"No embeddings generated for document {document.id}")
            return None

        except Exception as e:
            logger.error(
                f"Embedding generation failed for document {document.id}: {str(e)}"
            )
            return None

    def get_processing_status(self, document_id: str) -> Dict[str, Any]:
        """Get processing status for a document"""
        document = self.db.query(Document).filter(Document.id == document_id).first()

        if not document:
            return {"error": "Document not found"}

        # Get processing jobs
        jobs = (
            self.db.query(ProcessingJob)
            .filter(ProcessingJob.document_id == document_id)
            .order_by(ProcessingJob.created_at.desc())
            .all()
        )

        return {
            "document_id": document_id,
            "processing_status": document.processing_status.value,
            "is_embedded": document.is_embedded,
            "is_indexed": document.is_indexed,
            "processing_error": document.processing_error,
            "jobs": [job.to_dict() for job in jobs],
        }

    def retry_failed_jobs(self, organization_id: str = None) -> int:
        """Retry failed processing jobs"""
        query = self.db.query(ProcessingJob).filter(
            ProcessingJob.status == JobStatus.FAILED,
            ProcessingJob.retry_count < ProcessingJob.max_retries,
        )

        if organization_id:
            query = query.filter(ProcessingJob.organization_id == organization_id)

        failed_jobs = query.all()
        retried_count = 0

        for job in failed_jobs:
            if job.can_retry:
                job.retry_job()
                self.db.commit()
                self.queue_processing_job(job.id)
                retried_count += 1

        return retried_count


def get_processing_service(db: Session = Depends(get_db)) -> ProcessingPipeline:
    """Get processing service instance"""
    return ProcessingPipeline(db)
