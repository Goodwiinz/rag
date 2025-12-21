"""
Test Data Factories for Multi-Agent Search System
Provides factories for generating test data for search-related tests
"""

import factory
import uuid
import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from factory import fuzzy, SubFactory, post_generation

# Import models (adjust paths as needed)
try:
    from src.models.document import Document, DocumentType, ProcessingStatus
    from src.models.processing import ProcessingJob, JobType, JobStatus, JobPriority
    from src.models.user import User, UserRole
except ImportError:
    # Define mock classes if models not available
    class Document:
        pass
    class DocumentType:
        PDF = "pdf"
        TXT = "txt"
        IMAGE = "image"
        AUDIO = "audio"
        VIDEO = "video"
    class ProcessingStatus:
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"


class UserFactory(factory.Factory):
    """Factory for creating test users"""
    class Meta:
        model = User

    id = factory.LazyFunction(uuid.uuid4)
    email = factory.Faker("email")
    hashed_password = factory.Faker("password")
    full_name = factory.Faker("name")
    role = fuzzy.FuzzyChoice(list(UserRole) if 'UserRole' in globals() else ['user', 'admin'])
    is_active = True
    created_at = factory.LazyFunction(datetime.utcnow)


class DocumentFactory(factory.Factory):
    """Factory for creating test documents"""
    class Meta:
        model = Document

    id = factory.LazyFunction(uuid.uuid4)
    title = factory.Faker("sentence", nb_words=6)
    content = factory.Faker("text", max_nb_chars=2000)
    document_type = fuzzy.FuzzyChoice([
        DocumentType.PDF,
        DocumentType.TXT,
        DocumentType.IMAGE,
        DocumentType.AUDIO,
        DocumentType.VIDEO
    ])
    processing_status = fuzzy.FuzzyChoice([
        ProcessingStatus.PENDING,
        ProcessingStatus.PROCESSING,
        ProcessingStatus.COMPLETED,
        ProcessingStatus.FAILED
    ])
    owner_id = factory.LazyFunction(uuid.uuid4)
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)

    @post_generation
    def metadata(obj, create, extracted, **kwargs):
        """Generate metadata for documents"""
        if extracted:
            return extracted

        metadata = {
            "file_size": random.randint(1000, 10000000),
            "page_count": random.randint(1, 100) if obj.document_type == DocumentType.PDF else None,
            "word_count": len(obj.content.split()),
            "language": random.choice(["en", "es", "fr", "de"]),
            "tags": [f"tag_{i}" for i in range(random.randint(1, 5))],
            "author": factory.Faker("name").generate(),
            "created_date": (datetime.utcnow() - timedelta(days=random.randint(0, 365))).isoformat()
        }

        # Add type-specific metadata
        if obj.document_type == DocumentType.IMAGE:
            metadata.update({
                "width": random.randint(640, 3840),
                "height": random.randint(480, 2160),
                "format": random.choice(["JPEG", "PNG", "GIF"])
            })
        elif obj.document_type == DocumentType.AUDIO:
            metadata.update({
                "duration": random.randint(60, 3600),
                "sample_rate": 44100,
                "format": random.choice(["MP3", "WAV", "FLAC"])
            })
        elif obj.document_type == DocumentType.VIDEO:
            metadata.update({
                "duration": random.randint(60, 7200),
                "resolution": random.choice(["720p", "1080p", "4K"]),
                "format": random.choice(["MP4", "AVI", "MOV"])
            })

        return metadata


class ProcessingJobFactory(factory.Factory):
    """Factory for creating test processing jobs"""
    class Meta:
        model = ProcessingJob

    id = factory.LazyFunction(uuid.uuid4)
    document_id = factory.LazyFunction(uuid.uuid4)
    job_type = fuzzy.FuzzyChoice([
        JobType.EMBEDDING_GENERATION,
        JobType.ENTITY_EXTRACTION,
        JobType.IMAGE_PROCESSING,
        JobType.AUDIO_TRANSCRIPTION,
        JobType.VIDEO_PROCESSING
    ])
    status = fuzzy.FuzzyChoice([
        JobStatus.PENDING,
        JobStatus.RUNNING,
        JobStatus.COMPLETED,
        JobStatus.FAILED
    ])
    progress = fuzzy.FuzzyInteger(0, 100)
    priority = fuzzy.FuzzyChoice(list(JobPriority) if 'JobPriority' in globals() else ['low', 'medium', 'high'])
    owner_id = factory.LazyFunction(uuid.uuid4)
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)

    @post_generation
    def result_data(obj, create, extracted, **kwargs):
        """Generate result data for completed jobs"""
        if extracted:
            return extracted

        if obj.status == JobStatus.COMPLETED:
            return {
                "processing_time": random.uniform(1.0, 300.0),
                "output_files": [f"output_{uuid.uuid4()}.json"],
                "metadata": {
                    "processed_items": random.randint(1, 100),
                    "success_rate": random.uniform(0.8, 1.0)
                }
            }
        elif obj.status == JobStatus.FAILED:
            return {
                "error_message": factory.Faker("sentence").generate(),
                "error_code": f"ERR_{random.randint(1000, 9999)}",
                "failed_at": (datetime.utcnow() + timedelta(seconds=random.randint(1, 300))).isoformat()
            }
        return {}


# Search Result Factory
class SearchResultFactory:
    """Factory for creating search results"""

    @staticmethod
    def create_batch(count: int, query: str = None) -> List[Dict[str, Any]]:
        """Create a batch of search results"""
        results = []
        for _ in range(count):
            result = SearchResultFactory.create_one(query)
            results.append(result)
        return results

    @staticmethod
    def create_one(query: str = None) -> Dict[str, Any]:
        """Create a single search result"""
        doc_id = str(uuid.uuid4())
        return {
            "id": doc_id,
            "document_id": doc_id,
            "title": factory.Faker("sentence", nb_words=8).generate(),
            "content": factory.Faker("paragraph", nb_sentences=5).generate(),
            "snippet": factory.Faker("sentence", nb_words=15).generate(),
            "score": round(random.uniform(0.5, 1.0), 4),
            "metadata": {
                "document_type": random.choice(["pdf", "txt", "html"]),
                "author": factory.Faker("name").generate(),
                "publication_date": (datetime.utcnow() - timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d"),
                "tags": [f"tag_{i}" for i in range(random.randint(1, 5))],
                "language": random.choice(["en", "es", "fr", "de"])
            },
            "highlight": {
                "title": [factory.Faker("word").generate()],
                "content": [query or factory.Faker("word").generate()]
            }
        }


# Agent Response Factory
class AgentResponseFactory:
    """Factory for creating agent responses"""

    @staticmethod
    def create_orchestrator_response(query: str) -> Dict[str, Any]:
        """Create orchestrator agent response"""
        return {
            "agent": "orchestrator",
            "query": query,
            "decomposition": {
                "main_query": query,
                "sub_queries": [
                    factory.Faker("sentence").generate() for _ in range(random.randint(1, 3))
                ],
                "search_strategy": random.choice(["parallel", "sequential", "hybrid"]),
                "required_agents": random.sample(
                    ["retrieval", "graph", "vector", "qa"],
                    k=random.randint(2, 4)
                )
            },
            "execution_plan": [
                {
                    "step": i + 1,
                    "agent": agent,
                    "action": random.choice(["search", "filter", "rank", "synthesize"]),
                    "inputs": factory.Faker("words", nb=5).generate()
                }
                for i, agent in enumerate(["retrieval", "vector", "graph", "qa"][:random.randint(2, 4)])
            ]
        }

    @staticmethod
    def create_retrieval_response(query: str, num_results: int = 5) -> Dict[str, Any]:
        """Create retrieval agent response"""
        return {
            "agent": "retrieval",
            "query": query,
            "search_type": random.choice(["keyword", "semantic", "hybrid"]),
            "results": SearchResultFactory.create_batch(num_results, query),
            "total_found": random.randint(num_results, 1000),
            "search_time": round(random.uniform(0.1, 2.0), 3),
            "filters_applied": {
                "document_types": random.sample(["pdf", "txt", "html"], k=random.randint(1, 3)),
                "date_range": f"{random.randint(2020, 2024)}-01-01 TO 2024-12-31",
                "language": random.choice(["en", "es", "fr", "de"])
            }
        }

    @staticmethod
    def create_vector_response(query: str, num_results: int = 5) -> Dict[str, Any]:
        """Create vector agent response"""
        return {
            "agent": "vector",
            "query": query,
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "query_embedding": [random.uniform(-1, 1) for _ in range(384)],
            "results": SearchResultFactory.create_batch(num_results, query),
            "similarity_threshold": random.uniform(0.5, 0.8),
            "search_time": round(random.uniform(0.05, 0.5), 3),
            "index_info": {
                "vectors_count": random.randint(10000, 100000),
                "index_size": random.randint(100, 1000)
            }
        }

    @staticmethod
    def create_graph_response(query: str) -> Dict[str, Any]:
        """Create graph agent response"""
        return {
            "agent": "graph",
            "query": query,
            "entities_found": [
                {
                    "id": str(uuid.uuid4()),
                    "name": factory.Faker("name").generate(),
                    "type": random.choice(["Person", "Organization", "Concept", "Location"]),
                    "properties": {
                        "importance": round(random.uniform(0, 1), 2),
                        "frequency": random.randint(1, 100)
                    }
                }
                for _ in range(random.randint(3, 10))
            ],
            "relationships": [
                {
                    "from": str(uuid.uuid4()),
                    "to": str(uuid.uuid4()),
                    "type": random.choice(["AUTHORED", "RELATED_TO", "MENTIONED_IN", "WORKS_FOR"]),
                    "weight": round(random.uniform(0, 1), 2)
                }
                for _ in range(random.randint(2, 8))
            ],
            "graph_traversal_time": round(random.uniform(0.1, 1.0), 3),
            "nodes_explored": random.randint(10, 1000)
        }

    @staticmethod
    def create_qa_response(query: str, context: List[str] = None) -> Dict[str, Any]:
        """Create QA agent response"""
        if context is None:
            context = [factory.Faker("paragraph").generate() for _ in range(3)]

        return {
            "agent": "qa",
            "query": query,
            "answer": factory.Faker("paragraph", nb_sentences=5).generate(),
            "confidence": round(random.uniform(0.7, 1.0), 2),
            "context_used": context,
            "source_documents": [
                {
                    "id": str(uuid.uuid4()),
                    "title": factory.Faker("sentence", nb_words=6).generate(),
                    "relevance_score": round(random.uniform(0.5, 1.0), 3)
                }
                for _ in range(random.randint(1, 5))
            ],
            "reasoning": factory.Faker("paragraph", nb_sentences=3).generate(),
            "answer_type": random.choice(["factual", "analytical", "synthesis", "comparison"]),
            "synthesis_time": round(random.uniform(0.5, 2.0), 3)
        }


# Knowledge Graph Data Factory
class KnowledgeGraphDataFactory:
    """Factory for creating knowledge graph test data"""

    @staticmethod
    def create_entity() -> Dict[str, Any]:
        """Create a graph entity"""
        entity_types = ["Person", "Organization", "Concept", "Location", "Document", "Technology"]
        return {
            "id": str(uuid.uuid4()),
            "name": factory.Faker("name").generate(),
            "type": random.choice(entity_types),
            "properties": {
                "importance": round(random.uniform(0, 1), 2),
                "frequency": random.randint(1, 100),
                "created_at": (datetime.utcnow() - timedelta(days=random.randint(0, 365))).isoformat(),
                "aliases": [factory.Faker("word").generate() for _ in range(random.randint(0, 3))],
                "description": factory.Faker("sentence", nb_words=20).generate()
            }
        }

    @staticmethod
    def create_relationship(entity_id_1: str = None, entity_id_2: str = None) -> Dict[str, Any]:
        """Create a graph relationship"""
        relationship_types = ["AUTHORED", "RELATED_TO", "MENTIONED_IN", "WORKS_FOR", "PART_OF", "EXEMPLIFIES"]
        return {
            "id": str(uuid.uuid4()),
            "from": entity_id_1 or str(uuid.uuid4()),
            "to": entity_id_2 or str(uuid.uuid4()),
            "type": random.choice(relationship_types),
            "properties": {
                "weight": round(random.uniform(0, 1), 2),
                "confidence": round(random.uniform(0.5, 1.0), 2),
                "created_at": (datetime.utcnow() - timedelta(days=random.randint(0, 365))).isoformat(),
                "context": factory.Faker("sentence", nb_words=10).generate()
            }
        }

    @staticmethod
    def create_graph(num_entities: int = 20, num_relationships: int = 30) -> Dict[str, Any]:
        """Create a complete knowledge graph"""
        entities = [KnowledgeGraphDataFactory.create_entity() for _ in range(num_entities)]
        entity_ids = [e["id"] for e in entities]

        relationships = []
        for _ in range(num_relationships):
            rel = KnowledgeGraphDataFactory.create_relationship(
                random.choice(entity_ids),
                random.choice(entity_ids)
            )
            relationships.append(rel)

        return {
            "entities": entities,
            "relationships": relationships,
            "metadata": {
                "entity_count": num_entities,
                "relationship_count": num_relationships,
                "created_at": datetime.utcnow().isoformat()
            }
        }


# Query Factory
class QueryFactory:
    """Factory for creating test queries"""

    TOPICS = [
        "machine learning", "quantum computing", "climate change",
        "natural language processing", "deep learning", "renewable energy",
        "blockchain", "internet of things", "robotics", "biotechnology"
    ]

    @staticmethod
    def create_simple_query() -> str:
        """Create a simple search query"""
        topic = random.choice(QueryFactory.TOPICS)
        templates = [
            f"What is {topic}?",
            f"Find information about {topic}",
            f"{topic} research papers",
            f"How does {topic} work?",
            f"{topic} applications"
        ]
        return random.choice(templates)

    @staticmethod
    def create_complex_query() -> str:
        """Create a complex multi-part query"""
        topic1 = random.choice(QueryFactory.TOPICS)
        topic2 = random.choice([t for t in QueryFactory.TOPICS if t != topic1])

        templates = [
            f"Compare {topic1} and {topic2}",
            f"What are the advantages of {topic1} over {topic2}?",
            f"How can {topic1} be applied to solve {topic2} challenges?",
            f"What are the latest developments in {topic1} and how do they relate to {topic2}?",
            f"Explain the relationship between {topic1} and {topic2} with examples"
        ]
        return random.choice(templates)

    @staticmethod
    def create_filtered_query() -> Dict[str, Any]:
        """Create a query with filters"""
        return {
            "query": QueryFactory.create_simple_query(),
            "filters": {
                "document_types": random.sample(["pdf", "txt", "html"], k=random.randint(1, 3)),
                "date_range": f"{random.randint(2020, 2023)}-01-01 TO 2024-12-31",
                "languages": random.sample(["en", "es", "fr", "de"], k=random.randint(1, 2)),
                "tags": [f"tag_{i}" for i in range(random.randint(1, 4))],
                "authors": [factory.Faker("name").generate() for _ in range(random.randint(1, 3))]
            },
            "sort_by": random.choice(["relevance", "date", "popularity"]),
            "limit": random.choice([5, 10, 20, 50])
        }


# Performance Test Data Factory
class PerformanceTestFactory:
    """Factory for creating performance test data"""

    @staticmethod
    def create_load_test_config() -> Dict[str, Any]:
        """Create load test configuration"""
        return {
            "concurrent_users": random.randint(10, 100),
            "duration": random.randint(30, 300),  # seconds
            "ramp_up": random.randint(5, 30),     # seconds
            "requests_per_second": random.randint(10, 200),
            "test_scenarios": [
                {
                    "name": "simple_search",
                    "weight": 40,
                    "query": QueryFactory.create_simple_query()
                },
                {
                    "name": "complex_search",
                    "weight": 30,
                    "query": QueryFactory.create_complex_query()
                },
                {
                    "name": "filtered_search",
                    "weight": 30,
                    "query": QueryFactory.create_filtered_query()
                }
            ]
        }

    @staticmethod
    def create_benchmark_data() -> Dict[str, Any]:
        """Create benchmark test data"""
        return {
            "queries": [QueryFactory.create_simple_query() for _ in range(100)],
            "expected_latencies": {
                "p50": 0.5,    # 500ms
                "p95": 1.0,    # 1000ms
                "p99": 2.0     # 2000ms
            },
            "expected_throughput": 100,  # queries per second
            "error_threshold": 0.01      # 1% error rate
        }