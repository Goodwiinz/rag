"""
Application configuration settings
"""

import os
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "Multimodal Enterprise RAG System"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/multimodal_rag"
    REDIS_URL: str = "redis://localhost:6379"

    # Neo4j Configuration
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4jpassword"

    # Qdrant Configuration
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None

    # JWT Configuration
    JWT_SECRET_KEY: str = "your-jwt-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 10
    FREE_TIER_STORAGE_GB: int = 10

    # Security
    BCRYPT_ROUNDS: int = 12
    RATE_LIMIT_PER_MINUTE: int = 60
    AUTH_RATE_LIMIT_ATTEMPTS: int = 50  # Max auth attempts in window
    AUTH_RATE_LIMIT_WINDOW_MINUTES: int = 15  # Time window for rate limiting

    # External APIs
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Azure OpenAI Configuration
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_DEPLOYMENT_NAME: Optional[str] = None
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME: Optional[str] = None
    AZURE_OPENAI_CHAT_DEPLOYMENT_NAME: Optional[str] = None

    # Multiple Endpoints Support
    AZURE_OPENAI_CHAT_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_EMBEDDING_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_CHAT_API_VERSION: str = "2024-06-01"
    AZURE_OPENAI_EMBEDDING_API_VERSION: str = "2023-05-15"

    # Separate API Keys Support
    AZURE_OPENAI_CHAT_API_KEY: Optional[str] = None
    AZURE_OPENAI_EMBEDDING_API_KEY: Optional[str] = None

    # Processing Configuration
    MAX_CONCURRENT_JOBS: int = 5
    JOB_RETRY_MAX: int = 3
    JOB_RETRY_DELAY: int = 5  # seconds

    # Search Configuration
    DEFAULT_SEARCH_LIMIT: int = 10
    MAX_SEARCH_LIMIT: int = 50
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Embedding Provider Configuration
    EMBEDDING_PROVIDER: str = "sentence_transformers"  # sentence_transformers, azure_openai, auto

    # Monitoring
    ENABLE_METRICS: bool = True
    LOG_LEVEL: str = "INFO"

    @field_validator("NEO4J_URI")
    @classmethod
    def validate_neo4j_uri(cls, v):
        if not v.startswith(("bolt://", "neo4j://", "bolt+s://", "neo4j+s://")):
            raise ValueError("Neo4j URI must start with bolt://, neo4j://, bolt+s://, or neo4j+s://")
        return v

    @field_validator("QDRANT_API_KEY")
    @classmethod
    def validate_qdrant_api_key(cls, v):
        # Allow None or empty string for local development, but validate format if provided
        if v is not None and v != "" and len(v) < 10:
            raise ValueError("Qdrant API key must be at least 10 characters long")
        return v

    @field_validator("QDRANT_URL")
    @classmethod
    def validate_qdrant_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("Qdrant URL must start with http:// or https://")
        return v

    @field_validator("MAX_FILE_SIZE_MB")
    @classmethod
    def validate_max_file_size(cls, v):
        if v <= 0 or v > 1000:  # Max 1GB
            raise ValueError("MAX_FILE_SIZE_MB must be between 1 and 1000")
        return v

    @field_validator("FREE_TIER_STORAGE_GB")
    @classmethod
    def validate_storage_limit(cls, v):
        if v <= 0 or v > 10000:  # Max 10TB
            raise ValueError("FREE_TIER_STORAGE_GB must be between 1 and 10000")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()