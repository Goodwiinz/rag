"""
Configuration for Knowledge Graph Service
"""

import os
from typing import Optional

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings  # Fallback for older pydantic versions


class KnowledgeGraphConfig(BaseSettings):
    """Configuration settings for Knowledge Graph Service"""

    # Service Configuration
    SERVICE_NAME: str = "knowledge-graph"
    SERVICE_VERSION: str = "1.0.0"
    SERVICE_PORT: int = 8003
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database Configuration
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")

    # PostgreSQL Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://user:password@localhost:5432/rag_system"
    )

    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_CACHE_TTL: int = 3600  # 1 hour default TTL

    # Authentication Configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30

    # Performance Configuration
    MAX_CONNECTION_POOL_SIZE: int = 50
    MAX_CONNECTION_LIFETIME: int = 3600
    QUERY_TIMEOUT: int = 30
    BATCH_SIZE_LIMIT: int = 1000

    # Entity Extraction Configuration
    ENTITY_EXTRACTION_MODEL: str = "gpt-3.5-turbo"
    ENTITY_CONFIDENCE_THRESHOLD: float = 0.7
    RELATIONSHIP_CONFIDENCE_THRESHOLD: float = 0.6

    # WebSocket Configuration
    WS_CONNECTION_TIMEOUT: int = 60
    WS_HEARTBEAT_INTERVAL: int = 30

    # Monitoring Configuration
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9003

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",  # Allow extra environment variables without error
    }


# Global configuration instance
config = KnowledgeGraphConfig()
