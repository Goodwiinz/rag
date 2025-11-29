"""
Shared exceptions for microservices
"""

from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status


class BaseCustomException(Exception):
    """Base custom exception"""

    def __init__(
        self,
        message: str,
        error_code: str,
        error_type: str = "custom_error",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.error_type = error_type
        self.status_code = status_code
        self.details = details or {}
        self.suggestions = suggestions or []
        super().__init__(self.message)


class ValidationError(BaseCustomException):
    """Validation error"""

    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            error_type="validation_error",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
            suggestions=[
                "Check request parameters",
                "Verify data format",
                "Review API documentation"
            ]
        )


class AuthenticationError(BaseCustomException):
    """Authentication error"""

    def __init__(
        self,
        message: str = "Authentication failed"
    ):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            error_type="authentication_error",
            status_code=status.HTTP_401_UNAUTHORIZED,
            suggestions=[
                "Check your credentials",
                "Verify token is valid",
                "Try logging in again"
            ]
        )


class AuthorizationError(BaseCustomException):
    """Authorization error"""

    def __init__(
        self,
        message: str = "Access denied",
        required_permission: Optional[str] = None
    ):
        details = {}
        if required_permission:
            details["required_permission"] = required_permission

        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            error_type="authorization_error",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
            suggestions=[
                "Check your permissions",
                "Contact administrator",
                "Verify account status"
            ]
        )


class NotFoundError(BaseCustomException):
    """Resource not found error"""

    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None
    ):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id

        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            error_type="not_found_error",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
            suggestions=[
                "Verify resource ID",
                "Check if resource exists",
                "Review access permissions"
            ]
        )


class ConflictError(BaseCustomException):
    """Resource conflict error"""

    def __init__(
        self,
        message: str = "Resource conflict",
        resource_type: Optional[str] = None,
        conflict_details: Optional[Dict[str, Any]] = None
    ):
        details = conflict_details or {}
        if resource_type:
            details["resource_type"] = resource_type

        super().__init__(
            message=message,
            error_code="CONFLICT",
            error_type="conflict_error",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
            suggestions=[
                "Check for duplicate resources",
                "Verify resource state",
                "Review recent changes"
            ]
        )


class RateLimitError(BaseCustomException):
    """Rate limiting error"""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        limit: Optional[int] = None,
        window: Optional[int] = None
    ):
        details = {}
        if retry_after:
            details["retry_after"] = retry_after
        if limit:
            details["limit"] = limit
        if window:
            details["window"] = window

        suggestions = ["Wait before making another request"]
        if retry_after:
            suggestions.append(f"Try again after {retry_after} seconds")

        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            error_type="rate_limit_error",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
            suggestions=suggestions
        )


class StorageQuotaError(BaseCustomException):
    """Storage quota exceeded error"""

    def __init__(
        self,
        message: str = "Storage quota exceeded",
        current_usage_mb: Optional[float] = None,
        quota_limit_mb: Optional[int] = None
    ):
        details = {}
        if current_usage_mb:
            details["current_usage_mb"] = current_usage_mb
        if quota_limit_mb:
            details["quota_limit_mb"] = quota_limit_mb

        super().__init__(
            message=message,
            error_code="STORAGE_QUOTA_EXCEEDED",
            error_type="storage_quota_error",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
            suggestions=[
                "Delete unused documents",
                "Upgrade storage plan",
                "Contact administrator"
            ]
        )


class ProcessingError(BaseCustomException):
    """Document processing error"""

    def __init__(
        self,
        message: str = "Processing failed",
        document_id: Optional[str] = None,
        stage: Optional[str] = None,
        retry_count: Optional[int] = None
    ):
        details = {}
        if document_id:
            details["document_id"] = document_id
        if stage:
            details["stage"] = stage
        if retry_count:
            details["retry_count"] = retry_count

        super().__init__(
            message=message,
            error_code="PROCESSING_ERROR",
            error_type="processing_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
            suggestions=[
                "Check document format",
                "Verify file integrity",
                "Try re-uploading the document",
                "Contact support if issue persists"
            ]
        )


class SearchError(BaseCustomException):
    """Search operation error"""

    def __init__(
        self,
        message: str = "Search failed",
        query: Optional[str] = None,
        search_type: Optional[str] = None
    ):
        details = {}
        if query:
            details["query"] = query
        if search_type:
            details["search_type"] = search_type

        super().__init__(
            message=message,
            error_code="SEARCH_ERROR",
            error_type="search_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
            suggestions=[
                "Simplify search query",
                "Try different keywords",
                "Check search filters",
                "Contact support if issue persists"
            ]
        )


class VectorStoreError(BaseCustomException):
    """Vector store operation error"""

    def __init__(
        self,
        message: str = "Vector store operation failed",
        operation: Optional[str] = None,
        collection: Optional[str] = None
    ):
        details = {}
        if operation:
            details["operation"] = operation
        if collection:
            details["collection"] = collection

        super().__init__(
            message=message,
            error_code="VECTOR_STORE_ERROR",
            error_type="vector_store_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
            suggestions=[
                "Check vector store connection",
                "Verify collection exists",
                "Try the operation again",
                "Contact support if issue persists"
            ]
        )


class KnowledgeGraphError(BaseCustomException):
    """Knowledge graph operation error"""

    def __init__(
        self,
        message: str = "Knowledge graph operation failed",
        operation: Optional[str] = None,
        entity_type: Optional[str] = None
    ):
        details = {}
        if operation:
            details["operation"] = operation
        if entity_type:
            details["entity_type"] = entity_type

        super().__init__(
            message=message,
            error_code="KNOWLEDGE_GRAPH_ERROR",
            error_type="knowledge_graph_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
            suggestions=[
                "Check graph database connection",
                "Verify entity data",
                "Try the operation again",
                "Contact support if issue persists"
            ]
        )


class EvaluationError(BaseCustomException):
    """Evaluation operation error"""

    def __init__(
        self,
        message: str = "Evaluation failed",
        evaluation_type: Optional[str] = None,
        query_id: Optional[str] = None
    ):
        details = {}
        if evaluation_type:
            details["evaluation_type"] = evaluation_type
        if query_id:
            details["query_id"] = query_id

        super().__init__(
            message=message,
            error_code="EVALUATION_ERROR",
            error_type="evaluation_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
            suggestions=[
                "Check evaluation parameters",
                "Verify query and answer format",
                "Try the evaluation again",
                "Contact support if issue persists"
            ]
        )


class FileUploadError(BaseCustomException):
    """File upload error"""

    def __init__(
        self,
        message: str = "File upload failed",
        filename: Optional[str] = None,
        file_size: Optional[int] = None,
        mime_type: Optional[str] = None
    ):
        details = {}
        if filename:
            details["filename"] = filename
        if file_size:
            details["file_size"] = file_size
        if mime_type:
            details["mime_type"] = mime_type

        super().__init__(
            message=message,
            error_code="FILE_UPLOAD_ERROR",
            error_type="file_upload_error",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
            suggestions=[
                "Check file format",
                "Verify file size limit",
                "Ensure file is not corrupted",
                "Try uploading again"
            ]
        )


class ServiceUnavailableError(BaseCustomException):
    """Service unavailable error"""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        service_name: Optional[str] = None,
        retry_after: Optional[int] = None
    ):
        details = {}
        if service_name:
            details["service_name"] = service_name

        suggestions = ["Try again later"]
        if retry_after:
            suggestions.append(f"Retry after {retry_after} seconds")

        super().__init__(
            message=message,
            error_code="SERVICE_UNAVAILABLE",
            error_type="service_unavailable_error",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
            suggestions=suggestions
        )


class DatabaseError(BaseCustomException):
    """Database operation error"""

    def __init__(
        self,
        message: str = "Database operation failed",
        operation: Optional[str] = None,
        table: Optional[str] = None
    ):
        details = {}
        if operation:
            details["operation"] = operation
        if table:
            details["table"] = table

        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            error_type="database_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
            suggestions=[
                "Try the operation again",
                "Contact support if issue persists"
            ]
        )


class CacheError(BaseCustomException):
    """Cache operation error"""

    def __init__(
        self,
        message: str = "Cache operation failed",
        operation: Optional[str] = None,
        key: Optional[str] = None
    ):
        details = {}
        if operation:
            details["operation"] = operation
        if key:
            details["key"] = key

        super().__init__(
            message=message,
            error_code="CACHE_ERROR",
            error_type="cache_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
            suggestions=[
                "Try the operation again",
                "Contact support if issue persists"
            ]
        )


class ExternalServiceError(BaseCustomException):
    """External service error"""

    def __init__(
        self,
        message: str = "External service error",
        service_name: Optional[str] = None,
        status_code: Optional[int] = None
    ):
        details = {}
        if service_name:
            details["service_name"] = service_name
        if status_code:
            details["status_code"] = status_code

        super().__init__(
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            error_type="external_service_error",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
            suggestions=[
                "Try the operation again",
                "Contact support if issue persists"
            ]
        )


# HTTP Exception factory
def create_http_exception(exc: BaseCustomException) -> HTTPException:
    """Create HTTPException from custom exception"""
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "error": {
                "message": exc.message,
                "error_code": exc.error_code,
                "error_type": exc.error_type,
                "details": exc.details,
                "suggestions": exc.suggestions
            }
        }
    )


# Exception handler decorator
def handle_exceptions(func):
    """Decorator to handle custom exceptions"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except BaseCustomException as e:
            raise create_http_exception(e)
        except Exception as e:
            # Log unexpected exceptions
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)

            raise create_http_exception(BaseCustomException(
                message="Internal server error",
                error_code="INTERNAL_ERROR",
                error_type="internal_error"
            ))
    return wrapper