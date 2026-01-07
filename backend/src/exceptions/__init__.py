"""
RAG System Exception Hierarchy

Provides a comprehensive exception hierarchy for the RAG system
with proper error codes, status codes, and logging support.
"""

from typing import Any, Dict, Optional


class RAGException(Exception):
    """
    Base exception for the RAG system.
    
    All custom exceptions should inherit from this class.
    Provides consistent error structure and serialization.
    """
    
    error_code: str = "RAG_ERROR"
    status_code: int = 500
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        Initialize a RAG exception.
        
        Args:
            message: Human-readable error message
            details: Additional error details (safe to expose to clients)
            cause: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to a dictionary for API responses."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }
    
    def __str__(self) -> str:
        return f"{self.error_code}: {self.message}"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, details={self.details!r})"


# =============================================================================
# Validation Errors (4xx)
# =============================================================================

class ValidationException(RAGException):
    """Raised when input validation fails."""
    
    error_code = "VALIDATION_ERROR"
    status_code = 400


class InvalidQueryException(ValidationException):
    """Raised when a search query is invalid."""
    
    error_code = "INVALID_QUERY"


class InvalidFileException(ValidationException):
    """Raised when an uploaded file is invalid."""
    
    error_code = "INVALID_FILE"


class AuthenticationException(RAGException):
    """Raised when authentication fails."""
    
    error_code = "AUTH_ERROR"
    status_code = 401


class TokenExpiredException(AuthenticationException):
    """Raised when a JWT token has expired."""
    
    error_code = "TOKEN_EXPIRED"


class InvalidTokenException(AuthenticationException):
    """Raised when a JWT token is invalid."""
    
    error_code = "INVALID_TOKEN"


class AuthorizationException(RAGException):
    """Raised when user lacks required permissions."""
    
    error_code = "FORBIDDEN"
    status_code = 403


class InsufficientPermissionsException(AuthorizationException):
    """Raised when user doesn't have required role/permission."""
    
    error_code = "INSUFFICIENT_PERMISSIONS"


class NotFoundException(RAGException):
    """Raised when a requested resource is not found."""
    
    error_code = "NOT_FOUND"
    status_code = 404


class DocumentNotFoundException(NotFoundException):
    """Raised when a document is not found."""
    
    error_code = "DOCUMENT_NOT_FOUND"


class UserNotFoundException(NotFoundException):
    """Raised when a user is not found."""
    
    error_code = "USER_NOT_FOUND"


class ConflictException(RAGException):
    """Raised when there's a resource conflict."""
    
    error_code = "CONFLICT"
    status_code = 409


class DuplicateResourceException(ConflictException):
    """Raised when attempting to create a duplicate resource."""
    
    error_code = "DUPLICATE_RESOURCE"


class QuotaExceededException(RAGException):
    """Raised when a quota or rate limit is exceeded."""
    
    error_code = "QUOTA_EXCEEDED"
    status_code = 429


class RateLimitException(QuotaExceededException):
    """Raised when API rate limit is exceeded."""
    
    error_code = "RATE_LIMIT_EXCEEDED"


class StorageQuotaException(QuotaExceededException):
    """Raised when storage quota is exceeded."""
    
    error_code = "STORAGE_QUOTA_EXCEEDED"


# =============================================================================
# Processing Errors (5xx)
# =============================================================================

class ProcessingException(RAGException):
    """Raised when document processing fails."""
    
    error_code = "PROCESSING_ERROR"
    status_code = 500


class IngestionException(ProcessingException):
    """Raised when document ingestion fails."""
    
    error_code = "INGESTION_ERROR"


class EmbeddingException(ProcessingException):
    """Raised when embedding generation fails."""
    
    error_code = "EMBEDDING_ERROR"


class ExtractionException(ProcessingException):
    """Raised when entity/content extraction fails."""
    
    error_code = "EXTRACTION_ERROR"


class ServiceUnavailableError(RAGException):
    """Raised when a required service is unavailable."""
    
    error_code = "SERVICE_UNAVAILABLE"
    status_code = 503


class CircuitBreakerOpenError(ServiceUnavailableError):
    """Raised when a circuit breaker is open."""
    
    error_code = "CIRCUIT_BREAKER_OPEN"


# =============================================================================
# Integration Errors (External Services)
# =============================================================================

class Neo4jException(RAGException):
    """Raised when Neo4j operations fail."""
    
    error_code = "NEO4J_ERROR"
    status_code = 503


class Neo4jConnectionError(Neo4jException):
    """Raised when Neo4j connection fails."""
    
    error_code = "NEO4J_CONNECTION_ERROR"


class Neo4jQueryError(Neo4jException):
    """Raised when a Neo4j query fails."""
    
    error_code = "NEO4J_QUERY_ERROR"


class QdrantException(RAGException):
    """Raised when Qdrant operations fail."""
    
    error_code = "QDRANT_ERROR"
    status_code = 503


class QdrantConnectionError(QdrantException):
    """Raised when Qdrant connection fails."""
    
    error_code = "QDRANT_CONNECTION_ERROR"


class QdrantSearchError(QdrantException):
    """Raised when a Qdrant search fails."""
    
    error_code = "QDRANT_SEARCH_ERROR"


class RedisException(RAGException):
    """Raised when Redis operations fail."""
    
    error_code = "REDIS_ERROR"
    status_code = 503


class ExternalAPIException(RAGException):
    """Raised when an external API call fails."""
    
    error_code = "EXTERNAL_API_ERROR"
    status_code = 502


class CohereException(ExternalAPIException):
    """Raised when Cohere API calls fail."""
    
    error_code = "COHERE_ERROR"


class OpenAIException(ExternalAPIException):
    """Raised when OpenAI API calls fail."""
    
    error_code = "OPENAI_ERROR"


class AnthropicException(ExternalAPIException):
    """Raised when Anthropic API calls fail."""
    
    error_code = "ANTHROPIC_ERROR"


# =============================================================================
# Search Errors
# =============================================================================

class SearchException(RAGException):
    """Base exception for search-related errors."""
    
    error_code = "SEARCH_ERROR"
    status_code = 500


class SearchExecutionError(SearchException):
    """Raised when search execution fails."""
    
    error_code = "SEARCH_EXECUTION_ERROR"


class SearchTimeoutError(SearchException):
    """Raised when search times out."""
    
    error_code = "SEARCH_TIMEOUT"
    status_code = 504


class NoResultsError(SearchException):
    """Raised when search returns no results (optional use)."""
    
    error_code = "NO_RESULTS"
    status_code = 200  # Not really an error


# =============================================================================
# WebSocket Errors
# =============================================================================

class WebSocketException(RAGException):
    """Base exception for WebSocket errors."""
    
    error_code = "WEBSOCKET_ERROR"
    status_code = 500


class WebSocketAuthError(WebSocketException):
    """Raised when WebSocket authentication fails."""
    
    error_code = "WEBSOCKET_AUTH_ERROR"
    status_code = 401


class WebSocketConnectionError(WebSocketException):
    """Raised when WebSocket connection fails."""
    
    error_code = "WEBSOCKET_CONNECTION_ERROR"


# =============================================================================
# Configuration Errors
# =============================================================================

class ConfigurationException(RAGException):
    """Raised when configuration is invalid."""
    
    error_code = "CONFIG_ERROR"
    status_code = 500


class MissingConfigException(ConfigurationException):
    """Raised when required configuration is missing."""
    
    error_code = "MISSING_CONFIG"


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Base
    "RAGException",
    
    # Validation (4xx)
    "ValidationException",
    "InvalidQueryException",
    "InvalidFileException",
    "AuthenticationException",
    "TokenExpiredException",
    "InvalidTokenException",
    "AuthorizationException",
    "InsufficientPermissionsException",
    "NotFoundException",
    "DocumentNotFoundException",
    "UserNotFoundException",
    "ConflictException",
    "DuplicateResourceException",
    "QuotaExceededException",
    "RateLimitException",
    "StorageQuotaException",
    
    # Processing (5xx)
    "ProcessingException",
    "IngestionException",
    "EmbeddingException",
    "ExtractionException",
    "ServiceUnavailableError",
    "CircuitBreakerOpenError",
    
    # Integration
    "Neo4jException",
    "Neo4jConnectionError",
    "Neo4jQueryError",
    "QdrantException",
    "QdrantConnectionError",
    "QdrantSearchError",
    "RedisException",
    "ExternalAPIException",
    "CohereException",
    "OpenAIException",
    "AnthropicException",
    
    # Search
    "SearchException",
    "SearchExecutionError",
    "SearchTimeoutError",
    "NoResultsError",
    
    # WebSocket
    "WebSocketException",
    "WebSocketAuthError",
    "WebSocketConnectionError",
    
    # Configuration
    "ConfigurationException",
    "MissingConfigException",
]
