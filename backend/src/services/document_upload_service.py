"""
Document Upload Service
Handles document upload, processing, and knowledge graph integration
"""

import os
import uuid
import hashlib
import asyncio
from typing import List, Optional, Dict, Any, BinaryIO
from datetime import datetime
from pathlib import Path
import logging

from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException
from minio import Minio
from minio.error import S3Error

from src.core.config import settings
from src.models.document import Document
from src.models.processing import ProcessingJob, JobType, JobStatus, JobPriority
from src.models.user import User
from src.services.knowledge_graph_service import KnowledgeGraphService
from src.services.processing_service import ProcessingService
from src.utils.file_utils import validate_file_type, get_file_metadata

logger = logging.getLogger(__name__)

class DocumentUploadService:
    """Service for handling document uploads and processing"""

    def __init__(self, db: Session):
        self.db = db
        self.minio_client = self._init_minio_client()
        self.knowledge_graph_service = KnowledgeGraphService(db)
        self.processing_service = ProcessingService(db)

    def _init_minio_client(self) -> Minio:
        """Initialize MinIO client for file storage"""
        try:
            return Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise

    async def upload_document(
        self,
        file: UploadFile,
        title: str,
        user: User,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None
    ) -> Document:
        """
        Upload a document and start processing
        """
        try:
            # Validate file
            validation_result = await self._validate_file(file)
            if not validation_result["is_valid"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"File validation failed: {validation_result['error']}"
                )

            # Read file content
            file_content = await file.read()

            # Calculate checksums
            md5_hash = hashlib.md5(file_content).hexdigest()
            sha256_hash = hashlib.sha256(file_content).hexdigest()

            # Generate file path
            file_path = self._generate_file_path(file.filename, user.id)

            # Upload to MinIO
            await self._upload_to_storage(file_content, file_path, file.content_type)

            # Create document record
            document = Document(
                title=title,
                filename=file.filename,
                original_filename=file.filename,
                file_type=validation_result["file_type"],
                file_size_bytes=len(file_content),
                mime_type=file.content_type,
                file_path=file_path,
                checksum_md5=md5_hash,
                checksum_sha256=sha256_hash,
                uploaded_by=user.id,
                description=description,
                tags=tags or [],
                metadata=custom_metadata or {},
                status="uploaded"
            )

            self.db.add(document)
            self.db.commit()
            self.db.refresh(document)

            # Start processing pipeline
            await self._start_processing_pipeline(document)

            logger.info(f"Document uploaded successfully: {document.id}")
            return document

        except Exception as e:
            logger.error(f"Document upload failed: {e}")
            self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    async def _validate_file(self, file: UploadFile) -> Dict[str, Any]:
        """Validate uploaded file"""
        try:
            # Check file size
            if file.size and file.size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                return {
                    "is_valid": False,
                    "error": f"File size exceeds {settings.MAX_FILE_SIZE_MB}MB limit"
                }

            # Check file type
            allowed_types = {
                "application/pdf": "pdf",
                "text/plain": "txt",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
                "image/jpeg": "jpg",
                "image/png": "png",
                "audio/mpeg": "mp3",
                "audio/wav": "wav",
                "video/mp4": "mp4",
                "video/quicktime": "mov"
            }

            file_type = allowed_types.get(file.content_type)
            if not file_type:
                return {
                    "is_valid": False,
                    "error": f"Unsupported file type: {file.content_type}"
                }

            return {
                "is_valid": True,
                "file_type": file_type,
                "validation_details": f"Valid {file_type} file"
            }

        except Exception as e:
            return {
                "is_valid": False,
                "error": f"Validation error: {str(e)}"
            }

    def _generate_file_path(self, filename: str, user_id: str) -> str:
        """Generate unique file path for storage"""
        file_ext = Path(filename).suffix
        unique_id = str(uuid.uuid4())
        date_path = datetime.now().strftime("%Y/%m/%d")
        return f"documents/{user_id}/{date_path}/{unique_id}{file_ext}"

    async def _upload_to_storage(
        self,
        file_content: bytes,
        file_path: str,
        content_type: str
    ) -> None:
        """Upload file to MinIO storage"""
        try:
            # Ensure bucket exists
            bucket_name = settings.MINIO_BUCKET_NAME
            if not self.minio_client.bucket_exists(bucket_name):
                self.minio_client.make_bucket(bucket_name)

            # Upload file
            from io import BytesIO
            self.minio_client.put_object(
                bucket_name,
                file_path,
                BytesIO(file_content),
                length=len(file_content),
                content_type=content_type
            )

            logger.info(f"File uploaded to storage: {file_path}")

        except S3Error as e:
            logger.error(f"MinIO upload failed: {e}")
            raise HTTPException(status_code=500, detail="File storage failed")

    async def _start_processing_pipeline(self, document: Document) -> None:
        """Start the document processing pipeline"""
        try:
            # Create processing jobs
            jobs = []

            # Text extraction job
            if document.file_type in ["pdf", "txt", "docx"]:
                text_job = ProcessingJob(
                    document_id=document.id,
                    job_type=JobType.TEXT_EXTRACTION,
                    status=JobStatus.PENDING,
                    priority=JobPriority.NORMAL,
                    parameters={"file_path": document.file_path}
                )
                jobs.append(text_job)

            # Entity extraction job
            entity_job = ProcessingJob(
                document_id=document.id,
                job_type=JobType.ENTITY_EXTRACTION,
                status=JobStatus.PENDING,
                priority=JobPriority.NORMAL,
                parameters={"document_id": str(document.id)}
            )
            jobs.append(entity_job)

            # Knowledge graph population job
            graph_job = ProcessingJob(
                document_id=document.id,
                job_type=JobType.KNOWLEDGE_GRAPH_POPULATION,
                status=JobStatus.PENDING,
                priority=JobPriority.NORMAL,
                parameters={"document_id": str(document.id)}
            )
            jobs.append(graph_job)

            # Vector indexing job
            vector_job = ProcessingJob(
                document_id=document.id,
                job_type=JobType.VECTOR_INDEXING,
                status=JobStatus.PENDING,
                priority=JobPriority.NORMAL,
                parameters={"document_id": str(document.id)}
            )
            jobs.append(vector_job)

            # Save jobs to database
            for job in jobs:
                self.db.add(job)

            self.db.commit()

            # Start processing (in background)
            asyncio.create_task(self._process_jobs(jobs))

            logger.info(f"Processing pipeline started for document: {document.id}")

        except Exception as e:
            logger.error(f"Failed to start processing pipeline: {e}")
            raise

    async def _process_jobs(self, jobs: List[ProcessingJob]) -> None:
        """Process jobs in sequence"""
        for job in jobs:
            try:
                # Update job status to running
                job.status = JobStatus.RUNNING
                job.started_at = datetime.utcnow()
                self.db.commit()

                # Process based on job type
                if job.job_type == JobType.TEXT_EXTRACTION:
                    await self._process_text_extraction(job)
                elif job.job_type == JobType.ENTITY_EXTRACTION:
                    await self._process_entity_extraction(job)
                elif job.job_type == JobType.KNOWLEDGE_GRAPH_POPULATION:
                    await self._process_knowledge_graph_population(job)
                elif job.job_type == JobType.VECTOR_INDEXING:
                    await self._process_vector_indexing(job)

                # Mark job as completed
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                job.progress_percentage = 100.0
                self.db.commit()

                logger.info(f"Job completed: {job.id} ({job.job_type})")

            except Exception as e:
                # Mark job as failed
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                self.db.commit()

                logger.error(f"Job failed: {job.id} ({job.job_type}): {e}")

    async def _process_text_extraction(self, job: ProcessingJob) -> None:
        """Process text extraction job"""
        try:
            # Get document
            document = self.db.query(Document).filter(
                Document.id == job.document_id
            ).first()

            if not document:
                raise ValueError("Document not found")

            # Extract text based on file type
            if document.file_type == "pdf":
                text = await self._extract_pdf_text(document)
            elif document.file_type == "txt":
                text = await self._extract_txt_text(document)
            elif document.file_type == "docx":
                text = await self._extract_docx_text(document)
            else:
                raise ValueError(f"Unsupported file type for text extraction: {document.file_type}")

            # Update document with extracted text
            document.metadata = document.metadata or {}
            document.metadata["extracted_text"] = text
            document.metadata["text_length"] = len(text)

            # Update job progress
            job.progress_percentage = 100.0
            job.result_data = {
                "text_length": len(text),
                "extraction_method": f"{document.file_type}_extractor"
            }

            self.db.commit()

        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            raise

    async def _process_entity_extraction(self, job: ProcessingJob) -> None:
        """Process entity extraction job"""
        try:
            # Get document
            document = self.db.query(Document).filter(
                Document.id == job.document_id
            ).first()

            if not document:
                raise ValueError("Document not found")

            # Get extracted text
            text = document.metadata.get("extracted_text", "")
            if not text:
                raise ValueError("No text available for entity extraction")

            # Extract entities (placeholder - would use NLP service)
            entities = await self._extract_entities(text, document.id)

            # Update job result
            job.progress_percentage = 100.0
            job.result_data = {
                "entities_extracted": len(entities),
                "extraction_method": "nlp_service"
            }

            self.db.commit()

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            raise

    async def _process_knowledge_graph_population(self, job: ProcessingJob) -> None:
        """Process knowledge graph population job"""
        try:
            # Get document and extracted entities
            document = self.db.query(Document).filter(
                Document.id == job.document_id
            ).first()

            if not document:
                raise ValueError("Document not found")

            # Populate knowledge graph
            entities_added = await self.knowledge_graph_service.populate_from_document(document)

            # Update job result
            job.progress_percentage = 100.0
            job.result_data = {
                "entities_added_to_graph": entities_added,
                "graph_nodes_created": entities_added
            }

            self.db.commit()

        except Exception as e:
            logger.error(f"Knowledge graph population failed: {e}")
            raise

    async def _process_vector_indexing(self, job: ProcessingJob) -> None:
        """Process vector indexing job"""
        try:
            # Get document
            document = self.db.query(Document).filter(
                Document.id == job.document_id
            ).first()

            if not document:
                raise ValueError("Document not found")

            # Get text for embedding
            text = document.metadata.get("extracted_text", "")
            if not text:
                raise ValueError("No text available for vector indexing")

            # Create embeddings (placeholder)
            embedding_id = await self._create_embeddings(text, document.id)

            # Update job result
            job.progress_percentage = 100.0
            job.result_data = {
                "embedding_id": embedding_id,
                "vector_dimension": 1536,  # Placeholder
                "indexed_chunks": 1
            }

            self.db.commit()

        except Exception as e:
            logger.error(f"Vector indexing failed: {e}")
            raise

    # Placeholder methods for actual implementations
    async def _extract_pdf_text(self, document: Document) -> str:
        """Extract text from PDF file"""
        # Placeholder: Use PyPDF2 or similar
        return f"Extracted text from {document.filename}"

    async def _extract_txt_text(self, document: Document) -> str:
        """Extract text from TXT file"""
        # Placeholder: Read from MinIO storage
        return f"Text content from {document.filename}"

    async def _extract_docx_text(self, document: Document) -> str:
        """Extract text from DOCX file"""
        # Placeholder: Use python-docx
        return f"Extracted text from {document.filename}"

    async def _extract_entities(self, text: str, document_id: str) -> List[Dict[str, Any]]:
        """Extract entities from text"""
        # Placeholder: Use spaCy or similar NLP service
        return [
            {"text": "Entity1", "type": "PERSON", "confidence": 0.9},
            {"text": "Entity2", "type": "ORGANIZATION", "confidence": 0.85}
        ]

    async def _create_embeddings(self, text: str, document_id: str) -> str:
        """Create vector embeddings for text"""
        # Placeholder: Use OpenAI embeddings or similar
        return f"embedding_{document_id}"

    async def get_document_status(self, document_id: str) -> Dict[str, Any]:
        """Get comprehensive document processing status"""
        try:
            # Get document
            document = self.db.query(Document).filter(
                Document.id == document_id
            ).first()

            if not document:
                raise ValueError("Document not found")

            # Get processing jobs
            jobs = self.db.query(ProcessingJob).filter(
                ProcessingJob.document_id == document_id
            ).all()

            # Calculate overall status
            total_jobs = len(jobs)
            completed_jobs = len([j for j in jobs if j.status == JobStatus.COMPLETED])
            failed_jobs = len([j for j in jobs if j.status == JobStatus.FAILED])
            running_jobs = len([j for j in jobs if j.status == JobStatus.RUNNING])

            overall_progress = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0

            if running_jobs > 0:
                overall_status = "processing"
            elif failed_jobs > 0:
                overall_status = "has_failures"
            elif completed_jobs == total_jobs:
                overall_status = "completed"
            else:
                overall_status = "pending"

            return {
                "document_id": document_id,
                "status": overall_status,
                "progress_percentage": overall_progress,
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "running_jobs": running_jobs,
                "jobs": [
                    {
                        "id": str(job.id),
                        "job_type": job.job_type.value,
                        "status": job.status.value,
                        "progress_percentage": float(job.progress_percentage),
                        "started_at": job.started_at.isoformat() if job.started_at else None,
                        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                        "error_message": job.error_message,
                        "result_data": job.result_data
                    }
                    for job in jobs
                ]
            }

        except Exception as e:
            logger.error(f"Failed to get document status: {e}")
            raise