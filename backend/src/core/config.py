"""
Application configuration settings

SECURITY NOTE: All sensitive configuration values MUST be provided via environment
variables. Default values are only used for local development.
"""

import os
import secrets
from typing import Dict, List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


def _generate_dev_secret() -> str:
    """Generate a random secret for development only."""
    return secrets.token_urlsafe(32)


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "Multimodal Enterprise RAG System"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = ""

    # CORS Configuration (comma-separated string from env, parsed to list)
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    CORS_ALLOWED_HEADERS: str = (
        "Authorization,"
        "Content-Type,"
        "Accept,"
        "Origin,"
        "X-Request-ID,"
        "X-Correlation-ID,"
        "X-Organization-ID,"
        "X-Client-Version,"
        "Cache-Control"
    )
    CORS_ALLOWED_METHODS: str = "GET,POST,PUT,DELETE,PATCH,OPTIONS,HEAD"
    CORS_EXPOSE_HEADERS: str = "X-Request-ID,X-Correlation-ID,X-Process-Time"
    CORS_MAX_AGE: int = 86400  # 24 hours preflight cache

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS string into a list."""
        if not self.CORS_ORIGINS:
            return ["http://localhost:3000"]
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]

    @property
    def cors_headers_list(self) -> List[str]:
        """Parse CORS_ALLOWED_HEADERS string into a list."""
        return [h.strip() for h in self.CORS_ALLOWED_HEADERS.split(",") if h.strip()]

    @property
    def cors_methods_list(self) -> List[str]:
        """Parse CORS_ALLOWED_METHODS string into a list."""
        return [m.strip() for m in self.CORS_ALLOWED_METHODS.split(",") if m.strip()]

    @property
    def cors_expose_list(self) -> List[str]:
        """Parse CORS_EXPOSE_HEADERS string into a list."""
        return [h.strip() for h in self.CORS_EXPOSE_HEADERS.split(",") if h.strip()]

    # Database
    DATABASE_URL: str = (
        "postgresql://postgres:postgres@localhost:5432/multimodal_rag_dev"
    )

    # Supabase
    SUPABASE_URL: str = "http://localhost:54321"
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_DB_URL: str = ""  # If set, overrides DATABASE_URL for Supabase connection
    SUPABASE_JWT_SECRET: str = ""  # Supabase JWT secret for verifying auth tokens

    REDIS_URL: str = "redis://localhost:6379"

    # Neo4j Configuration
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    # Qdrant Configuration
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None

    # JWT Configuration
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # Default refresh token lifetime
    REMEMBER_ME_REFRESH_TOKEN_DAYS: int = 30  # Extended session for "Remember Me"
    CLI_TOKEN_EXPIRE_DAYS: int = 30  # Long-lived CLI device tokens

    @model_validator(mode="after")
    def _override_database_url_from_supabase(self):
        """Override DATABASE_URL when SUPABASE_DB_URL is set."""
        if self.SUPABASE_DB_URL:
            self.DATABASE_URL = self.SUPABASE_DB_URL
        # Validate final DATABASE_URL (allow sqlite in testing)
        allowed_prefixes = ("postgresql://", "postgresql+asyncpg://")
        if self.ENVIRONMENT == "testing":
            allowed_prefixes = ("postgresql://", "postgresql+asyncpg://", "sqlite://")
        if not self.DATABASE_URL.startswith(allowed_prefixes):
            raise ValueError(
                "DATABASE_URL must start with postgresql:// or postgresql+asyncpg://"
            )
        if self.ENVIRONMENT in ("production", "staging") and "localhost" in self.DATABASE_URL:
            raise ValueError(
                "DATABASE_URL must not point to localhost in production/staging"
            )
        return self

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v, info):
        """Validate SECRET_KEY - require in production, generate for dev."""
        weak_patterns = [
            "change-in-production",
            "your-secret",
            "changeme",
            "secret-key",
            "dev-secret",
        ]
        is_weak = not v or any(
            pattern in (v or "").lower() for pattern in weak_patterns
        )

        if is_weak:
            env = os.getenv("ENVIRONMENT", "development")
            if env in ("production", "staging"):
                raise ValueError(
                    "SECRET_KEY must be set to a strong value in production/staging"
                )
            return _generate_dev_secret()
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("JWT_SECRET_KEY", mode="before")
    @classmethod
    def validate_jwt_secret_key(cls, v, info):
        """Validate JWT_SECRET_KEY - require in production, generate for dev."""
        weak_patterns = [
            "change-in-production",
            "your-secret",
            "changeme",
            "jwt-secret",
            "dev-jwt-persistent",
        ]
        is_weak = not v or any(
            pattern in (v or "").lower() for pattern in weak_patterns
        )

        if is_weak:
            env = os.getenv("ENVIRONMENT", "development")
            if env in ("production", "staging"):
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a strong value in production/staging. "
                    "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
                )
            return _generate_dev_secret()
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("NEO4J_PASSWORD", mode="before")
    @classmethod
    def validate_neo4j_password(cls, v, info):
        """Validate NEO4J_PASSWORD - require in production."""
        if not v or v == "neo4jpassword":
            env = os.getenv("ENVIRONMENT", "development")
            if env in ("production", "staging"):
                raise ValueError(
                    "NEO4J_PASSWORD must be set via environment variable in production/staging"
                )
            return "neo4jpassword"  # Default for local development
        return v

    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 10
    FREE_TIER_STORAGE_GB: int = 10

    # Storage Backend: "local", "s3", or "supabase"
    STORAGE_BACKEND: str = "local"

    # S3-Compatible Object Storage (DigitalOcean Spaces)
    S3_ENDPOINT_URL: Optional[str] = None  # https://nyc3.digitaloceanspaces.com
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_BUCKET_NAME: str = "rag-system-storage"
    S3_REGION: str = "nyc3"
    S3_CDN_ENDPOINT: Optional[str] = None  # https://rag-system-storage.nyc3.cdn.digitaloceanspaces.com
    S3_STORAGE_TEMP_DIR: str = "/tmp/rag_s3_storage"

    # Supabase Storage (legacy)
    SUPABASE_STORAGE_ENABLED: bool = False
    SUPABASE_STORAGE_TEMP_DIR: str = "/tmp/rag_storage"

    # Security directories
    SECURITY_DIR: str = "./security"  # Directory for encryption keys and security files

    # Security
    BCRYPT_ROUNDS: int = 12
    RATE_LIMIT_PER_MINUTE: int = 60
    AUTH_RATE_LIMIT_ATTEMPTS: int = 50  # Max auth attempts in window
    AUTH_RATE_LIMIT_WINDOW_MINUTES: int = 15  # Time window for rate limiting

    # External APIs
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Research Connector APIs
    CROSSREF_MAILTO: Optional[str] = None
    NCBI_API_KEY: Optional[str] = None

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

    # Azure AI Cohere Reranking Configuration
    COHERE_RERANK_ENDPOINT: Optional[str] = None
    COHERE_RERANK_API_KEY: Optional[str] = None
    COHERE_RERANK_MODEL: str = "Cohere-rerank-v4.0-pro"
    COHERE_RERANK_TOP_N: int = 10

    # Cohere Embedding Configuration
    COHERE_EMBED_ENDPOINT: Optional[str] = None  # https://api.cohere.com/v2/embed
    COHERE_EMBED_API_KEY: Optional[str] = None  # Falls back to COHERE_RERANK_API_KEY
    COHERE_EMBED_MODEL: str = "embed-v-4-0"  # Azure AI deployment name
    COHERE_EMBED_DIMENSIONS: int = 1024
    COHERE_EMBED_BATCH_SIZE: int = 96

    # Processing Configuration
    MAX_CONCURRENT_JOBS: int = 5
    JOB_RETRY_MAX: int = 3
    JOB_RETRY_DELAY: int = 5  # seconds

    # Search Configuration
    DEFAULT_SEARCH_LIMIT: int = 10
    MAX_SEARCH_LIMIT: int = 50
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Embedding Provider Configuration
    EMBEDDING_PROVIDER: str = (
        "sentence_transformers"  # cohere, sentence_transformers, azure_openai, auto
    )

    # LLM Response Cache Configuration
    LLM_CACHE_ENABLED: bool = True
    LLM_CACHE_TTL_SECONDS: int = 3600  # 1 hour default
    LLM_CACHE_MAX_ENTRIES: int = 5000
    LLM_CACHE_SEMANTIC_ENABLED: bool = True
    LLM_CACHE_SIMILARITY_THRESHOLD: float = 0.92  # 0.0-1.0, higher = stricter matching

    # Thread Context Window Configuration
    # Model-aware defaults for context windows
    THREAD_DEFAULT_MAX_MESSAGES: int = 20  # Default messages to include in context
    THREAD_DEFAULT_MAX_TOKENS: int = 4000  # Default token limit for context
    THREAD_CONTEXT_WARN_THRESHOLD: float = (
        0.9  # Warn when context usage exceeds this ratio
    )

    # Model-specific token limits (used for model-aware defaults)
    MODEL_CONTEXT_LIMITS: Dict[str, int] = {
        "gpt-3.5-turbo": 16385,
        "gpt-4": 8192,
        "gpt-4-32k": 32768,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "claude-3-haiku": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-opus": 200000,
        "claude-3-5-sonnet": 200000,
    }

    # Monitoring
    ENABLE_METRICS: bool = True
    LOG_LEVEL: str = "INFO"

    @field_validator("NEO4J_URI")
    @classmethod
    def validate_neo4j_uri(cls, v):
        if not v.startswith(("bolt://", "neo4j://", "bolt+s://", "neo4j+s://")):
            raise ValueError(
                "Neo4j URI must start with bolt://, neo4j://, bolt+s://, or neo4j+s://"
            )
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

    @field_validator("LLM_CACHE_TTL_SECONDS")
    @classmethod
    def validate_cache_ttl(cls, v):
        if v <= 0:
            raise ValueError("LLM_CACHE_TTL_SECONDS must be positive")
        return v

    @field_validator("LLM_CACHE_MAX_ENTRIES")
    @classmethod
    def validate_cache_max_entries(cls, v):
        if v <= 0:
            raise ValueError("LLM_CACHE_MAX_ENTRIES must be positive")
        return v

    @field_validator("LLM_CACHE_SIMILARITY_THRESHOLD")
    @classmethod
    def validate_cache_similarity_threshold(cls, v):
        if v < 0.0 or v > 1.0:
            raise ValueError(
                "LLM_CACHE_SIMILARITY_THRESHOLD must be between 0.0 and 1.0"
            )
        return v

    @field_validator("THREAD_DEFAULT_MAX_MESSAGES")
    @classmethod
    def validate_thread_max_messages(cls, v):
        if v < 1 or v > 1000:
            raise ValueError("THREAD_DEFAULT_MAX_MESSAGES must be between 1 and 1000")
        return v

    @field_validator("THREAD_DEFAULT_MAX_TOKENS")
    @classmethod
    def validate_thread_max_tokens(cls, v):
        if v < 1 or v > 200000:
            raise ValueError("THREAD_DEFAULT_MAX_TOKENS must be between 1 and 200000")
        return v

    @field_validator("THREAD_CONTEXT_WARN_THRESHOLD")
    @classmethod
    def validate_thread_warn_threshold(cls, v):
        if v < 0.0 or v > 1.0:
            raise ValueError(
                "THREAD_CONTEXT_WARN_THRESHOLD must be between 0.0 and 1.0"
            )
        return v

    @field_validator("FREE_TIER_STORAGE_GB")
    @classmethod
    def validate_storage_limit(cls, v):
        if v <= 0 or v > 10000:  # Max 10TB
            raise ValueError("FREE_TIER_STORAGE_GB must be between 1 and 10000")
        return v

    class Config:
        env_file = "../.env"
        case_sensitive = True
        extra = "ignore"


# Create settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings"""
    return settings
