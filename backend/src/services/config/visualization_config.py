"""
Configuration for Graph Visualization Service
"""

import os
from typing import Optional

from pydantic import BaseSettings


class GraphVisualizationConfig(BaseSettings):
    """Configuration settings for Graph Visualization Service"""

    # Service Configuration
    SERVICE_NAME: str = "graph-visualization"
    SERVICE_VERSION: str = "1.0.0"
    SERVICE_PORT: int = 8010
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
    REDIS_CACHE_TTL: int = 1800  # 30 minutes default

    # Performance Configuration
    MAX_GRAPH_SIZE_FOR_REALTIME: int = 5000  # Maximum nodes for real-time visualization
    MAX_GRAPH_SIZE_FOR_INTERACTIVE: int = (
        20000  # Maximum nodes for interactive visualization
    )
    DEFAULT_NODE_LIMIT: int = 1000
    DEFAULT_EDGE_LIMIT: int = 2000
    QUERY_TIMEOUT: int = 30

    # Layout Configuration
    DEFAULT_LAYOUT_ALGORITHM: str = "force_directed"
    LAYOUT_ITERATIONS: int = 1000
    LAYOUT_THRESHOLD: float = 1e-4
    FORCE_DIRECTED_STRENGTH: float = 1.0
    FORCE_DIRECTED_REPULSION: float = 100.0
    FORCE_DIRECTED_GRAVITY: float = 0.1

    # Progressive Loading Configuration
    DEFAULT_BATCH_SIZE: int = 500
    MAX_BATCH_SIZE: int = 2000
    PROGRESSIVE_CACHE_TTL: int = 3600  # 1 hour

    # Caching Configuration
    ENABLE_CACHING: bool = True
    SMALL_GRAPH_CACHE_TTL: int = 1800  # 30 minutes
    MEDIUM_GRAPH_CACHE_TTL: int = 3600  # 1 hour
    LARGE_GRAPH_CACHE_TTL: int = 7200  # 2 hours
    XL_GRAPH_CACHE_TTL: int = 14400  # 4 hours

    # Visualization Configuration
    DEFAULT_NODE_SIZE_RANGE: list = [5, 20]
    DEFAULT_EDGE_WIDTH_RANGE: list = [1, 5]
    DEFAULT_NODE_COLORS: dict = {
        "PERSON": "#4ecdc4",
        "ORGANIZATION": "#45b7d1",
        "LOCATION": "#96ceb4",
        "PRODUCT": "#ffeaa7",
        "EVENT": "#dfe6e9",
        "CONCEPT": "#a29bfe",
    }
    DEFAULT_EDGE_COLORS: dict = {
        "WORKS_FOR": "#e17055",
        "KNOWS": "#00b894",
        "RELATED_TO": "#6c5ce7",
        "LOCATED_IN": "#fdcb6e",
        "PART_OF": "#e84393",
    }

    # Performance Optimization Configuration
    ENABLE_PERFORMANCE_OPTIMIZATION: bool = True
    MIN_DEGREE_FILTER: int = 1
    WEAK_EDGE_THRESHOLD: float = 0.1
    SIMILAR_ENTITY_SAMPLING: bool = True
    MAX_SIMILAR_ENTITIES: int = 10

    # Interactive Features Configuration
    ENABLE_INTERACTIVE_FILTERING: bool = True
    MAX_FILTER_CACHE_SIZE: int = 100
    FILTER_CACHE_TTL: int = 900  # 15 minutes

    # Export Configuration
    ENABLE_EXPORT: bool = True
    MAX_EXPORT_SIZE: int = 10000
    EXPORT_FORMATS: list = ["json", "csv", "gexf"]

    # Security Configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30

    # Resource Limits
    MAX_MEMORY_MB: int = 2048
    MAX_CPU_TIME_SECONDS: int = 120
    MAX_CONCURRENT_VISUALIZATIONS: int = 50

    # Feature Flags
    ENABLE_3D_VISUALIZATION: bool = False
    ENABLE_REAL_TIME_UPDATES: bool = True
    ENABLE_COLLABORATIVE_FEATURES: bool = False

    # Monitoring Configuration
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9010
    PERFORMANCE_TRACKING: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global configuration instance
config = GraphVisualizationConfig()
