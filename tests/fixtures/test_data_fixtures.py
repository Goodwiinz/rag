"""
Test Data Fixtures for Multimodal Enterprise RAG System
Provides comprehensive mock data generation utilities for testing
"""

import json
import uuid
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import faker
from io import BytesIO


class DocumentType(Enum):
    TEXT = "text"
    PDF = "pdf"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"

class ProcessingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class SearchType(Enum):
    HYBRID = "hybrid"
    VECTOR = "vector"
    FULLTEXT = "fulltext"
    GRAPH = "graph"

class UserRole(Enum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"

class EntityType(Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    TECHNOLOGY = "technology"
    CONCEPT = "concept"
    DATE = "date"
    PRODUCT = "product"

# Initialize faker for realistic data generation
fake = faker.Faker()


@dataclass
class UserFixture:
    """User data fixture for testing"""
    id: str
    email: str
    first_name: str
    last_name: str
    organization_id: str
    role: str
    is_active: bool
    created_at: str
    updated_at: str
    hashed_password: str = "hashed_password"

    @classmethod
    def create(cls, **overrides) -> 'UserFixture':
        """Create a user fixture with optional overrides"""
        data = {
            'id': str(uuid.uuid4()),
            'email': fake.email(),
            'first_name': fake.first_name(),
            'last_name': fake.last_name(),
            'organization_id': str(uuid.uuid4()),
            'role': UserRole.USER.value,
            'is_active': True,
            'created_at': fake.date_time_between(start_date='-2y', end_date='now').isoformat(),
            'updated_at': fake.date_time_between(start_date='-1y', end_date='now').isoformat(),
        }
        data.update(overrides)
        return cls(**data)

    @classmethod
    def create_admin(cls, **overrides) -> 'UserFixture':
        """Create an admin user fixture"""
        return cls.create(role=UserRole.ADMIN.value, **overrides)

    @classmethod
    def create_batch(cls, count: int, **common_overrides) -> List['UserFixture']:
        """Create multiple user fixtures"""
        return [cls.create(**common_overrides) for _ in range(count)]


@dataclass
class OrganizationFixture:
    """Organization data fixture for testing"""
    id: str
    name: str
    description: str
    industry: str
    size: str
    website: str
    created_at: str
    updated_at: str

    @classmethod
    def create(cls, **overrides) -> 'OrganizationFixture':
        """Create an organization fixture with optional overrides"""
        data = {
            'id': str(uuid.uuid4()),
            'name': fake.company(),
            'description': fake.catch_phrase(),
            'industry': random.choice(['Technology', 'Healthcare', 'Finance', 'Education', 'Manufacturing']),
            'size': random.choice(['1-10', '11-50', '51-200', '201-500', '500+']),
            'website': fake.url(),
            'created_at': fake.date_time_between(start_date='-2y', end_date='now').isoformat(),
            'updated_at': fake.date_time_between(start_date='-1y', end_date='now').isoformat(),
        }
        data.update(overrides)
        return cls(**data)


@dataclass
class DocumentFixture:
    """Document data fixture for testing"""
    id: str
    title: str
    filename: str
    document_type: str
    file_size_bytes: int
    file_size_mb: float
    mime_type: str
    processing_status: str
    tags: List[str]
    is_public: bool
    content_preview: Optional[str]
    content_summary: Optional[str]
    content_text: Optional[str]
    metadata: Dict[str, Any]
    uploaded_by_user_id: str
    organization_id: str
    created_at: str
    updated_at: str
    processing_started_at: Optional[str]
    processing_completed_at: Optional[str]
    processing_error: Optional[str]
    processing_retry_count: int

    @classmethod
    def create(cls, **overrides) -> 'DocumentFixture':
        """Create a document fixture with optional overrides"""
        doc_type = random.choice(list(DocumentType))
        file_size = random.randint(1024, 50 * 1024 * 1024)  # 1KB to 50MB

        mime_types = {
            DocumentType.TEXT: "text/plain",
            DocumentType.PDF: "application/pdf",
            DocumentType.IMAGE: random.choice(["image/jpeg", "image/png"]),
            DocumentType.AUDIO: random.choice(["audio/mpeg", "audio/wav"]),
            DocumentType.VIDEO: random.choice(["video/mp4", "video/avi"])
        }

        content_samples = {
            DocumentType.TEXT: fake.paragraph(nb_sentences=10),
            DocumentType.PDF: fake.paragraph(nb_sentences=15),
            DocumentType.IMAGE: "Image content with OCR text: " + fake.paragraph(nb_sentences=5),
            DocumentType.AUDIO: "Transcribed audio content: " + fake.paragraph(nb_sentences=8),
            DocumentType.VIDEO: "Video transcription: " + fake.paragraph(nb_sentences=12)
        }

        titles = {
            DocumentType.TEXT: fake.catch_phrase(),
            DocumentType.PDF: f"{random.choice(['Research', 'Technical', 'Business', 'Scientific'])} Paper on {fake.job()}",
            DocumentType.IMAGE: f"{random.choice(['Diagram', 'Chart', 'Photo', 'Illustration'])} of {fake.word()}",
            DocumentType.AUDIO: f"{random.choice(['Interview', 'Presentation', 'Podcast', 'Lecture'])} Recording",
            DocumentType.VIDEO: f"{random.choice(['Tutorial', 'Demo', 'Webinar', 'Meeting'])} Video"
        }

        processing_status = random.choice(list(ProcessingStatus))
        now = datetime.utcnow()

        processing_times = {
            ProcessingStatus.COMPLETED: {
                'processing_started_at': (now - timedelta(minutes=random.randint(1, 30))).isoformat(),
                'processing_completed_at': (now - timedelta(minutes=random.randint(0, 5))).isoformat(),
                'processing_error': None
            },
            ProcessingStatus.FAILED: {
                'processing_started_at': (now - timedelta(minutes=random.randint(1, 20))).isoformat(),
                'processing_completed_at': None,
                'processing_error': random.choice([
                    "File format not supported",
                    "OCR processing failed",
                    "Insufficient memory",
                    "Network timeout during processing"
                ])
            },
            ProcessingStatus.PROCESSING: {
                'processing_started_at': (now - timedelta(minutes=random.randint(1, 10))).isoformat(),
                'processing_completed_at': None,
                'processing_error': None
            },
            ProcessingStatus.PENDING: {
                'processing_started_at': None,
                'processing_completed_at': None,
                'processing_error': None
            }
        }

        processing_data = processing_times[processing_status]

        data = {
            'id': str(uuid.uuid4()),
            'title': titles[doc_type],
            'filename': f"{fake.word().lower()}_{random.randint(1000, 9999)}.{doc_type.value}",
            'document_type': doc_type.value,
            'file_size_bytes': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'mime_type': mime_types[doc_type],
            'processing_status': processing_status.value,
            'tags': random.sample([
                'research', 'technical', 'business', 'ai', 'machine learning', 'data',
                'analysis', 'report', 'presentation', 'documentation', 'guide',
                'tutorial', 'reference', 'case study', 'white paper'
            ], random.randint(2, 5)),
            'is_public': random.choice([True, False]),
            'content_preview': content_samples[doc_type][:200] + "...",
            'content_summary': fake.paragraph(nb_sentences=3),
            'content_text': content_samples[doc_type] if random.random() > 0.3 else None,
            'metadata': {
                'page_count': random.randint(1, 100) if doc_type == DocumentType.PDF else None,
                'duration_seconds': random.randint(60, 3600) if doc_type in [DocumentType.AUDIO, DocumentType.VIDEO] else None,
                'resolution': f"{random.choice([720, 1080, 1920])}p" if doc_type == DocumentType.VIDEO else None,
                'word_count': random.randint(500, 5000) if doc_type in [DocumentType.TEXT, DocumentType.PDF] else None,
                'author': fake.name(),
                'language': random.choice(['English', 'Spanish', 'French', 'German']),
                'creation_date': fake.date_between(start_date='-2y', end_date='now').isoformat()
            },
            'uploaded_by_user_id': str(uuid.uuid4()),
            'organization_id': str(uuid.uuid4()),
            'created_at': fake.date_time_between(start_date='-30d', end_date='now').isoformat(),
            'updated_at': fake.date_time_between(start_date='-7d', end_date='now').isoformat(),
            'processing_retry_count': random.randint(0, 3),
            **processing_data
        }
        data.update(overrides)
        return cls(**data)

    @classmethod
    def create_batch(cls, count: int, **common_overrides) -> List['DocumentFixture']:
        """Create multiple document fixtures"""
        return [cls.create(**common_overrides) for _ in range(count)]

    @classmethod
    def create_by_type(cls, doc_type: DocumentType, **overrides) -> 'DocumentFixture':
        """Create a document fixture of specific type"""
        return cls.create(document_type=doc_type.value, **overrides)


@dataclass
class SearchQueryFixture:
    """Search query data fixture for testing"""
    id: str
    query: str
    search_type: str
    max_results: int
    filters: Dict[str, Any]
    user_id: str
    organization_id: str
    created_at: str
    total_results: int
    execution_time_ms: int

    @classmethod
    def create(cls, **overrides) -> 'SearchQueryFixture':
        """Create a search query fixture with optional overrides"""
        search_queries = [
            "machine learning algorithms",
            "natural language processing",
            "computer vision applications",
            "deep neural networks",
            "artificial intelligence ethics",
            "data preprocessing techniques",
            "model evaluation metrics",
            "feature engineering methods",
            "reinforcement learning",
            "supervised learning",
            "unsupervised learning",
            "transfer learning",
            "generative AI models",
            "large language models",
            "transformer architecture",
            "convolutional neural networks",
            "recurrent neural networks",
            "gradient descent optimization",
            "backpropagation algorithm",
            "overfitting prevention",
            "cross validation techniques",
            "ensemble methods",
            "random forest",
            "support vector machines",
            "clustering algorithms",
            "dimensionality reduction",
            "principal component analysis",
            "time series analysis",
            "anomaly detection",
            "recommendation systems",
            "knowledge graphs"
        ]

        data = {
            'id': str(uuid.uuid4()),
            'query': random.choice(search_queries),
            'search_type': random.choice([t.value for t in SearchType]),
            'max_results': random.randint(5, 50),
            'filters': {
                'document_types': random.sample(['text', 'pdf', 'image', 'audio', 'video'], random.randint(1, 3)),
                'tags': random.sample(['ai', 'research', 'technical', 'business'], random.randint(0, 2)) or None,
                'date_range': {
                    'start_date': fake.date_between(start_date='-1y', end_date='-1m').isoformat(),
                    'end_date': fake.date_between(start_date='-1m', end_date='now').isoformat()
                } if random.random() > 0.7 else None
            },
            'user_id': str(uuid.uuid4()),
            'organization_id': str(uuid.uuid4()),
            'created_at': fake.date_time_between(start_date='-7d', end_date='now').isoformat(),
            'total_results': random.randint(0, 100),
            'execution_time_ms': random.randint(50, 3000)
        }
        data.update(overrides)
        return cls(**data)


@dataclass
class SearchResultFixture:
    """Search result data fixture for testing"""
    document_id: str
    title: str
    content_preview: str
    score: float
    highlights: List[str]
    document_type: str
    metadata: Dict[str, Any]
    similarity_score: Optional[float] = None

    @classmethod
    def create(cls, **overrides) -> 'SearchResultFixture':
        """Create a search result fixture with optional overrides"""
        data = {
            'document_id': str(uuid.uuid4()),
            'title': fake.catch_phrase(),
            'content_preview': fake.paragraph(nb_sentences=3),
            'score': round(random.uniform(0.1, 1.0), 3),
            'highlights': [
                f"Matched term in context: {fake.sentence()}",
                f"Relevant excerpt: {fake.sentence()}"
            ],
            'document_type': random.choice([t.value for t in DocumentType]),
            'metadata': {
                'page_number': random.randint(1, 50) if random.random() > 0.5 else None,
                'section_title': fake.sentence() if random.random() > 0.7 else None,
                'author': fake.name() if random.random() > 0.6 else None
            },
            'similarity_score': round(random.uniform(0.0, 1.0), 3) if random.random() > 0.5 else None
        }
        data.update(overrides)
        return cls(**data)


@dataclass
class EntityFixture:
    """Knowledge graph entity data fixture for testing"""
    id: str
    name: str
    type: str
    confidence: float
    mentions: List[Dict[str, Any]]
    metadata: Dict[str, Any]

    @classmethod
    def create(cls, **overrides) -> 'EntityFixture':
        """Create an entity fixture with optional overrides"""
        entity_data = {
            EntityType.PERSON: {
                'names': [fake.name(), fake.name(), fake.name()],
                'metadata_keys': ['title', 'organization', 'expertise']
            },
            EntityType.ORGANIZATION: {
                'names': [fake.company(), fake.company(), fake.company()],
                'metadata_keys': ['industry', 'founded', 'headquarters']
            },
            EntityType.LOCATION: {
                'names': [fake.city(), fake.country(), fake.state()],
                'metadata_keys': ['country', 'population', 'coordinates']
            },
            EntityType.TECHNOLOGY: {
                'names': ['Machine Learning', 'Neural Networks', 'Natural Language Processing', 'Computer Vision', 'Deep Learning'],
                'metadata_keys': ['category', 'year', 'creator']
            },
            EntityType.CONCEPT: {
                'names': ['Algorithm', 'Data Science', 'Artificial Intelligence', 'Big Data', 'Cloud Computing'],
                'metadata_keys': ['domain', 'definition', 'applications']
            }
        }

        entity_type = random.choice(list(EntityType))
        type_data = entity_data[entity_type]
        name = random.choice(type_data['names'])

        data = {
            'id': str(uuid.uuid4()),
            'name': name,
            'type': entity_type.value,
            'confidence': round(random.uniform(0.5, 1.0), 3),
            'mentions': [
                {
                    'document_id': str(uuid.uuid4()),
                    'text': f"...{name} mentioned in {fake.sentence()}...",
                    'position': random.randint(0, 1000),
                    'confidence': round(random.uniform(0.7, 1.0), 3)
                }
                for _ in range(random.randint(1, 5))
            ],
            'metadata': {
                key: fake.word() for key in random.sample(type_data['metadata_keys'], random.randint(1, 3))
            }
        }
        data.update(overrides)
        return cls(**data)

    @classmethod
    def create_by_type(cls, entity_type: EntityType, **overrides) -> 'EntityFixture':
        """Create an entity fixture of specific type"""
        return cls.create(type=entity_type.value, **overrides)


@dataclass
class RelationshipFixture:
    """Knowledge graph relationship data fixture for testing"""
    id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    confidence: float
    metadata: Dict[str, Any]

    @classmethod
    def create(cls, **overrides) -> 'RelationshipFixture':
        """Create a relationship fixture with optional overrides"""
        relationship_types = [
            'works_for', 'collaborates_with', 'located_in', 'founded_by',
            'uses', 'mentions', 'relates_to', 'part_of', 'specializes_in',
            'employs', 'invests_in', 'partners_with', 'competes_with'
        ]

        data = {
            'id': str(uuid.uuid4()),
            'source_entity_id': str(uuid.uuid4()),
            'target_entity_id': str(uuid.uuid4()),
            'relationship_type': random.choice(relationship_types),
            'confidence': round(random.uniform(0.3, 1.0), 3),
            'metadata': {
                'source_document': str(uuid.uuid4()),
                'extraction_date': fake.date_time_this_year().isoformat(),
                'context': fake.sentence()
            }
        }
        data.update(overrides)
        return cls(**data)


class FileFixture:
    """File generation utilities for testing"""

    @staticmethod
    def create_text_file(content: Optional[str] = None, filename: Optional[str] = None) -> tuple:
        """Create a text file for testing"""
        if content is None:
            content = fake.paragraph(nb_sentences=random.randint(5, 20))
        if filename is None:
            filename = f"test_document_{random.randint(1000, 9999)}.txt"

        return (filename, BytesIO(content.encode()), "text/plain")

    @staticmethod
    def create_pdf_file(filename: Optional[str] = None) -> tuple:
        """Create a mock PDF file for testing"""
        if filename is None:
            filename = f"test_document_{random.randint(1000, 9999)}.pdf"

        # Mock PDF content (simplified)
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        return (filename, BytesIO(pdf_content), "application/pdf")

    @staticmethod
    def create_image_file(image_type: str = "jpeg", filename: Optional[str] = None) -> tuple:
        """Create a mock image file for testing"""
        if filename is None:
            ext = "jpg" if image_type == "jpeg" else image_type
            filename = f"test_image_{random.randint(1000, 9999)}.{ext}"

        # Mock image headers
        image_headers = {
            "jpeg": b"\xff\xd8\xff\xe0\x00\x10JFIF",
            "png": b"\x89PNG\r\n\x1a\n",
            "gif": b"GIF87a"
        }

        content = image_headers.get(image_type.lower(), b"MOCK_IMAGE")
        content += b"\x00" * random.randint(1024, 10240)  # Add some size

        mime_type = f"image/{image_type.lower()}"
        return (filename, BytesIO(content), mime_type)

    @staticmethod
    def create_audio_file(audio_type: str = "mpeg", filename: Optional[str] = None) -> tuple:
        """Create a mock audio file for testing"""
        if filename is None:
            ext = "mp3" if audio_type == "mpeg" else audio_type
            filename = f"test_audio_{random.randint(1000, 9999)}.{ext}"

        # Mock audio headers
        audio_headers = {
            "mpeg": b"ID3\x04\x00\x00\x00\x00\x00\x00",
            "wav": b"RIFF\x24\x08\x00\x00WAVE"
        }

        content = audio_headers.get(audio_type.lower(), b"MOCK_AUDIO")
        content += b"\x00" * random.randint(10240, 102400)  # Add some size

        mime_type = f"audio/{audio_type.lower()}"
        return (filename, BytesIO(content), mime_type)

    @staticmethod
    def create_video_file(filename: Optional[str] = None) -> tuple:
        """Create a mock video file for testing"""
        if filename is None:
            filename = f"test_video_{random.randint(1000, 9999)}.mp4"

        # Mock video header
        content = b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00"
        content += b"\x00" * random.randint(102400, 1024000)  # Add some size

        return (filename, BytesIO(content), "video/mp4")


class MockDataGenerator:
    """Centralized mock data generation utilities"""

    @staticmethod
    def generate_complete_dataset(num_users: int = 10, num_documents: int = 50,
                               num_searches: int = 100, num_entities: int = 30) -> Dict[str, List]:
        """Generate a complete dataset for testing"""

        # Create organizations
        organizations = [OrganizationFixture.create() for _ in range(random.randint(3, 8))]

        # Create users
        users = []
        for i in range(num_users):
            org = random.choice(organizations)
            users.append(UserFixture.create(
                organization_id=org.id,
                role=UserRole.ADMIN.value if i == 0 else UserRole.USER.value
            ))

        # Create documents
        documents = []
        for i in range(num_documents):
            user = random.choice(users)
            documents.append(DocumentFixture.create(
                uploaded_by_user_id=user.id,
                organization_id=user.organization_id
            ))

        # Create search queries
        searches = []
        for i in range(num_searches):
            user = random.choice(users)
            searches.append(SearchQueryFixture.create(
                user_id=user.id,
                organization_id=user.organization_id
            ))

        # Create entities
        entities = [EntityFixture.create() for _ in range(num_entities)]

        # Create relationships
        relationships = [RelationshipFixture.create() for _ in range(random.randint(20, 50))]

        return {
            'organizations': organizations,
            'users': users,
            'documents': documents,
            'searches': searches,
            'entities': entities,
            'relationships': relationships
        }

    @staticmethod
    def export_fixtures_to_json(fixtures: Dict[str, List], output_dir: str = "/tmp/test_fixtures"):
        """Export fixtures to JSON files for reuse"""
        import os
        os.makedirs(output_dir, exist_ok=True)

        for fixture_type, fixture_list in fixtures.items():
            filename = os.path.join(output_dir, f"{fixture_type}.json")
            with open(filename, 'w') as f:
                json.dump([asdict(fixture) if hasattr(fixture, '__dict__') else fixture
                          for fixture in fixture_list], f, indent=2, default=str)

    @staticmethod
    def load_fixtures_from_json(fixture_type: str, input_dir: str = "/tmp/test_fixtures") -> List[Dict]:
        """Load fixtures from JSON files"""
        import os
        filename = os.path.join(input_dir, f"{fixture_type}.json")

        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return []

    @staticmethod
    def create_test_scenarios() -> Dict[str, Any]:
        """Create predefined test scenarios"""
        return {
            'basic_search': {
                'query': 'machine learning',
                'search_type': 'hybrid',
                'max_results': 10,
                'expected_results': 5
            },
            'complex_search': {
                'query': 'deep neural networks computer vision',
                'search_type': 'hybrid',
                'max_results': 20,
                'filters': {
                    'document_types': ['pdf', 'text'],
                    'tags': ['research', 'technical']
                },
                'enable_facets': True
            },
            'user_workflow': {
                'steps': ['register', 'upload_document', 'search', 'get_results'],
                'test_data': {
                    'user_email': 'test@example.com',
                    'document_title': 'Test Document',
                    'search_query': 'test content'
                }
            },
            'performance_test': {
                'concurrent_users': 50,
                'duration_minutes': 10,
                'operations_per_minute': 100
            }
        }


# Convenience functions for common test data needs
def create_test_user(**overrides) -> UserFixture:
    """Create a single test user"""
    return UserFixture.create(**overrides)

def create_test_document(**overrides) -> DocumentFixture:
    """Create a single test document"""
    return DocumentFixture.create(**overrides)

def create_test_search(**overrides) -> SearchQueryFixture:
    """Create a single test search query"""
    return SearchQueryFixture.create(**overrides)

def create_test_files(count: int = 1) -> List[tuple]:
    """Create multiple test files of different types"""
    file_creators = [
        FileFixture.create_text_file,
        FileFixture.create_pdf_file,
        FileFixture.create_image_file,
        FileFixture.create_audio_file,
        FileFixture.create_video_file
    ]

    files = []
    for _ in range(count):
        creator = random.choice(file_creators)
        files.append(creator())

    return files