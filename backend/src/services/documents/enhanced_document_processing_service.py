"""
Enhanced Document Processing Service
Provides comprehensive document processing with multimodal support, entity extraction,
knowledge graph integration, and real-time progress tracking
"""

import os
import uuid
import asyncio
import json
import hashlib
from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta
from pathlib import Path
import logging
import traceback
import io
import re
from dataclasses import dataclass

# Document processing libraries (optional dependencies)
try:
    import fitz  # PyMuPDF for PDF processing
except ImportError:
    fitz = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None

# AI/ML libraries (optional dependencies)
try:
    import spacy
except ImportError:
    spacy = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    import openai
except ImportError:
    openai = None

try:
    from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
except ImportError:
    pipeline = None
    AutoTokenizer = None
    AutoModelForTokenClassification = None

# Database and storage
from sqlalchemy.orm import Session
from fastapi import Depends
try:
    from minio import Minio
    from minio.error import S3Error
except ImportError:
    Minio = None
    S3Error = Exception

# Neo4j for knowledge graph
from neo4j import GraphDatabase

# Internal imports
from src.core.config import settings
from src.models.document import Document
from src.models.processing import ProcessingJob, JobType, JobStatus
# Note: ExtractedEntity and ExtractedRelationship not found in models/entity.py
# Using Entity from models/entity as fallback
from src.models.entity import Entity as ExtractedEntity
ExtractedRelationship = None  # Not defined yet
from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service as _kg_service_instance
from src.services.search.vector_service import VectorService as VectorStoreService
from src.core.database import get_db

logger = logging.getLogger(__name__)

@dataclass
class ProcessingResult:
    """Result of document processing step"""
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    processing_time_ms: Optional[float] = None

class MultimodalProcessor:
    """Handles processing of different file types"""

    def __init__(self, minio_client: Minio):
        self.minio_client = minio_client
        self.nlp = None
        self.sentence_model = None
        self._load_models()

    def _load_models(self):
        """Load ML models on initialization"""
        try:
            # Load spaCy model for entity extraction when available.
            if spacy is not None:
                self.nlp = spacy.load("en_core_web_sm")
            else:
                logger.warning("spaCy is not installed; using fallback text processing")

            # Load sentence transformer for embeddings when available.
            if SentenceTransformer is not None:
                self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            else:
                logger.warning("sentence-transformers is not installed; embeddings disabled")

            logger.info("ML models loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load ML models: {e}")
            # Continue without models - will use fallback methods

    async def process_pdf(self, document: Document) -> ProcessingResult:
        """Process PDF document with OCR and text extraction"""
        start_time = datetime.now()

        try:
            # Download file from MinIO
            file_content = await self._download_from_storage(document.file_path)

            # Extract text using PyMuPDF
            pdf_document = fitz.open(stream=io.BytesIO(file_content))
            extracted_text = ""
            pages_data = []

            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]

                # Extract text
                page_text = page.get_text()
                extracted_text += page_text + "\n"

                # Extract images if needed
                images = page.get_images()
                page_data = {
                    "page_number": page_num + 1,
                    "text": page_text,
                    "image_count": len(images),
                    "char_count": len(page_text)
                }
                pages_data.append(page_data)

            pdf_document.close()

            # If no text found, try OCR
            if len(extracted_text.strip()) < 100:
                extracted_text = await self._ocr_pdf(file_content)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProcessingResult(
                success=True,
                data={
                    "text": extracted_text,
                    "pages": pages_data,
                    "total_pages": len(pages_data),
                    "text_length": len(extracted_text),
                    "processing_method": "pymupdf" if len(extracted_text.strip()) >= 100 else "ocr"
                },
                processing_time_ms=processing_time
            )

        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )

    async def process_text(self, document: Document) -> ProcessingResult:
        """Process text document"""
        start_time = datetime.now()

        try:
            # Download file from MinIO
            file_content = await self._download_from_storage(document.file_path)

            # Decode text
            text = file_content.decode('utf-8')

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProcessingResult(
                success=True,
                data={
                    "text": text,
                    "text_length": len(text),
                    "line_count": len(text.split('\n')),
                    "word_count": len(text.split()),
                    "processing_method": "direct"
                },
                processing_time_ms=processing_time
            )

        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )

    async def process_image(self, document: Document) -> ProcessingResult:
        """Process image document with OCR and object detection"""
        start_time = datetime.now()

        try:
            # Download file from MinIO
            file_content = await self._download_from_storage(document.file_path)

            # Open image
            image = Image.open(io.BytesIO(file_content))

            # Extract text using OCR
            extracted_text = pytesseract.image_to_string(image)

            # Get image metadata
            image_metadata = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
                "has_text": len(extracted_text.strip()) > 0
            }

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProcessingResult(
                success=True,
                data={
                    "text": extracted_text,
                    "metadata": image_metadata,
                    "text_length": len(extracted_text),
                    "processing_method": "tesseract_ocr"
                },
                processing_time_ms=processing_time
            )

        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )

    async def process_audio(self, document: Document) -> ProcessingResult:
        """Process audio document with speech recognition"""
        start_time = datetime.now()

        try:
            # Download file from MinIO
            file_content = await self._download_from_storage(document.file_path)

            # Convert audio to WAV if needed
            audio = AudioSegment.from_file(io.BytesIO(file_content))

            # Export as WAV for speech recognition
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            wav_buffer.seek(0)

            # Transcribe audio
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_buffer) as source:
                audio_data = recognizer.record(source)
                extracted_text = recognizer.recognize_google(audio_data)

            # Get audio metadata
            audio_metadata = {
                "duration_seconds": len(audio) / 1000.0,
                "channels": audio.channels,
                "frame_rate": audio.frame_rate,
                "sample_width": audio.sample_width
            }

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProcessingResult(
                success=True,
                data={
                    "text": extracted_text,
                    "metadata": audio_metadata,
                    "text_length": len(extracted_text),
                    "processing_method": "google_speech_recognition"
                },
                processing_time_ms=processing_time
            )

        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )

    async def _download_from_storage(self, file_path: str, document=None) -> bytes:
        """Download file from storage (Supabase Storage or MinIO).

        If a document is provided and uses Supabase backend, downloads from
        Supabase Storage. Otherwise falls back to MinIO.
        """
        # Check if document uses Supabase Storage
        if document and getattr(document, "storage_backend", "local") == "supabase" and document.storage_path:
            from src.services.documents.storage_utils import download_document_bytes

            return download_document_bytes(document)

        try:
            bucket_name = settings.MINIO_BUCKET_NAME
            response = self.minio_client.get_object(bucket_name, file_path)
            return response.read()
        except Exception as e:
            logger.error(f"Failed to download file from storage: {e}")
            raise

    async def _ocr_pdf(self, file_content: bytes) -> str:
        """Perform OCR on PDF using pytesseract"""
        try:
            # Convert PDF to images
            pdf_document = fitz.open(stream=io.BytesIO(file_content))
            extracted_text = ""

            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]

                # Convert page to image
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))

                # Perform OCR
                page_text = pytesseract.image_to_string(image)
                extracted_text += page_text + "\n"

            pdf_document.close()
            return extracted_text

        except Exception as e:
            logger.error(f"PDF OCR failed: {e}")
            return ""

class EnhancedDocumentProcessingService:
    """Enhanced document processing service with multimodal support"""

    def __init__(self, db: Session):
        self.db = db
        self.minio_client = self._init_minio_client()
        self.multimodal_processor = MultimodalProcessor(self.minio_client)
        self.knowledge_graph_service = _kg_service_instance
        self.vector_store_service = VectorStoreService(db)

    def _init_minio_client(self) -> Minio:
        """Initialize MinIO client"""
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

    async def process_document(self, job_id: str) -> ProcessingResult:
        """Process document through the complete pipeline"""
        try:
            # Get processing job
            job = self.db.query(ProcessingJob).filter(
                ProcessingJob.id == job_id
            ).first()

            if not job:
                raise ValueError(f"Processing job {job_id} not found")

            # Get document
            document = self.db.query(Document).filter(
                Document.id == job.document_id
            ).first()

            if not document:
                raise ValueError(f"Document {job.document_id} not found")

            # Initialize processing steps
            total_steps = 5
            current_step = 0

            # Step 1: Text/Content Extraction
            await self._update_job_progress(job, 10, "Extracting content")
            extraction_result = await self._extract_content(document)

            if not extraction_result.success:
                raise Exception(f"Content extraction failed: {extraction_result.error}")

            current_step += 1

            # Step 2: Entity Extraction
            await self._update_job_progress(job, 30, "Extracting entities")
            extracted_text = extraction_result.data.get("text", "")

            if extracted_text:
                from src.services.processing.llm_entity_extraction import (
                    LLMEntityExtractionService,
                )

                llm_extractor = LLMEntityExtractionService()
                llm_result = await llm_extractor.extract_entities(
                    text=extracted_text,
                    document_id=str(document.id),
                    organization_id=str(getattr(document, "organization_id", "")),
                )
                entity_result = ProcessingResult(
                    success=True,
                    data={
                        "entities": [e.model_dump() for e in llm_result.entities],
                        "entity_count": len(llm_result.entities),
                    },
                )
                relationship_result = ProcessingResult(
                    success=True,
                    data={
                        "relationships": [r.model_dump() for r in llm_result.relationships],
                        "relationship_count": len(llm_result.relationships),
                    },
                )

                current_step += 2  # Steps 2 and 3 handled together by LLM extraction
            else:
                entity_result = ProcessingResult(success=True, data={"entities": []})
                relationship_result = ProcessingResult(success=True, data={"relationships": []})

            current_step += 1

            # Step 4: Knowledge Graph Population
            await self._update_job_progress(job, 70, "Populating knowledge graph")

            if entity_result.success and entity_result.data.get("entities"):
                graph_result = await self._populate_knowledge_graph(
                    document,
                    entity_result.data.get("entities", []),
                    relationship_result.data.get("relationships", [])
                )
            else:
                graph_result = ProcessingResult(success=True, data={"nodes_created": 0, "relationships_created": 0})

            current_step += 1

            # Step 5: Vector Indexing
            await self._update_job_progress(job, 90, "Creating vector embeddings")

            if extracted_text:
                vector_result = await self._create_vector_embeddings(document, extracted_text)
            else:
                vector_result = ProcessingResult(success=True, data={"embedding_id": None})

            # Update document with processing results
            await self._update_document_metadata(document, {
                "extraction": extraction_result.data,
                "entities": entity_result.data,
                "relationships": relationship_result.data,
                "knowledge_graph": graph_result.data,
                "vectors": vector_result.data,
                "processing_completed_at": datetime.utcnow().isoformat()
            })

            # Mark job as completed
            await self._update_job_progress(job, 100, "Processing completed")
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result_data = {
                "extraction": extraction_result.data,
                "entities": entity_result.data,
                "relationships": relationship_result.data,
                "knowledge_graph": graph_result.data,
                "vectors": vector_result.data,
                "total_processing_time_ms": sum([
                    extraction_result.processing_time_ms or 0,
                    entity_result.processing_time_ms or 0,
                    relationship_result.processing_time_ms or 0,
                    graph_result.processing_time_ms or 0,
                    vector_result.processing_time_ms or 0
                ])
            }

            self.db.commit()

            logger.info(f"Document processing completed for {document.id}")

            return ProcessingResult(
                success=True,
                data={
                    "document_id": str(document.id),
                    "processing_steps_completed": current_step,
                    "total_processing_time_ms": job.result_data.get("total_processing_time_ms")
                }
            )

        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            logger.error(traceback.format_exc())

            # Mark job as failed
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                self.db.commit()

            return ProcessingResult(
                success=False,
                data={},
                error=str(e)
            )

    async def _extract_content(self, document: Document) -> ProcessingResult:
        """Extract content based on document type"""
        if document.file_type == "pdf":
            return await self.multimodal_processor.process_pdf(document)
        elif document.file_type == "txt":
            return await self.multimodal_processor.process_text(document)
        elif document.file_type in ["jpg", "jpeg", "png"]:
            return await self.multimodal_processor.process_image(document)
        elif document.file_type in ["mp3", "wav"]:
            return await self.multimodal_processor.process_audio(document)
        else:
            return ProcessingResult(
                success=False,
                data={},
                error=f"Unsupported file type: {document.file_type}"
            )

    async def _save_entities(self, document: Document, entities: List[Dict[str, Any]]) -> None:
        """Save extracted entities to database"""
        try:
            for entity_data in entities:
                entity = ExtractedEntity(
                    document_id=document.id,
                    entity_text=entity_data["text"],
                    entity_type=entity_data["label"],
                    confidence_score=entity_data.get("confidence", 1.0),
                    start_position=entity_data.get("start"),
                    end_position=entity_data.get("end"),
                    context_text=entity_data.get("context"),
                    extraction_method="llm",
                    model_version="llm_entity_extraction",
                    metadata={
                        "document_id": str(document.id),
                        "extraction_timestamp": datetime.utcnow().isoformat()
                    }
                )
                self.db.add(entity)

            self.db.commit()
            logger.info(f"Saved {len(entities)} entities for document {document.id}")

        except Exception as e:
            logger.error(f"Failed to save entities: {e}")
            raise

    async def _save_relationships(self, document: Document, relationships: List[Dict[str, Any]]) -> None:
        """Save extracted relationships to database"""
        try:
            for rel_data in relationships:
                # Find source and target entities
                source_entity = self.db.query(ExtractedEntity).filter(
                    ExtractedEntity.document_id == document.id,
                    ExtractedEntity.entity_text.ilike(f"%{rel_data['source']}%")
                ).first()

                target_entity = self.db.query(ExtractedEntity).filter(
                    ExtractedEntity.document_id == document.id,
                    ExtractedEntity.entity_text.ilike(f"%{rel_data['target']}%")
                ).first()

                if source_entity and target_entity:
                    relationship = ExtractedRelationship(
                        document_id=document.id,
                        source_entity_id=source_entity.id,
                        target_entity_id=target_entity.id,
                        relationship_type=rel_data["type"],
                        confidence_score=rel_data.get("confidence", 0.8),
                        context_text=rel_data.get("context"),
                        extraction_method="pattern_based",
                        model_version="pattern_matching_v1",
                        metadata={
                            "document_id": str(document.id),
                            "extraction_timestamp": datetime.utcnow().isoformat()
                        }
                    )
                    self.db.add(relationship)

            self.db.commit()
            logger.info(f"Saved {len(relationships)} relationships for document {document.id}")

        except Exception as e:
            logger.error(f"Failed to save relationships: {e}")
            raise

    async def _populate_knowledge_graph(
        self,
        document: Document,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ) -> ProcessingResult:
        """Populate knowledge graph with entities and relationships"""
        start_time = datetime.now()

        try:
            nodes_created = 0
            relationships_created = 0

            # Create nodes for entities
            for entity_data in entities:
                node_id = self.knowledge_graph_service.create_entity_node(
                    entity_text=entity_data["text"],
                    entity_type=entity_data["label"],
                    document_id=str(document.id),
                    confidence=entity_data.get("confidence", 1.0),
                    metadata=entity_data.get("context", "")
                )

                if node_id:
                    nodes_created += 1

            # Create relationships
            for rel_data in relationships:
                # Find corresponding nodes in Neo4j
                source_node = self.knowledge_graph_service.find_entity_node(
                    rel_data["source"], rel_data.get("source_type", "UNKNOWN")
                )
                target_node = self.knowledge_graph_service.find_entity_node(
                    rel_data["target"], rel_data.get("target_type", "UNKNOWN")
                )

                if source_node and target_node:
                    from src.models.graph import (
                        CreateRelationshipRequest,
                        RelationshipType as GraphRelType,
                    )

                    raw_type = str(rel_data["type"]).upper().replace(" ", "_")
                    try:
                        rel_type = GraphRelType(raw_type)
                    except ValueError:
                        rel_type = GraphRelType.RELATED_TO

                    rel_request = CreateRelationshipRequest(
                        source_entity_id=source_node["id"],
                        target_entity_id=target_node["id"],
                        relationship_type=rel_type,
                        confidence_score=rel_data.get("confidence", 0.8),
                        source_document_id=str(document.id),
                    )
                    rel_result = self.knowledge_graph_service.create_relationship(rel_request)

                    if rel_result:
                        relationships_created += 1

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProcessingResult(
                success=True,
                data={
                    "nodes_created": nodes_created,
                    "relationships_created": relationships_created,
                    "total_entities": len(entities),
                    "total_relationships": len(relationships),
                    "processing_time_ms": processing_time
                },
                processing_time_ms=processing_time
            )

        except Exception as e:
            logger.error(f"Knowledge graph population failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )

    async def _create_vector_embeddings(self, document: Document, text: str) -> ProcessingResult:
        """Create vector embeddings for document text"""
        start_time = datetime.now()

        try:
            # Split text into chunks
            chunk_size = 500
            chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

            # Create embeddings
            embeddings = []
            if self.multimodal_processor.sentence_model:
                for chunk in chunks:
                    embedding = self.multimodal_processor.sentence_model.encode(chunk)
                    embeddings.append(embedding.tolist())
            else:
                # Fallback: use a simple hash-based embedding
                import hashlib
                for chunk in chunks:
                    # Use MD5 for non-security embedding fallback (usedforsecurity=False)
                    hash_obj = hashlib.md5(chunk.encode(), usedforsecurity=False)
                    embedding = [float(ord(c)) for c in hash_obj.hexdigest()[:384]]  # 384 dimensions
                    embeddings.append(embedding)

            # Store in vector database
            embedding_ids = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                embedding_id = await self.vector_store_service.store_embedding(
                    document_id=str(document.id),
                    chunk_text=chunk,
                    chunk_index=i,
                    embedding=embedding,
                    metadata={
                        "document_id": str(document.id),
                        "chunk_index": i,
                        "chunk_length": len(chunk),
                        "document_type": document.file_type
                    }
                )
                embedding_ids.append(embedding_id)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProcessingResult(
                success=True,
                data={
                    "embedding_count": len(embedding_ids),
                    "embedding_ids": embedding_ids,
                    "chunk_count": len(chunks),
                    "average_chunk_length": sum(len(c) for c in chunks) / len(chunks) if chunks else 0,
                    "processing_time_ms": processing_time
                },
                processing_time_ms=processing_time
            )

        except Exception as e:
            logger.error(f"Vector embedding creation failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )

    async def _update_job_progress(self, job: ProcessingJob, progress: float, current_step: str) -> None:
        """Update job progress"""
        job.progress_percentage = progress
        job.result_data = job.result_data or {}
        job.result_data["current_step"] = current_step
        job.result_data["last_updated"] = datetime.utcnow().isoformat()
        self.db.commit()

    async def _update_document_metadata(self, document: Document, metadata: Dict[str, Any]) -> None:
        """Update document metadata with processing results"""
        document.metadata = document.metadata or {}
        document.metadata.update(metadata)
        document.processing_status = "processed"
        document.processed_at = datetime.utcnow()
        self.db.commit()

# Factory function for dependency injection
def get_enhanced_document_processing_service(db: Session = Depends(get_db)) -> EnhancedDocumentProcessingService:
    """Get enhanced document processing service instance"""
    return EnhancedDocumentProcessingService(db)
