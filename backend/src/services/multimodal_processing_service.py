"""
Multimodal Processing Service with async pipeline for OCR, transcription, and AI analysis
"""

import os
import asyncio
import uuid
import time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
import logging

# OCR and document processing
try:
    import pytesseract
    import fitz  # PyMuPDF
    import pdfplumber
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Image processing
try:
    from PIL import Image
    import cv2
    import numpy as np
    IMAGE_PROCESSING_AVAILABLE = True
except ImportError:
    IMAGE_PROCESSING_AVAILABLE = False

# Audio processing
try:
    import whisper
    import librosa
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False

# Video processing
try:
    import cv2
    import ffmpeg
    VIDEO_PROCESSING_AVAILABLE = True
except ImportError:
    VIDEO_PROCESSING_AVAILABLE = False

# AI processing
try:
    import openai
    import anthropic
    AI_PROCESSING_AVAILABLE = True
except ImportError:
    AI_PROCESSING_AVAILABLE = False

from src.core.config import settings
from src.core.database import get_db
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.processing import ProcessingJob, JobType, JobStatus
from src.services.entity_extraction_service import EntityExtractionService
from src.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

class ProcessingStep:
    """Represents a processing step in the pipeline"""

    def __init__(self, name: str, function: callable, required: bool = True):
        self.name = name
        self.function = function
        self.required = required
        self.start_time = None
        self.end_time = None
        self.success = False
        self.error_message = None

class MultimodalProcessingService:
    """Service for processing multimodal documents with async pipeline"""

    def __init__(self, db: Session):
        self.db = db
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.processed_dir = self.upload_dir / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        # Initialize AI clients
        self.openai_client = None
        self.anthropic_client = None

        if settings.OPENAI_API_KEY and AI_PROCESSING_AVAILABLE:
            openai.api_key = settings.OPENAI_API_KEY
            self.openai_client = openai

        if settings.ANTHROPIC_API_KEY and AI_PROCESSING_AVAILABLE:
            self.anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Initialize AI models
        self.whisper_model = None
        if AUDIO_PROCESSING_AVAILABLE:
            try:
                self.whisper_model = whisper.load_model("base")
            except Exception as e:
                logger.warning(f"Failed to load Whisper model: {str(e)}")

        # Initialize processing services
        self.entity_service = None
        self.embedding_service = None

    async def process_document(
        self,
        document: Document,
        job: ProcessingJob,
        upload_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main processing pipeline for multimodal documents
        """
        start_time = time.time()
        processing_results = {
            "text_extraction": {},
            "entity_extraction": {},
            "embedding_generation": {},
            "ai_analysis": {},
            "quality_assessment": {},
            "processing_time": 0,
            "success": False,
            "errors": []
        }

        try:
            # Update job status
            job.start_job()
            job.update_progress("Starting document processing", 10.0)
            self.db.commit()

            # Define processing pipeline based on document type
            processing_steps = self.get_processing_pipeline(document.document_type)

            # Execute processing pipeline
            for i, step in enumerate(processing_steps):
                try:
                    step.start_time = time.time()
                    progress_percentage = 10.0 + (i * 80.0 / len(processing_steps))

                    job.update_progress(f"Executing: {step.name}", progress_percentage)
                    self.db.commit()

                    # Execute step
                    result = await step.function(document, job)

                    step.success = True
                    step.end_time = time.time()

                    # Store result
                    step_name = step.name.lower().replace(" ", "_")
                    processing_results[step_name] = result

                    logger.info(f"Processing step '{step.name}' completed successfully")

                except Exception as e:
                    step.success = False
                    step.error_message = str(e)
                    step.end_time = time.time()

                    error_msg = f"Processing step '{step.name}' failed: {str(e)}"
                    logger.error(error_msg)
                    processing_results["errors"].append(error_msg)

                    if step.required:
                        # Fail the job if required step fails
                        job.fail_job(error_msg)
                        self.db.commit()
                        return processing_results

            # Finalize processing
            processing_results["processing_time"] = time.time() - start_time
            processing_results["success"] = len(processing_results["errors"]) == 0

            # Update document with processing results
            await self.update_document_with_results(document, processing_results)

            # Complete job
            job.complete_job(
                result={"processing_results": processing_results},
                artifacts={"processed_files": self.get_processed_files(document)},
                metrics={"processing_time_seconds": processing_results["processing_time"]}
            )
            self.db.commit()

            logger.info(f"Document processing completed for {document.id}")

            return processing_results

        except Exception as e:
            error_msg = f"Document processing failed: {str(e)}"
            logger.error(error_msg)

            job.fail_job(error_msg)
            self.db.commit()

            processing_results["errors"].append(error_msg)
            return processing_results

    def get_processing_pipeline(self, document_type: DocumentType) -> List[ProcessingStep]:
        """Get processing pipeline based on document type"""

        # Common steps for all document types
        common_steps = [
            ProcessingStep("Text Extraction", self.extract_text_content),
            ProcessingStep("Entity Extraction", self.extract_entities),
            ProcessingStep("Embedding Generation", self.generate_embeddings),
            ProcessingStep("AI Analysis", self.perform_ai_analysis, required=False),
            ProcessingStep("Quality Assessment", self.assess_quality, required=False)
        ]

        # Document type-specific steps
        if document_type == DocumentType.PDF:
            return [
                ProcessingStep("PDF Processing", self.process_pdf),
                ProcessingStep("OCR Extraction", self.extract_text_with_ocr, required=False),
                *common_steps
            ]
        elif document_type == DocumentType.IMAGE:
            return [
                ProcessingStep("Image Processing", self.process_image),
                ProcessingStep("Image OCR", self.extract_text_from_image, required=False),
                ProcessingStep("Image Analysis", self.analyze_image_content, required=False),
                *common_steps
            ]
        elif document_type == DocumentType.AUDIO:
            return [
                ProcessingStep("Audio Processing", self.process_audio),
                ProcessingStep("Audio Transcription", self.transcribe_audio),
                *common_steps
            ]
        elif document_type == DocumentType.VIDEO:
            return [
                ProcessingStep("Video Processing", self.process_video),
                ProcessingStep("Frame Extraction", self.extract_video_frames),
                ProcessingStep("Audio Extraction", self.extract_audio_from_video, required=False),
                *common_steps
            ]
        else:
            return common_steps

    async def process_pdf(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Process PDF document"""
        try:
            if not OCR_AVAILABLE:
                return {"error": "OCR libraries not available"}

            file_path = document.file_path
            results = {
                "text_content": "",
                "page_count": 0,
                "images_extracted": 0,
                "metadata": {}
            }

            # Extract text using PyMuPDF
            try:
                pdf_document = fitz.open(file_path)
                results["page_count"] = len(pdf_document)

                text_content = []
                for page_num in range(len(pdf_document)):
                    page = pdf_document.load_page(page_num)
                    text_content.append(page.get_text())

                results["text_content"] = "\n".join(text_content)

                # Extract metadata
                metadata = pdf_document.metadata
                results["metadata"] = {
                    "title": metadata.get("title", ""),
                    "author": metadata.get("author", ""),
                    "subject": metadata.get("subject", ""),
                    "creator": metadata.get("creator", ""),
                    "producer": metadata.get("producer", ""),
                    "creation_date": metadata.get("creationDate", ""),
                    "modification_date": metadata.get("modDate", "")
                }

                pdf_document.close()

            except Exception as e:
                logger.error(f"PyMuPDF processing failed: {str(e)}")

                # Fallback to pdfplumber
                try:
                    import pdfplumber
                    with pdfplumber.open(file_path) as pdf:
                        text_content = []
                        for page in pdf.pages:
                            text_content.append(page.extract_text())

                        results["text_content"] = "\n".join(text_content)
                        results["page_count"] = len(pdf.pages)

                except Exception as e2:
                    logger.error(f"pdfplumber fallback failed: {str(e2)}")
                    raise e

            return results

        except Exception as e:
            logger.error(f"PDF processing failed: {str(e)}")
            raise

    async def extract_text_with_ocr(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Extract text from PDF using OCR"""
        try:
            if not OCR_AVAILABLE:
                return {"error": "OCR not available"}

            file_path = document.file_path
            results = {
                "ocr_text": "",
                "confidence_scores": [],
                "processing_time": 0
            }

            start_time = time.time()

            # Use pytesseract for OCR
            try:
                import pytesseract
                from PIL import Image
                import fitz

                pdf_document = fitz.open(file_path)
                ocr_text_pages = []

                for page_num in range(len(pdf_document)):
                    page = pdf_document.load_page(page_num)

                    # Convert page to image
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
                    img_data = pix.tobytes("png")

                    # Perform OCR
                    image = Image.open(io.BytesIO(img_data))
                    text = pytesseract.image_to_string(image)
                    confidence = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

                    ocr_text_pages.append(text)

                    # Calculate average confidence
                    if confidence.get('conf'):
                        avg_confidence = sum(conf['conf'] for conf in confidence['conf'] if conf > 0) / len([c for c in confidence['conf'] if c > 0])
                        results["confidence_scores"].append(avg_confidence)

                results["ocr_text"] = "\n".join(ocr_text_pages)
                results["processing_time"] = time.time() - start_time

                pdf_document.close()

            except Exception as e:
                logger.error(f"OCR processing failed: {str(e)}")
                raise

            return results

        except Exception as e:
            logger.error(f"OCR extraction failed: {str(e)}")
            raise

    async def process_image(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Process image document"""
        try:
            if not IMAGE_PROCESSING_AVAILABLE:
                return {"error": "Image processing libraries not available"}

            file_path = document.file_path
            results = {
                "width": 0,
                "height": 0,
                "format": "",
                "mode": "",
                "size_bytes": 0,
                "has_transparency": False,
                "color_analysis": {}
            }

            # Analyze image using PIL
            with Image.open(file_path) as img:
                results.update({
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode,
                    "has_transparency": img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                })

                # Basic color analysis
                if img.mode == 'RGB':
                    # Convert to numpy array for analysis
                    img_array = np.array(img)
                    results["color_analysis"] = {
                        "mean_color": img_array.mean(axis=(0, 1)).tolist(),
                        "brightness": np.mean(img_array),
                        "contrast": np.std(img_array)
                    }

            results["size_bytes"] = os.path.getsize(file_path)

            return results

        except Exception as e:
            logger.error(f"Image processing failed: {str(e)}")
            raise

    async def extract_text_from_image(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Extract text from image using OCR"""
        try:
            if not OCR_AVAILABLE:
                return {"error": "OCR not available"}

            file_path = document.file_path
            results = {
                "extracted_text": "",
                "confidence_score": 0,
                "processing_time": 0
            }

            start_time = time.time()

            # Perform OCR using pytesseract
            with Image.open(file_path) as img:
                # Preprocess image for better OCR
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Extract text
                text = pytesseract.image_to_string(img)

                # Get confidence scores
                try:
                    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                    confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                    results["confidence_score"] = avg_confidence
                except:
                    results["confidence_score"] = 0

                results["extracted_text"] = text
                results["processing_time"] = time.time() - start_time

            return results

        except Exception as e:
            logger.error(f"Image OCR failed: {str(e)}")
            raise

    async def analyze_image_content(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Analyze image content using AI"""
        try:
            if not self.openai_client:
                return {"error": "AI processing not available"}

            file_path = document.file_path
            results = {
                "description": "",
                "objects": [],
                "scene_analysis": {},
                "confidence_scores": []
            }

            # This would require vision model integration
            # For now, return placeholder
            results["description"] = "Image content analysis not yet implemented"
            results["objects"] = []
            results["scene_analysis"] = {"type": "unknown"}

            return results

        except Exception as e:
            logger.error(f"Image analysis failed: {str(e)}")
            raise

    async def process_audio(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Process audio document"""
        try:
            if not AUDIO_PROCESSING_AVAILABLE:
                return {"error": "Audio processing libraries not available"}

            file_path = document.file_path
            results = {
                "duration": 0,
                "sample_rate": 0,
                "channels": 0,
                "format": "",
                "bitrate": 0,
                "file_size": 0
            }

            # Analyze audio using librosa
            try:
                y, sr = librosa.load(file_path, sr=None)
                duration = librosa.get_duration(y=y, sr=sr)

                results.update({
                    "duration": duration,
                    "sample_rate": sr,
                    "channels": 1 if y.ndim == 1 else y.shape[0]
                })

            except Exception as e:
                logger.error(f"Librosa analysis failed: {str(e)}")

                # Fallback basic analysis
                import mutagen
                try:
                    audio_file = mutagen.File(file_path)
                    if audio_file is not None:
                        results["duration"] = audio_file.info.length
                        results["bitrate"] = audio_file.info.bitrate
                except:
                    pass

            results["format"] = Path(file_path).suffix[1:].upper()
            results["file_size"] = os.path.getsize(file_path)

            return results

        except Exception as e:
            logger.error(f"Audio processing failed: {str(e)}")
            raise

    async def transcribe_audio(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Transcribe audio using Whisper"""
        try:
            if not self.whisper_model:
                return {"error": "Whisper model not available"}

            file_path = document.file_path
            results = {
                "transcription": "",
                "language": "",
                "confidence": 0,
                "processing_time": 0
            }

            start_time = time.time()

            # Transcribe using Whisper
            result = self.whisper_model.transcribe(file_path)

            results["transcription"] = result["text"]
            results["language"] = result.get("language", "unknown")
            results["processing_time"] = time.time() - start_time

            return results

        except Exception as e:
            logger.error(f"Audio transcription failed: {str(e)}")
            raise

    async def process_video(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Process video document"""
        try:
            if not VIDEO_PROCESSING_AVAILABLE:
                return {"error": "Video processing libraries not available"}

            file_path = document.file_path
            results = {
                "duration": 0,
                "fps": 0,
                "width": 0,
                "height": 0,
                "frames_count": 0,
                "format": "",
                "file_size": 0
            }

            # Analyze video using OpenCV
            try:
                cap = cv2.VideoCapture(file_path)

                if cap.isOpened():
                    results["fps"] = cap.get(cv2.CAP_PROP_FPS)
                    results["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    results["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    results["frames_count"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    results["duration"] = results["frames_count"] / results["fps"] if results["fps"] > 0 else 0

                cap.release()

            except Exception as e:
                logger.error(f"OpenCV analysis failed: {str(e)}")

            results["format"] = Path(file_path).suffix[1:].upper()
            results["file_size"] = os.path.getsize(file_path)

            return results

        except Exception as e:
            logger.error(f"Video processing failed: {str(e)}")
            raise

    async def extract_video_frames(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Extract key frames from video"""
        try:
            if not VIDEO_PROCESSING_AVAILABLE:
                return {"error": "Video processing not available"}

            file_path = document.file_path
            results = {
                "extracted_frames": [],
                "frame_count": 0,
                "extraction_method": "uniform"
            }

            # Create output directory for frames
            frames_dir = self.processed_dir / f"{document.id}_frames"
            frames_dir.mkdir(exist_ok=True)

            # Extract frames using OpenCV
            try:
                cap = cv2.VideoCapture(file_path)

                if not cap.isOpened():
                    raise Exception("Cannot open video file")

                fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

                # Extract 10 frames uniformly distributed
                frames_to_extract = min(10, total_frames)
                frame_interval = total_frames // frames_to_extract if frames_to_extract > 0 else 1

                extracted_frames = []
                for i in range(0, total_frames, frame_interval):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, frame = cap.read()

                    if ret:
                        frame_filename = f"frame_{i:06d}.jpg"
                        frame_path = frames_dir / frame_filename

                        cv2.imwrite(str(frame_path), frame)
                        extracted_frames.append({
                            "frame_number": i,
                            "timestamp": i / fps if fps > 0 else 0,
                            "filename": frame_filename,
                            "path": str(frame_path)
                        })

                        if len(extracted_frames) >= frames_to_extract:
                            break

                cap.release()

                results["extracted_frames"] = extracted_frames
                results["frame_count"] = len(extracted_frames)

            except Exception as e:
                logger.error(f"Frame extraction failed: {str(e)}")
                raise

            return results

        except Exception as e:
            logger.error(f"Video frame extraction failed: {str(e)}")
            raise

    async def extract_audio_from_video(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Extract audio from video"""
        try:
            file_path = document.file_path
            results = {
                "audio_extracted": False,
                "audio_path": "",
                "audio_duration": 0
            }

            # Extract audio using ffmpeg-python
            try:
                import ffmpeg

                audio_path = self.processed_dir / f"{document.id}_audio.wav"

                (
                    ffmpeg
                    .input(file_path)
                    .audio
                    .output(str(audio_path))
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )

                if audio_path.exists():
                    results["audio_extracted"] = True
                    results["audio_path"] = str(audio_path)

                    # Get audio duration
                    try:
                        import librosa
                        y, sr = librosa.load(str(audio_path), sr=None)
                        results["audio_duration"] = librosa.get_duration(y=y, sr=sr)
                    except:
                        pass

            except Exception as e:
                logger.error(f"Audio extraction failed: {str(e)}")
                # Don't raise error as this is optional

            return results

        except Exception as e:
            logger.error(f"Video audio extraction failed: {str(e)}")
            raise

    async def extract_text_content(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Extract text content from document"""
        try:
            results = {
                "text_content": "",
                "extraction_method": "",
                "confidence": 0,
                "word_count": 0,
                "character_count": 0
            }

            # Use existing file_service for text extraction
            from src.services.file_service import FileService
            file_service = FileService(self.db)

            text_content = file_service.extract_text_content(document)

            results["text_content"] = text_content
            results["extraction_method"] = "basic"
            results["word_count"] = len(text_content.split()) if text_content else 0
            results["character_count"] = len(text_content)

            return results

        except Exception as e:
            logger.error(f"Text extraction failed: {str(e)}")
            raise

    async def extract_entities(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Extract entities from document text"""
        try:
            if not self.entity_service:
                self.entity_service = EntityExtractionService(self.db)

            text_content = document.content_text or ""
            if not text_content:
                return {"entities": [], "entity_count": 0, "extraction_method": "none"}

            results = {
                "entities": [],
                "entity_count": 0,
                "extraction_method": "spacy",
                "processing_time": 0
            }

            start_time = time.time()

            # Extract entities
            entities = await self.entity_service.extract_entities_from_text(
                text_content,
                document_id=document.id,
                organization_id=document.organization_id
            )

            results["entities"] = [
                {
                    "text": entity.name,
                    "label": entity.entity_type.value,
                    "confidence": entity.confidence_score,
                    "start": entity.metadata.get("start", 0) if entity.metadata else 0,
                    "end": entity.metadata.get("end", 0) if entity.metadata else 0
                }
                for entity in entities
            ]

            results["entity_count"] = len(entities)
            results["processing_time"] = time.time() - start_time

            return results

        except Exception as e:
            logger.error(f"Entity extraction failed: {str(e)}")
            raise

    async def generate_embeddings(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Generate embeddings for document"""
        try:
            if not self.embedding_service:
                self.embedding_service = EmbeddingService(self.db)

            text_content = document.content_text or ""
            if not text_content:
                return {"embedding_generated": False, "reason": "No text content"}

            results = {
                "embedding_generated": False,
                "embedding_id": None,
                "vector_dimension": 0,
                "processing_time": 0
            }

            start_time = time.time()

            # Generate embeddings
            embedding_id = await self.embedding_service.generate_and_store_embedding(
                text=text_content,
                document_id=document.id,
                organization_id=document.organization_id
            )

            if embedding_id:
                results.update({
                    "embedding_generated": True,
                    "embedding_id": embedding_id,
                    "vector_dimension": getattr(settings, 'EMBEDDING_DIMENSION', 384),
                    "processing_time": time.time() - start_time
                })

                # Update document
                document.embedding_id = embedding_id
                document.is_embedded = True
                self.db.commit()

            return results

        except Exception as e:
            logger.error(f"Embedding generation failed: {str(e)}")
            raise

    async def perform_ai_analysis(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Perform AI analysis on document"""
        try:
            if not (self.openai_client or self.anthropic_client):
                return {"analysis_performed": False, "reason": "AI clients not available"}

            text_content = document.content_text or ""
            if not text_content:
                return {"analysis_performed": False, "reason": "No text content"}

            results = {
                "analysis_performed": False,
                "summary": "",
                "key_topics": [],
                "sentiment": {},
                "insights": [],
                "processing_time": 0
            }

            start_time = time.time()

            # Use OpenAI for analysis
            if self.openai_client:
                try:
                    response = self.openai_client.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {
                                "role": "system",
                                "content": "Analyze the following document and provide a summary, key topics, sentiment, and insights."
                            },
                            {
                                "role": "user",
                                "content": text_content[:4000]  # Limit text length
                            }
                        ],
                        max_tokens=500,
                        temperature=0.3
                    )

                    analysis_text = response.choices[0].message.content

                    # Parse analysis (simplified)
                    results["summary"] = analysis_text
                    results["analysis_performed"] = True

                except Exception as e:
                    logger.error(f"OpenAI analysis failed: {str(e)}")

            results["processing_time"] = time.time() - start_time

            return results

        except Exception as e:
            logger.error(f"AI analysis failed: {str(e)}")
            raise

    async def assess_quality(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
        """Assess document quality"""
        try:
            from src.services.document_quality_service import DocumentQualityService

            if not hasattr(self, 'quality_service'):
                self.quality_service = DocumentQualityService(self.db)

            results = await self.quality_service.comprehensive_quality_assessment(document)
            results["quality_assessment_performed"] = True

            return results

        except Exception as e:
            logger.error(f"Quality assessment failed: {str(e)}")
            return {
                "quality_assessment_performed": False,
                "error": str(e),
                "overall_score": 0.0
            }

    async def update_document_with_results(self, document: Document, results: Dict[str, Any]):
        """Update document with processing results"""
        try:
            # Update text content
            if "text_extraction" in results and results["text_extraction"].get("text_content"):
                document.content_text = results["text_extraction"]["text_content"]

            # Update processing status
            if results["success"]:
                document.processing_status = ProcessingStatus.COMPLETED
            else:
                document.processing_status = ProcessingStatus.FAILED
                document.processing_error = "; ".join(results["errors"])

            # Update processing timestamps
            document.processing_completed_at = datetime.utcnow()

            # Store processing results in metadata
            document.add_metadata("processing_results", results)
            document.add_metadata("processed_at", datetime.utcnow().isoformat())

            # Mark as indexed if successful
            if results["success"]:
                document.is_indexed = True

            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to update document with results: {str(e)}")
            raise

    def get_processed_files(self, document: Document) -> List[str]:
        """Get list of processed files for document"""
        processed_files = []
        document_id = str(document.id)

        # Check for extracted frames
        frames_dir = self.processed_dir / f"{document_id}_frames"
        if frames_dir.exists():
            processed_files.extend([str(f) for f in frames_dir.glob("*.jpg")])

        # Check for extracted audio
        audio_file = self.processed_dir / f"{document_id}_audio.wav"
        if audio_file.exists():
            processed_files.append(str(audio_file))

        return processed_files

    def estimate_processing_time(self, document_type: DocumentType, file_size_bytes: int) -> int:
        """Estimate processing time in seconds"""
        base_times = {
            DocumentType.TEXT: 5,
            DocumentType.PDF: 30,
            DocumentType.IMAGE: 15,
            DocumentType.AUDIO: 60,
            DocumentType.VIDEO: 120,
            DocumentType.SPREADSHEET: 10,
            DocumentType.PRESENTATION: 20,
            DocumentType.MULTIMODAL: 45
        }

        base_time = base_times.get(document_type, 30)

        # Adjust based on file size (in MB)
        size_mb = file_size_bytes / (1024 * 1024)
        size_factor = max(1.0, size_mb / 10.0)  # Normalize to 10MB

        estimated_time = int(base_time * size_factor)
        return min(estimated_time, 600)  # Cap at 10 minutes

# Dependency injection
def get_multimodal_processing_service(db: Session = Depends(get_db)) -> MultimodalProcessingService:
    """Get multimodal processing service instance"""
    return MultimodalProcessingService(db)