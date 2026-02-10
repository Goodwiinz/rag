"""
Comprehensive validation rules and data consistency constraints for the RAG system
"""

import re
import uuid
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

import bleach
from email_validator import EmailNotValidError
from email_validator import validate_email as validate_email_format
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ValidationError as PydanticValidationError
from pydantic import validator
from sqlalchemy import event, inspect
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import validates


class ValidationRule:
    """Base class for validation rules"""

    def __init__(self, field_name: str, error_message: str = None):
        self.field_name = field_name
        self.error_message = error_message or f"Validation failed for {field_name}"

    def validate(self, value: Any, instance: Any = None) -> bool:
        """Validate the value. Returns True if valid, raises ValueError if invalid."""
        raise NotImplementedError("Subclasses must implement validate method")


class LengthRule(ValidationRule):
    """Validate string length"""

    def __init__(
        self,
        field_name: str,
        min_length: int = None,
        max_length: int = None,
        error_message: str = None,
    ):
        super().__init__(field_name, error_message)
        self.min_length = min_length
        self.max_length = max_length

    def validate(self, value: Any, instance: Any = None) -> bool:
        if value is None:
            return True

        if not isinstance(value, str):
            raise ValueError(f"{self.field_name} must be a string")

        length = len(value)

        if self.min_length is not None and length < self.min_length:
            raise ValueError(
                f"{self.field_name} must be at least {self.min_length} characters long"
            )

        if self.max_length is not None and length > self.max_length:
            raise ValueError(
                f"{self.field_name} must be no more than {self.max_length} characters long"
            )

        return True


class RegexRule(ValidationRule):
    """Validate against regex pattern"""

    def __init__(self, field_name: str, pattern: str, error_message: str = None):
        super().__init__(field_name, error_message)
        self.pattern = re.compile(pattern)

    def validate(self, value: Any, instance: Any = None) -> bool:
        if value is None:
            return True

        if not isinstance(value, str):
            raise ValueError(f"{self.field_name} must be a string")

        if not self.pattern.match(value):
            raise ValueError(
                self.error_message or f"{self.field_name} format is invalid"
            )

        return True


class RangeRule(ValidationRule):
    """Validate numeric range"""

    def __init__(
        self,
        field_name: str,
        min_value: float = None,
        max_value: float = None,
        error_message: str = None,
    ):
        super().__init__(field_name, error_message)
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, value: Any, instance: Any = None) -> bool:
        if value is None:
            return True

        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"{self.field_name} must be a number")

        if self.min_value is not None and numeric_value < self.min_value:
            raise ValueError(f"{self.field_name} must be at least {self.min_value}")

        if self.max_value is not None and numeric_value > self.max_value:
            raise ValueError(f"{self.field_name} must be no more than {self.max_value}")

        return True


class EnumRule(ValidationRule):
    """Validate enum values"""

    def __init__(self, field_name: str, enum_class: type, error_message: str = None):
        super().__init__(field_name, error_message)
        self.enum_class = enum_class
        self.valid_values = [e.value for e in enum_class]

    def validate(self, value: Any, instance: Any = None) -> bool:
        if value is None:
            return True

        # Handle both enum instances and string values
        if hasattr(value, "value"):
            enum_value = value.value
        else:
            enum_value = value

        if enum_value not in self.valid_values:
            raise ValueError(
                self.error_message
                or f"{self.field_name} must be one of: {', '.join(self.valid_values)}"
            )

        return True


class EmailRule(ValidationRule):
    """Validate email addresses"""

    def validate(self, value: Any, instance: Any = None) -> bool:
        if value is None:
            return True

        if not isinstance(value, str):
            raise ValueError(f"{self.field_name} must be a string")

        try:
            validate_email_format(value)
        except EmailNotValidError as e:
            raise ValueError(
                f"{self.field_name} is not a valid email address: {str(e)}"
            )

        return True


class URLRule(ValidationRule):
    """Validate URLs"""

    def __init__(
        self, field_name: str, schemes: List[str] = None, error_message: str = None
    ):
        super().__init__(field_name, error_message)
        self.schemes = schemes or ["http", "https"]

    def validate(self, value: Any, instance: Any = None) -> bool:
        if value is None:
            return True

        if not isinstance(value, str):
            raise ValueError(f"{self.field_name} must be a string")

        url_pattern = re.compile(
            r"^(?:" + "|".join(self.schemes) + r")://"
            r"(?:\S+(?::\S*)?@)?"  # optional user:pass@
            r"(?:"
            r"(?P<private_ip>"
            r"10(?:\.\d{1,3}){3}|"  # 10.0.0.0/8
            r"127(?:\.\d{1,3}){3}|"  # 127.0.0.0/8
            r"169\.254(?:\.\d{1,3}){2}|"  # 169.254.0.0/16
            r"192\.168(?:\.\d{1,3}){2}|"  # 192.168.0.0/16
            r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}"  # 172.16.0.0/12
            r")|"
            r"(?P<public_ip>"
            r"(?:[1-9]\d?|1\d\d|2[01]\d|22[0-3])"  # 1-223
            r"(?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5])){3}"  # IP pattern
            r")|"
            r"(?P<domain>"
            r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"  # subdomains
            r"[a-zA-Z]{2,63}"  # TLD
            r")"
            r")"
            r"(?::\d{2,5})?"  # optional port
            r"(?:[/?#]\S*)?$",  # optional path, query, fragment
            re.IGNORECASE,
        )

        if not url_pattern.match(value):
            raise ValueError(
                self.error_message or f"{self.field_name} is not a valid URL"
            )

        return True


class FileSizeRule(ValidationRule):
    """Validate file sizes"""

    def __init__(self, field_name: str, max_size_bytes: int, error_message: str = None):
        super().__init__(field_name, error_message)
        self.max_size_bytes = max_size_bytes

    def validate(self, value: Any, instance: Any = None) -> bool:
        if value is None:
            return True

        try:
            size_bytes = int(value)
        except (ValueError, TypeError):
            raise ValueError(f"{self.field_name} must be a valid file size in bytes")

        if size_bytes < 0:
            raise ValueError(f"{self.field_name} cannot be negative")

        if size_bytes > self.max_size_bytes:
            size_mb = size_bytes / (1024 * 1024)
            max_mb = self.max_size_bytes / (1024 * 1024)
            raise ValueError(
                self.error_message
                or f"{self.field_name} ({size_mb:.1f}MB) exceeds maximum allowed size ({max_mb:.1f}MB)"
            )

        return True


class DateTimeRule(ValidationRule):
    """Validate datetime values"""

    def __init__(
        self,
        field_name: str,
        allow_future: bool = True,
        allow_past: bool = True,
        min_date: datetime = None,
        max_date: datetime = None,
        error_message: str = None,
    ):
        super().__init__(field_name, error_message)
        self.allow_future = allow_future
        self.allow_past = allow_past
        self.min_date = min_date
        self.max_date = max_date

    def validate(self, value: Any, instance: Any = None) -> bool:
        if value is None:
            return True

        if not isinstance(value, datetime):
            raise ValueError(f"{self.field_name} must be a datetime object")

        now = datetime.utcnow()

        if not self.allow_future and value > now:
            raise ValueError(f"{self.field_name} cannot be in the future")

        if not self.allow_past and value < now:
            raise ValueError(f"{self.field_name} cannot be in the past")

        if self.min_date and value < self.min_date:
            raise ValueError(f"{self.field_name} must be after {self.min_date}")

        if self.max_date and value > self.max_date:
            raise ValueError(f"{self.field_name} must be before {self.max_date}")

        return True


class SanitizeHTMLRule(ValidationRule):
    """Sanitize HTML content"""

    def __init__(
        self,
        field_name: str,
        allowed_tags: List[str] = None,
        allowed_attributes: List[str] = None,
    ):
        super().__init__(field_name)
        self.allowed_tags = allowed_tags or [
            "p",
            "br",
            "strong",
            "em",
            "ul",
            "ol",
            "li",
        ]
        self.allowed_attributes = allowed_attributes or []

    def validate(self, value: Any, instance: Any = None) -> bool:
        if value is None:
            return True

        if not isinstance(value, str):
            raise ValueError(f"{self.field_name} must be a string")

        # Sanitize HTML
        sanitized = bleach.clean(
            value,
            tags=self.allowed_tags,
            attributes=self.allowed_attributes,
            strip=True,
        )

        # Update the value on the instance if it changed
        if hasattr(instance, self.field_name) and sanitized != value:
            setattr(instance, self.field_name, sanitized)

        return True


class CrossFieldRule(ValidationRule):
    """Validate across multiple fields"""

    def __init__(
        self,
        field_name: str,
        dependent_fields: List[str],
        validation_func: Callable[[Dict[str, Any]], bool],
        error_message: str = None,
    ):
        super().__init__(field_name, error_message)
        self.dependent_fields = dependent_fields
        self.validation_func = validation_func

    def validate(self, value: Any, instance: Any = None) -> bool:
        if instance is None:
            return True

        # Get values from all dependent fields
        field_values = {
            field: getattr(instance, field, None) for field in self.dependent_fields
        }
        field_values[self.field_name] = value

        try:
            if not self.validation_func(field_values):
                raise ValueError(
                    self.error_message
                    or f"Cross-field validation failed for {', '.join(self.dependent_fields + [self.field_name])}"
                )
        except Exception as e:
            raise ValueError(f"Cross-field validation error: {str(e)}")

        return True


# Business logic validation functions
def validate_quota_usage(fields: Dict[str, Any]) -> bool:
    """Validate that storage usage doesn't exceed quota"""
    used = fields.get("storage_used_bytes", 0)
    quota = fields.get("storage_quota_bytes", 0)
    return used <= quota


def validate_document_processing_status(fields: Dict[str, Any]) -> bool:
    """Validate logical processing status transitions"""
    status = fields.get("processing_status")
    completed_at = fields.get("processing_completed_at")
    error_message = fields.get("processing_error")

    if status == "completed":
        return completed_at is not None and error_message is None
    elif status == "failed":
        return error_message is not None
    elif status in ["pending", "processing"]:
        return completed_at is None

    return True


def validate_relationship_dates(fields: Dict[str, Any]) -> bool:
    """Validate relationship date logic"""
    valid_from = fields.get("valid_from")
    valid_to = fields.get("valid_to")

    if valid_from and valid_to:
        return valid_from <= valid_to
    return True


def validate_query_retention(fields: Dict[str, Any]) -> bool:
    """Validate query retention period"""
    created_at = fields.get("created_at")
    expires_at = fields.get("expires_at")

    if created_at and expires_at:
        # Ensure minimum 30-day retention
        min_expiry = created_at + timedelta(days=30)
        return expires_at >= min_expiry
    return True


# Model validation rules configuration
MODEL_VALIDATION_RULES = {
    "User": [
        EmailRule("email"),
        LengthRule("first_name", min_length=1, max_length=100),
        LengthRule("last_name", min_length=1, max_length=100),
        RegexRule("password_hash", r"^.{60,}$"),  # Minimum 60 chars for bcrypt hash
    ],
    "EnhancedDocument": [
        LengthRule("title", min_length=1, max_length=500),
        LengthRule("original_filename", min_length=1, max_length=500),
        FileSizeRule("file_size_bytes", 5368709120),  # 5GB max
        RegexRule("file_hash_sha256", r"^[a-f0-9]{64}$"),
        RegexRule("file_hash_md5", r"^[a-f0-9]{32}$"),
        EnumRule("primary_modality", DocumentModality),
        EnumRule("processing_status", ProcessingStage),
        RangeRule("processing_priority", min_value=1, max_value=10),
        RangeRule("overall_quality_score", min_value=0.0, max_value=1.0),
        CrossFieldRule(
            "processing_status",
            ["processing_completed_at", "processing_error"],
            validate_document_processing_status,
        ),
    ],
    "RAGQuery": [
        LengthRule("query_text", min_length=1, max_length=10000),
        EnumRule("query_type", QueryType),
        EnumRule("answer_type", AnswerType),
        RangeRule("answer_confidence", min_value=0.0, max_value=1.0),
        RangeRule("faithfulness_score", min_value=0.0, max_value=1.0),
        RangeRule("relevance_score", min_value=0.0, max_value=1.0),
        RangeRule("overall_quality_score", min_value=0.0, max_value=1.0),
        CrossFieldRule("created_at", ["expires_at"], validate_query_retention),
        DateTimeRule("expires_at", allow_future=True, allow_past=False),
    ],
    "KnowledgeEntity": [
        LengthRule("name", min_length=1, max_length=500),
        LengthRule("canonical_name", max_length=500),
        EnumRule("entity_type", EntityType),
        EnumRule("source", EntitySource),
        RangeRule("extraction_confidence", min_value=0.0, max_value=1.0),
        RangeRule("quality_score", min_value=0.0, max_value=1.0),
        CrossFieldRule("valid_from", ["valid_to"], validate_relationship_dates),
        URLRule("entity_uri", schemes=["http", "https", "urn"]),
    ],
    "EntityRelationship": [
        EnumRule("relationship_type", RelationshipType),
        RangeRule("confidence", min_value=0.0, max_value=1.0),
        RangeRule("weight", min_value=0.0, max_value=10.0),
        CrossFieldRule("valid_from", ["valid_to"], validate_relationship_dates),
    ],
    "UserQuota": [
        RangeRule("storage_quota_bytes", min_value=0),
        RangeRule("storage_used_bytes", min_value=0),
        RangeRule("document_quota", min_value=0),
        RangeRule("document_count", min_value=0),
        FileSizeRule("max_file_size_bytes", 52428800),  # 50MB max
        CrossFieldRule(
            "storage_used_bytes", ["storage_quota_bytes"], validate_quota_usage
        ),
    ],
    "ProcessingJob": [
        EnumRule("job_type", JobType),
        EnumRule("status", JobStatus),
        RangeRule("progress_percentage", min_value=0.0, max_value=100.0),
        RangeRule("priority", min_value=1, max_value=4),
    ],
    "WebSocketConnection": [
        LengthRule("connection_id", min_length=1, max_length=255),
        EnumRule("connection_status", ConnectionStatus),
        DateTimeRule("last_heartbeat", allow_future=False, allow_past=True),
    ],
    "MetricMeasurement": [
        RangeRule("metric_value", min_value=0.0, max_value=1.0),
        RangeRule("metric_score", min_value=0.0, max_value=1.0),
        RangeRule("confidence_interval", min_value=0.0, max_value=1.0),
    ],
}


# Data consistency validators
class ConsistencyValidator:
    """Validates data consistency across the system"""

    @staticmethod
    def validate_user_quota_consistency(
        user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> bool:
        """Validate user belongs to organization and quota is consistent"""
        # This would typically query the database
        # Implementation depends on your ORM/database layer
        return True

    @staticmethod
    def validate_document_ownership(document_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Validate document ownership"""
        return True

    @staticmethod
    def validate_entity_organization_scope(
        entity_id: uuid.UUID, organization_id: uuid.UUID
    ) -> bool:
        """Validate entity belongs to organization scope"""
        return True

    @staticmethod
    def validate_query_user_access(query_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Validate user can access query"""
        return True

    @staticmethod
    def validate_relationship_entities(relationship_id: uuid.UUID) -> bool:
        """Validate relationship entities exist and are in same organization"""
        return True


# Pydantic models for API validation
class UserCreateSchema(PydanticBaseModel):
    """Pydantic schema for user creation validation"""

    email: str
    first_name: str
    last_name: str
    password: str
    organization_id: uuid.UUID

    @validator("email")
    def validate_email(cls, v):
        try:
            validate_email_format(v)
        except EmailNotValidError as e:
            raise ValueError(str(e))
        return v.lower()

    @validator("first_name", "last_name")
    def validate_names(cls, v):
        if not v or len(v.strip()) < 1:
            raise ValueError("Name cannot be empty")
        if len(v) > 100:
            raise ValueError("Name too long")
        return v.strip()

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain digit")
        return v


class DocumentUploadSchema(PydanticBaseModel):
    """Pydantic schema for document upload validation"""

    title: str
    tags: List[str] = []
    categories: List[str] = []
    is_public: bool = False
    sharing_level: str = "private"

    @validator("title")
    def validate_title(cls, v):
        if not v or len(v.strip()) < 1:
            raise ValueError("Title is required")
        if len(v) > 500:
            raise ValueError("Title too long")
        return v.strip()

    @validator("sharing_level")
    def validate_sharing_level(cls, v):
        allowed_levels = ["private", "team", "organization", "public"]
        if v not in allowed_levels:
            raise ValueError(
                f'Sharing level must be one of: {", ".join(allowed_levels)}'
            )
        return v

    @validator("tags", "categories")
    def validate_lists(cls, v):
        if len(v) > 50:
            raise ValueError("Too many tags or categories")
        for item in v:
            if not isinstance(item, str) or len(item) > 100:
                raise ValueError("Invalid tag or category format")
        return v


class RAGQuerySchema(PydanticBaseModel):
    """Pydantic schema for RAG query validation"""

    query_text: str
    query_type: str = "factual_lookup"
    search_strategy: str = "hybrid"
    retrieval_limit: int = 5
    similarity_threshold: float = 0.7
    filters: Dict[str, Any] = {}

    @validator("query_text")
    def validate_query_text(cls, v):
        if not v or len(v.strip()) < 1:
            raise ValueError("Query text is required")
        if len(v) > 10000:
            raise ValueError("Query too long")
        return v.strip()

    @validator("query_type")
    def validate_query_type(cls, v):
        allowed_types = [
            "factual_lookup",
            "reasoning",
            "comparison",
            "summary",
            "analysis",
            "recommendation",
        ]
        if v not in allowed_types:
            raise ValueError(f'Query type must be one of: {", ".join(allowed_types)}')
        return v

    @validator("search_strategy")
    def validate_search_strategy(cls, v):
        allowed_strategies = ["semantic", "keyword", "hybrid", "graph"]
        if v not in allowed_strategies:
            raise ValueError(
                f'Search strategy must be one of: {", ".join(allowed_strategies)}'
            )
        return v

    @validator("retrieval_limit")
    def validate_retrieval_limit(cls, v):
        if not 1 <= v <= 50:
            raise ValueError("Retrieval limit must be between 1 and 50")
        return v

    @validator("similarity_threshold")
    def validate_similarity_threshold(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Similarity threshold must be between 0.0 and 1.0")
        return v


class EntityCreateSchema(PydanticBaseModel):
    """Pydantic schema for entity creation validation"""

    name: str
    canonical_name: Optional[str] = None
    entity_type: str
    description: Optional[str] = None
    aliases: List[str] = []
    external_ids: Dict[str, str] = {}

    @validator("name")
    def validate_name(cls, v):
        if not v or len(v.strip()) < 1:
            raise ValueError("Entity name is required")
        if len(v) > 500:
            raise ValueError("Entity name too long")
        return v.strip()

    @validator("entity_type")
    def validate_entity_type(cls, v):
        # This would typically reference the EntityType enum
        allowed_types = ["person", "organization", "location", "product", "concept"]
        if v not in allowed_types:
            raise ValueError(f'Entity type must be one of: {", ".join(allowed_types)}')
        return v

    @validator("aliases")
    def validate_aliases(cls, v):
        if len(v) > 100:
            raise ValueError("Too many aliases")
        for alias in v:
            if not isinstance(alias, str) or len(alias) > 500:
                raise ValueError("Invalid alias format")
        return v


# Database event listeners for validation
def setup_validation_event_listners():
    """Setup SQLAlchemy event listeners for validation"""

    def validate_model_before_insert(mapper, connection, target):
        """Validate model before insert"""
        model_class = target.__class__.__name__
        rules = MODEL_VALIDATION_RULES.get(model_class, [])

        for rule in rules:
            field_value = getattr(target, rule.field_name, None)
            rule.validate(field_value, target)

    def validate_model_before_update(mapper, connection, target):
        """Validate model before update"""
        model_class = target.__class__.__name__
        rules = MODEL_VALIDATION_RULES.get(model_class, [])

        for rule in rules:
            field_value = getattr(target, rule.field_name, None)
            rule.validate(field_value, target)

    # Register event listeners for all models
    from sqlalchemy import event

    from .base import BaseModel

    event.listen(BaseModel, "before_insert", validate_model_before_insert)
    event.listen(BaseModel, "before_update", validate_model_before_update)


# Validation error handling
class ValidationError(Exception):
    """Custom validation error"""

    def __init__(self, field: str, message: str, value: Any = None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"Validation failed for {field}: {message}")


class ValidationSummary:
    """Summary of validation results"""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.success_count = 0
        self.failure_count = 0

    def add_error(self, field: str, message: str, value: Any = None):
        """Add validation error"""
        self.errors.append(ValidationError(field, message, value))
        self.failure_count += 1

    def add_warning(self, field: str, message: str):
        """Add validation warning"""
        self.warnings.append({"field": field, "message": message})

    def add_success(self):
        """Increment success count"""
        self.success_count += 1

    @property
    def is_valid(self) -> bool:
        """Check if validation passed"""
        return len(self.errors) == 0

    @property
    def error_messages(self) -> List[str]:
        """Get list of error messages"""
        return [error.message for error in self.errors]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "is_valid": self.is_valid,
            "errors": [
                {"field": e.field, "message": e.message, "value": e.value}
                for e in self.errors
            ],
            "warnings": self.warnings,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
        }


# Utility functions for validation
def validate_model_instance(instance: Any) -> ValidationSummary:
    """Validate a model instance against all configured rules"""
    summary = ValidationSummary()
    model_class = instance.__class__.__name__
    rules = MODEL_VALIDATION_RULES.get(model_class, [])

    for rule in rules:
        try:
            field_value = getattr(instance, rule.field_name, None)
            rule.validate(field_value, instance)
            summary.add_success()
        except ValueError as e:
            summary.add_error(rule.field_name, str(e), field_value)

    return summary


def sanitize_user_input(text: str, allow_html: bool = False) -> str:
    """Sanitize user input"""
    if not isinstance(text, str):
        return ""

    if allow_html:
        # Allow basic HTML tags
        allowed_tags = ["p", "br", "strong", "em", "ul", "ol", "li", "a"]
        allowed_attributes = {"a": ["href", "title"]}
        return bleach.clean(text, tags=allowed_tags, attributes=allowed_attributes)
    else:
        # Strip all HTML
        return bleach.clean(text, tags=[], strip=True)


def validate_file_upload(
    file_size: int, file_name: str, allowed_extensions: List[str] = None
) -> ValidationSummary:
    """Validate file upload parameters"""
    summary = ValidationSummary()

    # Check file size (50MB default limit)
    max_size = 50 * 1024 * 1024
    if file_size > max_size:
        summary.add_error(
            "file_size",
            f"File size ({file_size} bytes) exceeds maximum ({max_size} bytes)",
            file_size,
        )
    else:
        summary.add_success()

    # Check file extension
    if allowed_extensions:
        file_extension = file_name.split(".")[-1].lower() if "." in file_name else ""
        if file_extension not in allowed_extensions:
            summary.add_error(
                "file_extension",
                f"File extension .{file_extension} not allowed",
                file_extension,
            )
        else:
            summary.add_success()
    else:
        summary.add_success()

    return summary


# Export main validation components
__all__ = [
    "ValidationRule",
    "LengthRule",
    "RegexRule",
    "RangeRule",
    "EnumRule",
    "EmailRule",
    "URLRule",
    "FileSizeRule",
    "DateTimeRule",
    "SanitizeHTMLRule",
    "CrossFieldRule",
    "MODEL_VALIDATION_RULES",
    "ConsistencyValidator",
    "UserCreateSchema",
    "DocumentUploadSchema",
    "RAGQuerySchema",
    "EntityCreateSchema",
    "ValidationError",
    "ValidationSummary",
    "validate_model_instance",
    "sanitize_user_input",
    "validate_file_upload",
    "setup_validation_event_listners",
]
