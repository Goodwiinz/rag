"""
Configuration for Graph Analytics Service
"""

import os
from typing import Optional
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings  # Fallback for older pydantic


class GraphAnalyticsConfig(BaseSettings):
    """Configuration settings for Graph Analytics Service"""

    # Service Configuration
    SERVICE_NAME: str = "graph-analytics"
    SERVICE_VERSION: str = "1.0.0"
    SERVICE_PORT: int = 8009
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database Configuration
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")

    # PostgreSQL Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/rag_system"
    )

    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_CACHE_TTL: int = 3600

    # Celery Configuration
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list = ["json"]
    CELERY_TIMEZONE: str = "UTC"

    # Algorithm Configuration
    MAX_GRAPH_SIZE_FOR_CENTRALITY: int = 10000  # Maximum nodes for real-time centrality
    MAX_GRAPH_SIZE_FOR_COMMUNITIES: int = 50000   # Maximum nodes for community detection
    MAX_PATH_LENGTH: int = 10                     # Maximum path length for algorithms
    DEFAULT_CENTRALITY_LIMIT: int = 100           # Default limit for centrality results
    DEFAULT_COMMUNITY_RESOLUTION: float = 1.0     # Default resolution for Louvain algorithm

    # Performance Configuration
    QUERY_TIMEOUT: int = 300                      # Timeout for graph queries in seconds
    MAX_CONCURRENT_JOBS: int = 10                 # Maximum concurrent analytics jobs
    JOB_TIMEOUT: int = 3600                       # Default job timeout in seconds

    # Cache Configuration
    ENABLE_RESULT_CACHING: bool = True
    CENTRALITY_CACHE_TTL: int = 3600              # 1 hour
    PATH_CACHE_TTL: int = 1800                    # 30 minutes
    COMMUNITY_CACHE_TTL: int = 7200               # 2 hours
    INSIGHTS_CACHE_TTL: int = 3600                # 1 hour

    # Background Processing Configuration
    ENABLE_BACKGROUND_PROCESSING: bool = True
    BACKGROUND_JOB_QUEUE: str = "graph_analytics"
    MAX_RETRIES_PER_JOB: int = 3
    RETRY_DELAY_SECONDS: int = 60

    # Scheduling Configuration
    ENABLE_SCHEDULING: bool = True
    SCHEDULER_TIMEZONE: str = "UTC"
    MAX_SCHEDULED_JOBS: int = 100

    # Monitoring Configuration
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9009
    METRICS_COLLECTION_INTERVAL: int = 60        # seconds

    # Algorithm-Specific Settings
    # PageRank
    PAGERANK_DAMPING_FACTOR: float = 0.85
    PAGERANK_MAX_ITERATIONS: int = 100
    PAGERANK_TOLERANCE: float = 1e-6

    # Community Detection
    LOUVAIN_DEFAULT_RESOLUTION: float = 1.0
    LABEL_PROPAGATION_MAX_ITERATIONS: int = 100
    MIN_COMMUNITY_SIZE: int = 3

    # Path Finding
    DIJKSTRA_WEIGHT_PROPERTY: str = "strength"
    BFS_MAX_DEPTH: int = 5
    MAX_PATHS_PER_QUERY: int = 10

    # Security Configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30

    # Resource Limits
    MAX_ENTITIES_PER_ANALYSIS: int = 100000
    MAX_RELATIONSHIPS_PER_ANALYSIS: int = 500000
    MEMORY_LIMIT_GB: int = 8
    CPU_CORES: int = 4

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra env vars from other configs


# Global configuration instance
config = GraphAnalyticsConfig()