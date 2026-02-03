"""
Shared enumerations for API validation

These enums provide type-safe validation for query parameters
to prevent SQL injection and other security vulnerabilities.
"""

from enum import Enum


class DocumentSortField(str, Enum):
    """
    Allowed sort fields for document queries.

    SECURITY: Only these fields can be used for sorting documents.
    Using an enum prevents SQL injection via arbitrary column names.
    """

    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    TITLE = "title"
    FILENAME = "filename"
    FILE_SIZE = "file_size_bytes"
    PROCESSING_STATUS = "processing_status"
    DOCUMENT_TYPE = "document_type"


class SortOrder(str, Enum):
    """
    Sort order direction.

    SECURITY: Restricts sort order to valid SQL directions only.
    """

    ASC = "asc"
    DESC = "desc"


class EntitySortField(str, Enum):
    """
    Allowed sort fields for entity queries.
    """

    CREATED_AT = "created_at"
    NAME = "name"
    ENTITY_TYPE = "entity_type"
    CONFIDENCE_SCORE = "confidence_score"


class JobSortField(str, Enum):
    """
    Allowed sort fields for processing job queries.
    """

    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    STATUS = "status"
    PRIORITY = "priority"
    STARTED_AT = "started_at"
    COMPLETED_AT = "completed_at"


class SearchSortField(str, Enum):
    """
    Allowed sort fields for search results.
    """

    RELEVANCE = "relevance"
    DATE = "date"
    TITLE = "title"


class UserSortField(str, Enum):
    """
    Allowed sort fields for user queries.
    """

    CREATED_AT = "created_at"
    EMAIL = "email"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    LAST_LOGIN = "last_login_at"


class OrganizationSortField(str, Enum):
    """
    Allowed sort fields for organization queries.
    """

    CREATED_AT = "created_at"
    NAME = "name"
    MEMBER_COUNT = "member_count"


# Model to field mapping for validation
SORT_FIELD_MAPPINGS = {
    "Document": {field.value for field in DocumentSortField},
    "Entity": {field.value for field in EntitySortField},
    "ProcessingJob": {field.value for field in JobSortField},
    "User": {field.value for field in UserSortField},
    "Organization": {field.value for field in OrganizationSortField},
}


def validate_sort_field(model_name: str, field_name: str) -> bool:
    """
    Validate if a sort field is allowed for a given model.

    Args:
        model_name: Name of the SQLAlchemy model
        field_name: Field name to validate

    Returns:
        True if the field is allowed, False otherwise
    """
    allowed_fields = SORT_FIELD_MAPPINGS.get(model_name, set())
    return field_name in allowed_fields
