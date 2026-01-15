"""
Document Factory for Test Data Generation
Creates realistic test documents, processing jobs, and related entities
"""

import uuid
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from faker import Faker

# Import models
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.processing import ProcessingJob, JobType, JobStatus, JobPriority
from src.models.quality import QualityMetric
from src.models.user import User
from src.models.organization import Organization


# Initialize Faker for realistic data generation
fake = Faker()


@dataclass
class DocumentConfig:
    """Configuration for document generation"""
    title: Optional[str] = None
    filename: Optional[str] = None
    file_type: DocumentType = DocumentType.PDF
    file_size_bytes: Optional[int] = None
    processing_status: ProcessingStatus = ProcessingStatus.COMPLETED
    is_public: bool = False
    is_deleted: bool = False
    uploaded_by_user_id: Optional[str] = None
    organization_id: Optional[str] = None
    custom_metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    page_count: Optional[int] = None
    duration_seconds: Optional[int] = None
    processing_error: Optional[str] = None


@dataclass
class ProcessingJobConfig:
    """Configuration for processing job generation"""
    job_type: JobType = JobType.DOCUMENT_INGESTION
    status: JobStatus = JobStatus.COMPLETED
    priority: JobPriority = JobPriority.NORMAL
    document_id: Optional[str] = None
    organization_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    total_steps: int = 10
    completed_steps: int = 10
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class QualityMetricConfig:
    """Configuration for quality assessment generation"""
    document_id: Optional[str] = None
    overall_score: Optional[float] = None
    readability_score: Optional[float] = None
    content_quality_score: Optional[float] = None
    technical_quality_score: Optional[float] = None
    recommendations: List[str] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    processing_time_ms: Optional[int] = None
    created_at: Optional[datetime] = None


class DocumentFactory:
    """Factory for creating test documents and related entities"""

    # File type configurations with realistic extensions and MIME types
    FILE_TYPE_CONFIGS = {
        DocumentType.PDF: {
            'extensions': ['.pdf'],
            'mime_types': ['application/pdf'],
            'size_range': (50 * 1024, 50 * 1024 * 1024),  # 50KB - 50MB
            'has_pages': True,
            'has_duration': False
        },
        DocumentType.TEXT: {
            'extensions': ['.txt', '.md'],
            'mime_types': ['text/plain', 'text/markdown'],
            'size_range': (1 * 1024, 5 * 1024 * 1024),  # 1KB - 5MB
            'has_pages': False,
            'has_duration': False
        },
        DocumentType.JPG: {
            'extensions': ['.jpg', '.jpeg'],
            'mime_types': ['image/jpeg'],
            'size_range': (10 * 1024, 10 * 1024 * 1024),  # 10KB - 10MB
            'has_pages': False,
            'has_duration': False
        },
        DocumentType.PNG: {
            'extensions': ['.png'],
            'mime_types': ['image/png'],
            'size_range': (10 * 1024, 10 * 1024 * 1024),  # 10KB - 10MB
            'has_pages': False,
            'has_duration': False
        },
        DocumentType.MP3: {
            'extensions': ['.mp3'],
            'mime_types': ['audio/mpeg', 'audio/mp3'],
            'size_range': (100 * 1024, 100 * 1024 * 1024),  # 100KB - 100MB
            'has_pages': False,
            'has_duration': True
        },
        DocumentType.MP4: {
            'extensions': ['.mp4', '.avi', '.mov'],
            'mime_types': ['video/mp4', 'video/avi', 'video/quicktime'],
            'size_range': (1 * 1024 * 1024, 1024 * 1024 * 1024),  # 1MB - 1GB
            'has_pages': False,
            'has_duration': True
        }
    }

    @classmethod
    def create_document(cls, config: Optional[DocumentConfig] = None) -> Document:
        """
        Create a single test document with realistic data

        Args:
            config: Document configuration overrides

        Returns:
            Document instance with test data
        """
        if config is None:
            config = DocumentConfig()

        # Generate title and filename if not provided
        title = config.title or cls._generate_title(config.file_type)
        filename = config.filename or cls._generate_filename(title, config.file_type)

        # Determine file size if not provided
        if config.file_size_bytes is None:
            size_range = cls.FILE_TYPE_CONFIGS[config.file_type]['size_range']
            config.file_size_bytes = random.randint(*size_range)

        # Generate timestamps
        now = datetime.utcnow()
        created_at = config.created_at or now - timedelta(days=random.randint(1, 365))
        updated_at = config.updated_at or created_at + timedelta(minutes=random.randint(1, 60))

        # Generate file-specific metadata
        page_count = None
        duration_seconds = None
        file_type_config = cls.FILE_TYPE_CONFIGS[config.file_type]

        if file_type_config['has_pages'] and config.page_count is None:
            page_count = random.randint(1, 500)

        if file_type_config['has_duration'] and config.duration_seconds is None:
            # Generate realistic duration (10 seconds to 2 hours)
            duration_seconds = random.randint(10, 7200)

        # Generate MIME type
        mime_types = file_type_config['mime_types']
        mime_type = random.choice(mime_types)

        # Generate thumbnail URL for supported types
        thumbnail_url = config.thumbnail_url
        if thumbnail_url is None and config.file_type in [DocumentType.PDF, DocumentType.JPG, DocumentType.PNG]:
            thumbnail_url = f"https://test-thumbnails.example.com/{uuid.uuid4()}.jpg"

        # Generate custom metadata
        if not config.custom_metadata:
            config.custom_metadata = cls._generate_custom_metadata(config.file_type)

        # Create document instance
        document = Document(
            id=str(uuid.uuid4()),
            title=title,
            filename=filename,
            file_path=f"/uploads/{uuid.uuid4()}/{filename}",
            file_type=config.file_type,
            mime_type=mime_type,
            file_size_bytes=config.file_size_bytes,
            file_size_mb=round(config.file_size_bytes / (1024 * 1024), 3),
            processing_status=config.processing_status,
            uploaded_by_user_id=config.uploaded_by_user_id or str(uuid.uuid4()),
            organization_id=config.organization_id or str(uuid.uuid4()),
            is_public=config.is_public,
            is_deleted=config.is_deleted,
            created_at=created_at,
            updated_at=updated_at,
            thumbnail_url=thumbnail_url,
            page_count=page_count,
            duration_seconds=duration_seconds,
            processing_error=config.processing_error,
            custom_metadata=config.custom_metadata
        )

        return document

    @classmethod
    def create_batch_documents(cls, count: int, config: Optional[DocumentConfig] = None) -> List[Document]:
        """
        Create multiple test documents

        Args:
            count: Number of documents to create
            config: Base configuration for all documents

        Returns:
            List of Document instances
        """
        documents = []

        for i in range(count):
            # Create variation in config for each document
            doc_config = DocumentConfig() if config is None else DocumentConfig(**config.__dict__)

            # Add variation to processing status
            if config is None or config.processing_status == ProcessingStatus.INDEXED:
                doc_config.processing_status = random.choice(list(ProcessingStatus))

            # Add variation to file type if not specified
            if config is None or config.file_type == DocumentType.PDF:
                doc_config.file_type = random.choice(list(DocumentType))

            # Add variation to public status
            if config is None:
                doc_config.is_public = random.choice([True, False])

            # Generate unique title
            doc_config.title = f"{doc_config.title or 'Test Document'} {i+1}"

            document = cls.create_document(doc_config)
            documents.append(document)

        return documents

    @classmethod
    def create_processing_job(cls, config: Optional[ProcessingJobConfig] = None) -> ProcessingJob:
        """
        Create a test processing job

        Args:
            config: Processing job configuration

        Returns:
            ProcessingJob instance
        """
        if config is None:
            config = ProcessingJobConfig()

        # Generate timestamps
        now = datetime.utcnow()
        created_at = config.created_at or now - timedelta(minutes=random.randint(1, 60))

        started_at = config.started_at
        if started_at is None and config.status in [JobStatus.IN_PROGRESS, JobStatus.COMPLETED, JobStatus.FAILED]:
            started_at = created_at + timedelta(minutes=random.randint(1, 5))

        completed_at = config.completed_at
        if completed_at is None and config.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            completed_at = started_at + timedelta(minutes=random.randint(1, 30))

        updated_at = config.updated_at or completed_at or started_at or created_at

        # Generate realistic parameters based on job type
        if not config.parameters:
            config.parameters = cls._generate_job_parameters(config.job_type)

        # Generate realistic config based on job type
        if not config.config:
            config.config = cls._generate_job_config(config.job_type)

        # Create processing job instance
        job = ProcessingJob(
            id=str(uuid.uuid4()),
            job_type=config.job_type,
            status=config.status,
            priority=config.priority,
            document_id=config.document_id or str(uuid.uuid4()),
            organization_id=config.organization_id or str(uuid.uuid4()),
            created_by_user_id=config.created_by_user_id or str(uuid.uuid4()),
            parameters=config.parameters,
            config=config.config,
            total_steps=config.total_steps,
            completed_steps=config.completed_steps,
            error_message=config.error_message,
            started_at=started_at,
            completed_at=completed_at,
            created_at=created_at,
            updated_at=updated_at
        )

        return job

    @classmethod
    def create_quality_assessment(cls, config: Optional[QualityMetricConfig] = None) -> QualityMetric:
        """
        Create a test quality assessment

        Args:
            config: Quality assessment configuration

        Returns:
            QualityMetric instance
        """
        if config is None:
            config = QualityMetricConfig()

        # Generate scores if not provided
        if config.overall_score is None:
            config.overall_score = round(random.uniform(0.3, 0.95), 2)

        if config.readability_score is None:
            config.readability_score = round(random.uniform(0.4, 0.95), 2)

        if config.content_quality_score is None:
            config.content_quality_score = round(random.uniform(0.3, 0.95), 2)

        if config.technical_quality_score is None:
            config.technical_quality_score = round(random.uniform(0.5, 0.95), 2)

        # Generate recommendations if not provided
        if not config.recommendations:
            config.recommendations = cls._generate_recommendations(config.overall_score)

        # Generate issues if not provided
        if not config.issues:
            config.issues = cls._generate_quality_issues(config.overall_score)

        # Generate processing time if not provided
        if config.processing_time_ms is None:
            config.processing_time_ms = random.randint(500, 5000)

        # Generate timestamp
        created_at = config.created_at or datetime.utcnow()

        # Create quality assessment instance
        assessment = QualityMetric(
            id=str(uuid.uuid4()),
            document_id=config.document_id or str(uuid.uuid4()),
            overall_score=config.overall_score,
            readability_score=config.readability_score,
            content_quality_score=config.content_quality_score,
            technical_quality_score=config.technical_quality_score,
            recommendations=config.recommendations,
            issues=config.issues,
            processing_time_ms=config.processing_time_ms,
            created_at=created_at
        )

        return assessment

    @classmethod
    def create_document_with_job_and_quality(
        cls,
        doc_config: Optional[DocumentConfig] = None,
        job_config: Optional[ProcessingJobConfig] = None,
        qa_config: Optional[QualityMetricConfig] = None
    ) -> Dict[str, Any]:
        """
        Create a complete document with associated processing job and quality assessment

        Args:
            doc_config: Document configuration
            job_config: Processing job configuration
            qa_config: Quality assessment configuration

        Returns:
            Dictionary containing document, job, and quality assessment
        """
        # Create document
        document = cls.create_document(doc_config)

        # Create processing job linked to document
        if job_config is None:
            job_config = ProcessingJobConfig()
        job_config.document_id = document.id
        job_config.organization_id = document.organization_id

        # Adjust job status based on document processing status
        if document.processing_status == ProcessingStatus.UPLOADED:
            job_config.status = JobStatus.PENDING
        elif document.processing_status == ProcessingStatus.PROCESSING:
            job_config.status = JobStatus.IN_PROGRESS
        elif document.processing_status == ProcessingStatus.INDEXED:
            job_config.status = JobStatus.COMPLETED
        elif document.processing_status == ProcessingStatus.FAILED:
            job_config.status = JobStatus.FAILED
            job_config.error_message = document.processing_error or "Processing failed"

        processing_job = cls.create_processing_job(job_config)

        # Create quality assessment if document is processed
        quality_assessment = None
        if document.processing_status == ProcessingStatus.INDEXED:
            if qa_config is None:
                qa_config = QualityMetricConfig()
            qa_config.document_id = document.id
            quality_assessment = cls.create_quality_assessment(qa_config)

        return {
            'document': document,
            'processing_job': processing_job,
            'quality_assessment': quality_assessment
        }

    @classmethod
    def _generate_title(cls, file_type: DocumentType) -> str:
        """Generate a realistic document title based on file type"""
        title_templates = {
            DocumentType.PDF: [
                "Annual Report {year}",
                "Quarterly Financial Statement Q{quarter}",
                "Technical Documentation: {topic}",
                "Product Specifications {product}",
                "Research Paper: {subject}",
                "Contract Agreement {party}",
                "Invoice #{number}",
                "Meeting Minutes {date}",
                "Project Proposal {project}",
                "User Manual {product}"
            ],
            DocumentType.TEXT: [
                "Meeting Notes {date}",
                "Project Timeline {project}",
                "Code Documentation {module}",
                "Configuration File {service}",
                "README {project}",
                "Change Log {version}",
                "API Documentation {service}",
                "Installation Guide",
                "Troubleshooting Guide",
                "Release Notes {version}"
            ],
            DocumentType.JPG: [
                "Product Screenshot {view}",
                "Architecture Diagram {system}",
                "Process Flowchart {process}",
                "User Interface Mockup {screen}",
                "Chart {type}",
                "Infographic {topic}",
                "Photo {subject}",
                "Diagram {type}",
                "Illustration {subject}",
                "Design Mockup {component}"
            ],
            DocumentType.PNG: [
                "Logo {brand}",
                "Icon {type}",
                "Screenshot {application}",
                "Chart {type}",
                "Diagram {system}",
                "Mockup {screen}",
                "Illustration {subject}",
                "Graphic {type}",
                "Image {description}",
                "Visual {type}"
            ],
            DocumentType.MP3: [
                "Meeting Recording {date}",
                "Podcast Episode {number}",
                "Interview {guest}",
                "Presentation Audio {topic}",
                "Training Session {subject}",
                "Webinar Recording {topic}",
                "Audio Notes {date}",
                "Voice Memo {subject}",
                "Sound Effect {type}",
                "Music Track {title}"
            ],
            DocumentType.MP4: [
                "Product Demo {product}",
                "Training Video {topic}",
                "Presentation Recording {event}",
                "Tutorial {subject}",
                "Webinar Recording {topic}",
                "Meeting Recording {date}",
                "Screen Recording {task}",
                "Video Tutorial {lesson}",
                "Demo {feature}",
                "Explainer Video {topic}"
            ]
        }

        templates = title_templates.get(file_type, title_templates[DocumentType.PDF])
        template = random.choice(templates)

        # Fill in template variables
        replacements = {
            '{year}': str(random.randint(2020, 2024)),
            '{quarter}': str(random.randint(1, 4)),
            '{topic}': fake.catch_phrase(),
            '{product}': fake.word().capitalize(),
            '{subject}': fake.catch_phrase(),
            '{party}': fake.company(),
            '{number}': str(random.randint(1000, 9999)),
            '{date}': fake.date(pattern='%Y-%m-%d'),
            '{project}': fake.catch_phrase(),
            '{view}': fake.word(),
            '{system}': f"{fake.word().capitalize()} System",
            '{process}': f"{fake.word().capitalize()} Process",
            '{screen}': f"{fake.word().capitalize()} Screen",
            '{type}': fake.word(),
            '{brand}': fake.company(),
            '{module}': fake.word(),
            '{service}': f"{fake.word().capitalize()} Service",
            '{version}': f"v{random.randint(1, 10)}.{random.randint(0, 9)}",
            '{application}': fake.word().capitalize(),
            '{guest}': fake.name(),
            '{event}': fake.catch_phrase(),
            '{subject}': fake.word(),
            '{component}': fake.word(),
            '{lesson}': f"Lesson {random.randint(1, 20)}",
            '{feature}': fake.word(),
            '{task}': fake.catch_phrase(),
            '{title}': fake.catch_phrase(),
            '{description}': fake.sentence()
        }

        title = template
        for placeholder, value in replacements.items():
            title = title.replace(placeholder, value)

        return title

    @classmethod
    def _generate_filename(cls, title: str, file_type: DocumentType) -> str:
        """Generate a realistic filename from title"""
        # Clean title for filename
        clean_title = title.lower().replace(' ', '_').replace(':', '').replace('/', '_')
        clean_title = ''.join(c for c in clean_title if c.isalnum() or c in '_-')

        # Limit length
        if len(clean_title) > 50:
            clean_title = clean_title[:47] + '...'

        # Get appropriate extension
        extensions = cls.FILE_TYPE_CONFIGS[file_type]['extensions']
        extension = random.choice(extensions)

        # Add random suffix for uniqueness
        suffix = random.randint(1, 9999)

        return f"{clean_title}_{suffix}{extension}"

    @classmethod
    def _generate_custom_metadata(cls, file_type: DocumentType) -> Dict[str, Any]:
        """Generate realistic custom metadata based on file type"""
        base_metadata = {
            'upload_source': random.choice(['web', 'api', 'mobile', 'email']),
            'upload_device': random.choice(['desktop', 'mobile', 'tablet']),
            'client_version': f"v{random.randint(1, 3)}.{random.randint(0, 9)}.{random.randint(0, 99)}",
            'timezone': fake.timezone(),
            'language': random.choice(['en', 'es', 'fr', 'de', 'ja', 'zh'])
        }

        type_specific_metadata = {
            DocumentType.PDF: {
                'pdf_version': random.choice(['1.4', '1.5', '1.6', '1.7', '2.0']),
                'has_forms': random.choice([True, False]),
                'has_annotations': random.choice([True, False]),
                'is_encrypted': random.choice([True, False]),
                'creation_tool': random.choice(['Adobe Acrobat', 'Microsoft Word', 'Google Docs', 'LibreOffice'])
            },
            DocumentType.TEXT: {
                'encoding': random.choice(['UTF-8', 'UTF-16', 'ISO-8859-1', 'ASCII']),
                'line_endings': random.choice(['\\n', '\\r\\n', '\\r']),
                'word_count': random.randint(100, 50000),
                'character_count': random.randint(500, 200000)
            },
            DocumentType.JPG: {
                'camera_make': random.choice(['Canon', 'Nikon', 'Sony', 'Apple', 'Samsung']),
                'camera_model': f"{fake.word()} {random.randint(1000, 9999)}",
                'resolution': f"{random.choice([1920, 2560, 3840, 4096])}x{random.choice([1080, 1440, 2160, 3072])}",
                'color_space': random.choice(['sRGB', 'Adobe RGB', 'ProPhoto RGB']),
                'has_exif': random.choice([True, False])
            },
            DocumentType.PNG: {
                'compression_level': random.randint(1, 9),
                'has_transparency': random.choice([True, False]),
                'bit_depth': random.choice([8, 16, 24, 32]),
                'color_type': random.choice(['RGB', 'RGBA', 'Grayscale', 'Indexed'])
            },
            DocumentType.MP3: {
                'bitrate': random.choice([128, 192, 256, 320]),
                'sample_rate': random.choice([44100, 48000]),
                'duration_seconds': random.randint(30, 3600),
                'has_album_art': random.choice([True, False]),
                'codec': random.choice(['MP3', 'AAC'])
            },
            DocumentType.MP4: {
                'resolution': random.choice(['720p', '1080p', '4K']),
                'frame_rate': random.choice([24, 30, 60]),
                'duration_seconds': random.randint(60, 7200),
                'codec': random.choice(['H.264', 'H.265', 'VP9']),
                'has_audio': random.choice([True, False]),
                'file_size_mb': random.randint(10, 1000)
            }
        }

        metadata = {**base_metadata, **type_specific_metadata.get(file_type, {})}
        return metadata

    @classmethod
    def _generate_job_parameters(cls, job_type: JobType) -> Dict[str, Any]:
        """Generate realistic job parameters based on job type"""
        base_params = {
            'retry_count': random.randint(0, 3),
            'timeout_seconds': random.randint(300, 1800),
            'worker_id': f"worker-{random.randint(1, 10):03d}",
            'queue_name': random.choice(['high_priority', 'normal_priority', 'low_priority'])
        }

        type_specific_params = {
            JobType.DOCUMENT_INGESTION: {
                'enable_ocr': random.choice([True, False]),
                'enable_entity_extraction': random.choice([True, False]),
                'enable_embedding_generation': random.choice([True, False]),
                'enable_quality_check': random.choice([True, False]),
                'ocr_languages': random.choice(['en', 'en,es', 'en,fr', 'auto']),
                'extract_images': random.choice([True, False]),
                'chunk_size': random.randint(500, 2000),
                'chunk_overlap': random.randint(50, 200)
            },
            JobType.QUALITY_ASSESSMENT: {
                'check_readability': True,
                'check_content_quality': True,
                'check_technical_quality': True,
                'generate_recommendations': True,
                'assessment_model': random.choice(['baseline', 'advanced', 'ml_enhanced']),
                'include_detailed_analysis': random.choice([True, False])
            },
            JobType.INDEXING: {
                'index_type': random.choice(['vector', 'hybrid', 'full_text']),
                'embedding_model': random.choice(['text-embedding-ada-002', 'sentence-transformers', 'custom']),
                'vector_dimension': random.choice([768, 1024, 1536]),
                'index_name': f"index_{uuid.uuid4().hex[:8]}",
                'update_existing': random.choice([True, False])
            }
        }

        return {**base_params, **type_specific_params.get(job_type, {})}

    @classmethod
    def _generate_job_config(cls, job_type: JobType) -> Dict[str, Any]:
        """Generate realistic job configuration based on job type"""
        base_config = {
            'max_retries': random.randint(1, 5),
            'priority_weight': random.randint(1, 10),
            'resource_allocation': random.choice(['low', 'medium', 'high']),
            'monitoring_enabled': True,
            'logging_level': random.choice(['DEBUG', 'INFO', 'WARNING', 'ERROR'])
        }

        type_specific_config = {
            JobType.DOCUMENT_INGESTION: {
                'ocr_engine': random.choice(['tesseract', 'google_vision', 'azure_ocr']),
                'entity_extraction_model': random.choice(['spacy', 'stanza', 'custom']),
                'chunking_strategy': random.choice(['fixed_size', 'semantic', 'recursive']),
                'enable_async_processing': random.choice([True, False]),
                'batch_size': random.randint(1, 10)
            },
            JobType.QUALITY_ASSESSMENT: {
                'quality_threshold': random.uniform(0.5, 0.8),
                'detailed_logging': random.choice([True, False]),
                'cache_results': random.choice([True, False]),
                'parallel_assessment': random.choice([True, False])
            },
            JobType.INDEXING: {
                'index_strategy': random.choice(['create', 'update', 'append']),
                'bulk_size': random.randint(100, 1000),
                'refresh_interval': random.choice(['1s', '5s', '30s']),
                'number_of_shards': random.randint(1, 5),
                'number_of_replicas': random.randint(0, 2)
            }
        }

        return {**base_config, **type_specific_config.get(job_type, {})}

    @classmethod
    def _generate_recommendations(cls, overall_score: float) -> List[str]:
        """Generate realistic quality improvement recommendations"""
        all_recommendations = [
            "Improve document structure with clear headings",
            "Add more descriptive section titles",
            "Include a comprehensive summary or abstract",
            "Enhance readability with shorter paragraphs",
            "Add relevant examples and case studies",
            "Include proper citations and references",
            "Improve formatting consistency",
            "Add visual elements to support text content",
            "Include a table of contents for longer documents",
            "Ensure consistent terminology throughout",
            "Add metadata and document properties",
            "Improve language clarity and reduce jargon",
            "Include contact information or author details",
            "Add revision history or version information",
            "Include glossary for technical terms"
        ]

        # Number of recommendations based on score (lower score = more recommendations)
        num_recommendations = max(1, int((1.0 - overall_score) * 10))

        return random.sample(all_recommendations, min(num_recommendations, len(all_recommendations)))

    @classmethod
    def _generate_quality_issues(cls, overall_score: float) -> List[Dict[str, Any]]:
        """Generate realistic quality issues based on score"""
        issue_templates = [
            {
                'type': 'readability',
                'severity': 'medium',
                'description': 'Long paragraphs reduce readability',
                'suggestion': 'Break up long paragraphs into shorter sections'
            },
            {
                'type': 'readability',
                'severity': 'low',
                'description': 'Inconsistent heading formatting',
                'suggestion': 'Use consistent heading styles throughout the document'
            },
            {
                'type': 'content_quality',
                'severity': 'high',
                'description': 'Missing document summary or abstract',
                'suggestion': 'Add a concise summary at the beginning'
            },
            {
                'type': 'content_quality',
                'severity': 'medium',
                'description': 'Insufficient examples or illustrations',
                'suggestion': 'Add relevant examples to support key points'
            },
            {
                'type': 'technical_quality',
                'severity': 'low',
                'description': 'Missing document metadata',
                'suggestion': 'Add title, author, and creation date metadata'
            },
            {
                'type': 'technical_quality',
                'severity': 'medium',
                'description': 'Poor image resolution detected',
                'suggestion': 'Replace images with higher resolution versions'
            },
            {
                'type': 'structure',
                'severity': 'high',
                'description': 'Document lacks logical structure',
                'suggestion': 'Reorganize content with clear sections and subsections'
            },
            {
                'type': 'language',
                'severity': 'medium',
                'description': 'Inconsistent terminology usage',
                'suggestion': 'Create and use a consistent terminology guide'
            }
        ]

        # Number of issues based on score (lower score = more issues)
        num_issues = max(1, int((1.0 - overall_score) * 8))

        selected_issues = random.sample(issue_templates, min(num_issues, len(issue_templates)))

        # Add unique IDs to issues
        for issue in selected_issues:
            issue['id'] = str(uuid.uuid4())
            issue['location'] = {
                'page': random.randint(1, 20),
                'section': f"Section {random.randint(1, 10)}"
            }

        return selected_issues


# Convenience functions for common test scenarios
def create_sample_document_collection(org_id: str, user_id: str, count: int = 10) -> List[Document]:
    """Create a sample collection of documents for testing"""
    config = DocumentConfig(
        organization_id=org_id,
        uploaded_by_user_id=user_id,
        is_public=False,
        is_deleted=False
    )
    return DocumentFactory.create_batch_documents(count, config)


def create_document_processing_pipeline(doc_id: str, org_id: str, user_id: str) -> Dict[str, Any]:
    """Create a complete document processing pipeline for testing"""
    doc_config = DocumentConfig(
        id=doc_id,
        organization_id=org_id,
        uploaded_by_user_id=user_id,
        processing_status=ProcessingStatus.PROCESSING
    )

    job_config = ProcessingJobConfig(
        document_id=doc_id,
        organization_id=org_id,
        created_by_user_id=user_id,
        status=JobStatus.IN_PROGRESS,
        completed_steps=3,
        total_steps=8
    )

    return DocumentFactory.create_document_with_job_and_quality(doc_config, job_config)


def create_failed_document_processing(doc_id: str, org_id: str, user_id: str) -> Dict[str, Any]:
    """Create a failed document processing scenario for testing"""
    doc_config = DocumentConfig(
        id=doc_id,
        organization_id=org_id,
        uploaded_by_user_id=user_id,
        processing_status=ProcessingStatus.FAILED,
        processing_error="OCR processing failed due to corrupted file"
    )

    job_config = ProcessingJobConfig(
        document_id=doc_id,
        organization_id=org_id,
        created_by_user_id=user_id,
        status=JobStatus.FAILED,
        error_message="OCR processing failed: Unable to process corrupted PDF file",
        completed_steps=2,
        total_steps=8
    )

    return DocumentFactory.create_document_with_job_and_quality(doc_config, job_config)