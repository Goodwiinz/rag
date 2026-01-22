"""
Test Configuration for Multi-Agent Search System
Provides centralized test settings and environment configurations
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass

# Add backend src to path
backend_src = Path(__file__).parent / "src"
sys.path.insert(0, str(backend_src))

# Test Environment Configuration
TEST_ENV = "testing"
TEST_LOG_LEVEL = "INFO"
TEST_DEBUG = True

# Database Configuration
TEST_DATABASES = {
    "postgresql": {
        "url": "postgresql://postgres:postgres@localhost:5432/multimodal_rag_test",
        "echo": False,
        "pool_size": 5,
        "max_overflow": 10
    },
    "sqlite": {
        "url": "sqlite:///:memory:",
        "echo": False,
        "connect_args": {"check_same_thread": False}
    }
}

# Redis Configuration
TEST_REDIS = {
    "url": "redis://localhost:6379/1",
    "decode_responses": True
}

# Neo4j Configuration
TEST_NEO4J = {
    "uri": "bolt://localhost:7687",
    "user": "neo4j",
    "password": "testpassword",
    "database": "neo4j"
}

# Qdrant Configuration
TEST_QDRANT = {
    "url": "http://localhost:6333",
    "api_key": None,
    "timeout": 30
}

# OpenAI/LLM Configuration (Mock)
TEST_LLM_CONFIG = {
    "openai": {
        "api_key": "test-openai-key",
        "model": "gpt-3.5-turbo",
        "temperature": 0.1,
        "max_tokens": 1000
    },
    "anthropic": {
        "api_key": "test-anthropic-key",
        "model": "claude-3-haiku-20240307",
        "temperature": 0.1,
        "max_tokens": 1000
    }
}

# Multi-Agent Configuration
TEST_AGENT_CONFIG = {
    "crewai": {
        "verbose": True,
        "process": "hierarchical",
        "manager_llm": "openai:gpt-3.5-turbo",
        "max_rpm": 100,
        "share_crew": False
    },
    "agents": {
        "orchestrator": {
            "role": "Search Orchestrator",
            "goal": "Coordinate multi-modal search queries",
            "backstory": "Expert in query decomposition and agent coordination",
            "tools": ["search_tool", "filter_tool"]
        },
        "retrieval_agent": {
            "role": "Document Retrieval Specialist",
            "goal": "Retrieve relevant documents from multiple sources",
            "backstory": "Specialized in semantic and keyword search",
            "tools": ["vector_search", "fulltext_search"]
        },
        "graph_agent": {
            "role": "Knowledge Graph Analyst",
            "goal": "Extract relationships from knowledge graph",
            "backstory": "Expert in graph traversal and relationship analysis",
            "tools": ["graph_search", "relationship_query"]
        },
        "vector_agent": {
            "role": "Semantic Search Expert",
            "goal": "Perform semantic similarity searches",
            "backstory": "Specialized in vector embeddings and similarity",
            "tools": ["vector_search", "embedding_tool"]
        },
        "qa_agent": {
            "role": "Question Answering Specialist",
            "goal": "Synthesize answers from retrieved information",
            "backstory": "Expert in information synthesis and answer generation",
            "tools": ["synthesis_tool", "ranking_tool"]
        }
    }
}

# Test Data Configuration
TEST_DATA_CONFIG = {
    "sample_documents": {
        "count": 100,
        "types": ["pdf", "txt", "image", "audio", "video"],
        "languages": ["en", "es", "fr", "de"]
    },
    "sample_queries": [
        "What are the latest developments in machine learning?",
        "Find documents about quantum computing applications",
        "Search for climate change research papers",
        "What are the benefits of renewable energy?",
        "Find information about natural language processing"
    ],
    "test_embeddings": {
        "dimension": 384,
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "batch_size": 32
    }
}

# Performance Test Configuration
TEST_PERFORMANCE_CONFIG = {
    "load_testing": {
        "concurrent_users": 10,
        "duration": 60,  # seconds
        "ramp_up": 10,   # seconds
        "requests_per_second": 100
    },
    "thresholds": {
        "response_time_p95": 2000,  # ms
        "response_time_p99": 5000,  # ms
        "error_rate": 1.0,          # %
        "throughput": 100           # requests/sec
    }
}

# WebSocket Test Configuration
TEST_WEBSOCKET_CONFIG = {
    "endpoint": "ws://localhost:8000/api/v2/ws/connect",
    "test_channels": ["document_status", "search_results", "system_metrics"],
    "message_types": ["status_update", "search_complete", "error"],
    "timeout": 30
}

# Security Test Configuration
TEST_SECURITY_CONFIG = {
    "test_users": {
        "admin": {
            "email": "admin@test.com",
            "password": "test123",
            "role": "admin"
        },
        "user": {
            "email": "user@test.com",
            "password": "test123",
            "role": "user"
        },
        "guest": {
            "email": "guest@test.com",
            "password": "test123",
            "role": "guest"
        }
    },
    "test_tokens": {
        "valid_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.signature",
        "expired_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.expired.signature",
        "invalid_token": "invalid.token.here"
    }
}

# Environment Variables for Testing
def set_test_environment():
    """Set all test environment variables"""
    os.environ["ENVIRONMENT"] = TEST_ENV
    os.environ["LOG_LEVEL"] = TEST_LOG_LEVEL
    os.environ["DEBUG"] = str(TEST_DEBUG)

    # Database URLs
    os.environ["DATABASE_URL"] = TEST_DATABASES["postgresql"]["url"]
    os.environ["REDIS_URL"] = TEST_REDIS["url"]

    # External Services
    os.environ["NEO4J_URI"] = TEST_NEO4J["uri"]
    os.environ["NEO4J_USER"] = TEST_NEO4J["user"]
    os.environ["NEO4J_PASSWORD"] = TEST_NEO4J["password"]

    os.environ["QDRANT_URL"] = TEST_QDRANT["url"]
    os.environ["QDRANT_API_KEY"] = TEST_QDRANT["api_key"] or ""

    # LLM API Keys (Test/Mock)
    os.environ["OPENAI_API_KEY"] = TEST_LLM_CONFIG["openai"]["api_key"]
    os.environ["ANTHROPIC_API_KEY"] = TEST_LLM_CONFIG["anthropic"]["api_key"]

    # Test-specific settings
    os.environ["TESTING"] = "true"
    os.environ["SKIP_MIGRATIONS"] = "false"
    os.environ["DISABLE_BACKGROUND_TASKS"] = "true"

# Test Data Factory Configuration
@dataclass
class TestDocumentConfig:
    """Configuration for generating test documents"""
    min_words: int = 100
    max_words: int = 5000
    min_paragraphs: int = 3
    max_paragraphs: int = 50
    include_images: bool = True
    include_tables: bool = True
    include_metadata: bool = True
    languages: List[str] = None

    def __post_init__(self):
        if self.languages is None:
            self.languages = ["en", "es", "fr"]

@dataclass
class TestSearchConfig:
    """Configuration for search testing"""
    query_types: List[str] = None
    result_counts: List[int] = None
    filters: Dict[str, Any] = None

    def __post_init__(self):
        if self.query_types is None:
            self.query_types = ["keyword", "semantic", "hybrid", "graph"]
        if self.result_counts is None:
            self.result_counts = [5, 10, 20, 50]
        if self.filters is None:
            self.filters = {
                "document_types": ["pdf", "txt"],
                "date_range": "last_year",
                "languages": ["en"]
            }

# Export configurations
__all__ = [
    "TEST_ENV",
    "TEST_LOG_LEVEL",
    "TEST_DEBUG",
    "TEST_DATABASES",
    "TEST_REDIS",
    "TEST_NEO4J",
    "TEST_QDRANT",
    "TEST_LLM_CONFIG",
    "TEST_AGENT_CONFIG",
    "TEST_DATA_CONFIG",
    "TEST_PERFORMANCE_CONFIG",
    "TEST_WEBSOCKET_CONFIG",
    "TEST_SECURITY_CONFIG",
    "set_test_environment",
    "TestDocumentConfig",
    "TestSearchConfig"
]