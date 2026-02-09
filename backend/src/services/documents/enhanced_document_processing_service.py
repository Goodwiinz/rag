"""
Enhanced Document Processing Service
Provides comprehensive document processing with multimodal support, entity extraction,
knowledge graph integration, and real-time progress tracking
"""

import asyncio
import hashlib
import io
import json
import logging
import os
import re
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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

import openai

# AI/ML libraries
import spacy
from fastapi import Depends
from sentence_transformers import SentenceTransformer

# Database and storage
from sqlalchemy.orm import Session
from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline

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

# Note: ExtractedEntity and ExtractedRelationship not found in models/entity.py
# Using Entity from models/entity as fallback
from src.models.entity import Entity as ExtractedEntity
from src.models.processing import JobStatus, JobType, ProcessingJob

ExtractedRelationship = None  # Not defined yet
from src.core.database import get_db
from src.services.knowledge_graph import KnowledgeGraphService
from src.services.search.vector_service import VectorService as VectorStoreService

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
            # Load spaCy model for entity extraction
            self.nlp = spacy.load("en_core_web_sm")

            # Load sentence transformer for embeddings
            self.sentence_model = SentenceTransformer("all-MiniLM-L6-v2")

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
                    "char_count": len(page_text),
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
                    "processing_method": "pymupdf"
                    if len(extracted_text.strip()) >= 100
                    else "ocr",
                },
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    async def process_text(self, document: Document) -> ProcessingResult:
        """Process text document"""
        start_time = datetime.now()

        try:
            # Download file from MinIO
            file_content = await self._download_from_storage(document.file_path)

            # Decode text
            text = file_content.decode("utf-8")

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProcessingResult(
                success=True,
                data={
                    "text": text,
                    "text_length": len(text),
                    "line_count": len(text.split("\n")),
                    "word_count": len(text.split()),
                    "processing_method": "direct",
                },
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
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
                "has_text": len(extracted_text.strip()) > 0,
            }

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProcessingResult(
                success=True,
                data={
                    "text": extracted_text,
                    "metadata": image_metadata,
                    "text_length": len(extracted_text),
                    "processing_method": "tesseract_ocr",
                },
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
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
                "sample_width": audio.sample_width,
            }

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProcessingResult(
                success=True,
                data={
                    "text": extracted_text,
                    "metadata": audio_metadata,
                    "text_length": len(extracted_text),
                    "processing_method": "google_speech_recognition",
                },
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    async def _download_from_storage(self, file_path: str) -> bytes:
        """Download file from MinIO storage"""
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
                pix = page.get_pixmap(
                    matrix=fitz.Matrix(2, 2)
                )  # 2x zoom for better OCR
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


class EntityExtractor:
    """Extracts entities and relationships from text"""

    def __init__(self):
        self.nlp = None
        self._load_model()

    def _load_model(self):
        """Load spaCy model"""
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except Exception as e:
            logger.error(f"Failed to load spaCy model: {e}")

    async def extract_entities(self, text: str, document_id: str) -> ProcessingResult:
        """Extract entities from text using spaCy"""
        start_time = datetime.now()

        try:
            if not self.nlp:
                # Fallback to basic pattern matching
                return await self._extract_entities_basic(text, document_id)

            # Process text with spaCy
            doc = self.nlp(text)

            entities = []
            for ent in doc.ents:
                entity = {
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "confidence": 1.0,  # spaCy doesn't provide confidence scores
                    "context": text[max(0, ent.start_char - 50) : ent.end_char + 50],
                }
                entities.append(entity)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProcessingResult(
                success=True,
                data={
                    "entities": entities,
                    "entity_count": len(entities),
                    "entity_types": list(set([e["label"] for e in entities])),
                    "processing_method": "spacy",
                },
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    async def extract_relationships(
        self, text: str, entities: List[Dict], document_id: str
    ) -> ProcessingResult:
        """Extract relationships between entities"""
        start_time = datetime.now()

        try:
            relationships = []

            # Simple pattern-based relationship extraction
            # This can be enhanced with more sophisticated NLP techniques

            # Define relationship patterns
            relationship_patterns = [
                (
                    r"(\w+)\s+(works for|is employed by|is a member of)\s+(\w+)",
                    "WORKS_FOR",
                ),
                (
                    r"(\w+)\s+(is located in|is based in|is situated in)\s+(\w+)",
                    "LOCATED_IN",
                ),
                (
                    r"(\w+)\s+(is the CEO of|is the president of|is the director of)\s+(\w+)",
                    "LEADS",
                ),
                (r"(\w+)\s+(owns|founded|established)\s+(\w+)", "OWNS"),
                (
                    r"(\w+)\s+(is a|is an|is the)\s+(\w+)\s+(at|in|for)\s+(\w+)",
                    "RELATED_TO",
                ),
            ]

            for pattern, rel_type in relationship_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    source_entity = match.group(1).strip()
                    target_entity = match.group(3).strip()

                    # Find corresponding entities
                    source_found = False
                    target_found = False

                    for entity in entities:
                        if source_entity.lower() in entity["text"].lower():
                            source_found = True
                        if target_entity.lower() in entity["text"].lower():
                            target_found = True

                    if source_found and target_found:
                        relationship = {
                            "source": source_entity,
                            "target": target_entity,
                            "type": rel_type,
                            "context": text[
                                max(0, match.start() - 50) : match.end() + 50
                            ],
                            "confidence": 0.8,  # Default confidence for pattern-based extraction
                        }
                        relationships.append(relationship)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProcessingResult(
                success=True,
                data={
                    "relationships": relationships,
                    "relationship_count": len(relationships),
                    "relationship_types": list(set([r["type"] for r in relationships])),
                    "processing_method": "pattern_based",
                },
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"Relationship extraction failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    async def _extract_entities_basic(
        self, text: str, document_id: str
    ) -> ProcessingResult:
        """Basic entity extraction using patterns"""
        try:
            # Define patterns for common entity types
            patterns = {
                "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                "PHONE": r"\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\)\s*\d{3}-\d{4}\b",
                "DATE": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
                "MONEY": r"\$\d+(?:,\d{3})*(?:\.\d{2})?",
                "URL": r"https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?",
            }

            entities = []
            for entity_type, pattern in patterns.items():
                matches = re.finditer(pattern, text)
                for match in matches:
                    entity = {
                        "text": match.group(),
                        "label": entity_type,
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 0.9,
                        "context": text[max(0, match.start() - 50) : match.end() + 50],
                    }
                    entities.append(entity)

            return ProcessingResult(
                success=True,
                data={
                    "entities": entities,
                    "entity_count": len(entities),
                    "entity_types": list(patterns.keys()),
                    "processing_method": "pattern_based",
                },
                processing_time_ms=0,
            )

        except Exception as e:
            return ProcessingResult(
                success=False, data={}, error=str(e), processing_time_ms=0
            )


class EnhancedDocumentProcessingService:
    """Enhanced document processing service with multimodal support"""

    def __init__(self, db: Session):
        self.db = db
        self.minio_client = self._init_minio_client()
        self.multimodal_processor = MultimodalProcessor(self.minio_client)
        self.entity_extractor = EntityExtractor()
        self.knowledge_graph_service = KnowledgeGraphService(db)
        self.vector_store_service = VectorStoreService(db)

    def _init_minio_client(self) -> Minio:
        """Initialize MinIO client"""
        try:
            return Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise

    async def process_document(self, job_id: str) -> ProcessingResult:
        """Process document through the complete pipeline"""
        try:
            # Get processing job
            job = (
                self.db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            )

            if not job:
                raise ValueError(f"Processing job {job_id} not found")

            # Get document
            document = (
                self.db.query(Document).filter(Document.id == job.document_id).first()
            )

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
                entity_result = await self.entity_extractor.extract_entities(
                    extracted_text, str(document.id)
                )

                if entity_result.success:
                    await self._save_entities(
                        document, entity_result.data.get("entities", [])
                    )

                current_step += 1

                # Step 3: Relationship Extraction
                await self._update_job_progress(job, 50, "Extracting relationships")
                entities = entity_result.data.get("entities", [])

                relationship_result = await self.entity_extractor.extract_relationships(
                    extracted_text, entities, str(document.id)
                )

                if relationship_result.success:
                    await self._save_relationships(
                        document, relationship_result.data.get("relationships", [])
                    )
            else:
                entity_result = ProcessingResult(success=True, data={"entities": []})
                relationship_result = ProcessingResult(
                    success=True, data={"relationships": []}
                )

            current_step += 1

            # Step 4: Knowledge Graph Population
            await self._update_job_progress(job, 70, "Populating knowledge graph")

            if entity_result.success and entity_result.data.get("entities"):
                graph_result = await self._populate_knowledge_graph(
                    document,
                    entity_result.data.get("entities", []),
                    relationship_result.data.get("relationships", []),
                )
            else:
                graph_result = ProcessingResult(
                    success=True, data={"nodes_created": 0, "relationships_created": 0}
                )

            current_step += 1

            # Step 5: Vector Indexing
            await self._update_job_progress(job, 90, "Creating vector embeddings")

            if extracted_text:
                vector_result = await self._create_vector_embeddings(
                    document, extracted_text
                )
            else:
                vector_result = ProcessingResult(
                    success=True, data={"embedding_id": None}
                )

            # Update document with processing results
            await self._update_document_metadata(
                document,
                {
                    "extraction": extraction_result.data,
                    "entities": entity_result.data,
                    "relationships": relationship_result.data,
                    "knowledge_graph": graph_result.data,
                    "vectors": vector_result.data,
                    "processing_completed_at": datetime.utcnow().isoformat(),
                },
            )

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
                "total_processing_time_ms": sum(
                    [
                        extraction_result.processing_time_ms or 0,
                        entity_result.processing_time_ms or 0,
                        relationship_result.processing_time_ms or 0,
                        graph_result.processing_time_ms or 0,
                        vector_result.processing_time_ms or 0,
                    ]
                ),
            }

            self.db.commit()

            logger.info(f"Document processing completed for {document.id}")

            return ProcessingResult(
                success=True,
                data={
                    "document_id": str(document.id),
                    "processing_steps_completed": current_step,
                    "total_processing_time_ms": job.result_data.get(
                        "total_processing_time_ms"
                    ),
                },
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

            return ProcessingResult(success=False, data={}, error=str(e))

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
                error=f"Unsupported file type: {document.file_type}",
            )

    async def _save_entities(
        self, document: Document, entities: List[Dict[str, Any]]
    ) -> None:
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
                    extraction_method="spacy"
                    if self.entity_extractor.nlp
                    else "pattern_based",
                    model_version="spacy_en_core_web_sm",
                    metadata={
                        "document_id": str(document.id),
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                    },
                )
                self.db.add(entity)

            self.db.commit()
            logger.info(f"Saved {len(entities)} entities for document {document.id}")

        except Exception as e:
            logger.error(f"Failed to save entities: {e}")
            raise

    async def _save_relationships(
        self, document: Document, relationships: List[Dict[str, Any]]
    ) -> None:
        """Save extracted relationships to database"""
        try:
            for rel_data in relationships:
                # Find source and target entities
                source_entity = (
                    self.db.query(ExtractedEntity)
                    .filter(
                        ExtractedEntity.document_id == document.id,
                        ExtractedEntity.entity_text.ilike(f"%{rel_data['source']}%"),
                    )
                    .first()
                )

                target_entity = (
                    self.db.query(ExtractedEntity)
                    .filter(
                        ExtractedEntity.document_id == document.id,
                        ExtractedEntity.entity_text.ilike(f"%{rel_data['target']}%"),
                    )
                    .first()
                )

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
                            "extraction_timestamp": datetime.utcnow().isoformat(),
                        },
                    )
                    self.db.add(relationship)

            self.db.commit()
            logger.info(
                f"Saved {len(relationships)} relationships for document {document.id}"
            )

        except Exception as e:
            logger.error(f"Failed to save relationships: {e}")
            raise

    async def _populate_knowledge_graph(
        self,
        document: Document,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> ProcessingResult:
        """Populate knowledge graph with entities and relationships"""
        start_time = datetime.now()

        try:
            nodes_created = 0
            relationships_created = 0

            # Create nodes for entities
            for entity_data in entities:
                node_id = await self.knowledge_graph_service.create_entity_node(
                    entity_text=entity_data["text"],
                    entity_type=entity_data["label"],
                    document_id=str(document.id),
                    confidence=entity_data.get("confidence", 1.0),
                    metadata=entity_data.get("context", ""),
                )

                if node_id:
                    nodes_created += 1

            # Create relationships
            for rel_data in relationships:
                # Find corresponding nodes in Neo4j
                source_node = await self.knowledge_graph_service.find_entity_node(
                    rel_data["source"], rel_data.get("source_type", "UNKNOWN")
                )
                target_node = await self.knowledge_graph_service.find_entity_node(
                    rel_data["target"], rel_data.get("target_type", "UNKNOWN")
                )

                if source_node and target_node:
                    rel_id = await self.knowledge_graph_service.create_relationship(
                        source_node["id"],
                        target_node["id"],
                        rel_data["type"],
                        confidence=rel_data.get("confidence", 0.8),
                        document_id=str(document.id),
                    )

                    if rel_id:
                        relationships_created += 1

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProcessingResult(
                success=True,
                data={
                    "nodes_created": nodes_created,
                    "relationships_created": relationships_created,
                    "total_entities": len(entities),
                    "total_relationships": len(relationships),
                    "processing_time_ms": processing_time,
                },
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"Knowledge graph population failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    async def _create_vector_embeddings(
        self, document: Document, text: str
    ) -> ProcessingResult:
        """Create vector embeddings for document text"""
        start_time = datetime.now()

        try:
            # Split text into chunks
            chunk_size = 500
            chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

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
                    hash_obj = hashlib.md5(chunk.encode())
                    embedding = [
                        float(ord(c)) for c in hash_obj.hexdigest()[:384]
                    ]  # 384 dimensions
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
                        "document_type": document.file_type,
                    },
                )
                embedding_ids.append(embedding_id)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProcessingResult(
                success=True,
                data={
                    "embedding_count": len(embedding_ids),
                    "embedding_ids": embedding_ids,
                    "chunk_count": len(chunks),
                    "average_chunk_length": sum(len(c) for c in chunks) / len(chunks)
                    if chunks
                    else 0,
                    "processing_time_ms": processing_time,
                },
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"Vector embedding creation failed: {e}")
            return ProcessingResult(
                success=False,
                data={},
                error=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    async def _update_job_progress(
        self, job: ProcessingJob, progress: float, current_step: str
    ) -> None:
        """Update job progress"""
        job.progress_percentage = progress
        job.result_data = job.result_data or {}
        job.result_data["current_step"] = current_step
        job.result_data["last_updated"] = datetime.utcnow().isoformat()
        self.db.commit()

    async def _update_document_metadata(
        self, document: Document, metadata: Dict[str, Any]
    ) -> None:
        """Update document metadata with processing results"""
        document.metadata = document.metadata or {}
        document.metadata.update(metadata)
        document.processing_status = "processed"
        document.processed_at = datetime.utcnow()
        self.db.commit()


# Factory function for dependency injection
def get_enhanced_document_processing_service(
    db: Session = Depends(get_db),
) -> EnhancedDocumentProcessingService:
    """Get enhanced document processing service instance"""
    return EnhancedDocumentProcessingService(db)
