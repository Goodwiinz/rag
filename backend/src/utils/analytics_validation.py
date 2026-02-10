"""
Analytics validation utilities for input sanitization and security
Provides comprehensive validation and sanitization functions for analytics data
"""

import hashlib
import html
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import unquote

try:
    import bleach

    HAS_BLEACH = True
except ImportError:
    bleach = None
    HAS_BLEACH = False
    bleach = None  # Define bleach as None if import fails for consistent module attribute access

# Security configurations
MAX_STRING_LENGTH = 10000
MAX_QUERY_PARAMS = 50
MAX_LIST_ITEMS = 1000
MAX_NESTING_DEPTH = 10

# Allowed HTML tags for rich text (if needed)
ALLOWED_HTML_TAGS = ["b", "i", "em", "strong", "span", "br"]
ALLOWED_HTML_ATTRIBUTES = {"span": ["class"], "*": ["title"]}

# SQL injection patterns
SQL_INJECTION_PATTERNS = [
    r"(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
    r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
    r"(\'\s*(OR|AND)\s*\'.*\'\s*=\s*\'.*\')",
    r"(\;\s*(DROP|DELETE|INSERT|UPDATE))",
    r"(\/\*.*\*\/)",
    r"(--.*$)",
    r"(\b(WAITFOR|DELAY)\s+)",
    r"(\b(BENCHMARK|SLEEP)\s*\()",
    r"(\b(USER|VERSION|DATABASE)\s*\()",
    r"(\'\s*OR\s*\'[^']+\'\s*=\s*\'[^']+\')",
    r"(\'\s*OR\s*\'?\w+\'?\s*=\s*\'?\w+\'?)",
]

# XSS patterns
XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"vbscript:",
    r"onload\s*=",
    r"onerror\s*=",
    r"onclick\s*=",
    r"onmouseover\s*=",
    r"<iframe[^>]*>",
    r"<object[^>]*>",
    r"<embed[^>]*>",
    r"<link[^>]*>",
    r"<meta[^>]*>",
]


class AnalyticsValidationError(Exception):
    """Custom exception for analytics validation errors"""

    pass


class SecurityValidator:
    """Security-focused validator for analytics inputs"""

    @staticmethod
    def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize string input to prevent injection attacks

        Args:
            value: Input string to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            raise AnalyticsValidationError(f"Expected string, got {type(value)}")

        # Trim whitespace
        value = value.strip()

        # Apply max length limit
        if max_length:
            value = value[:max_length]
        elif len(value) > MAX_STRING_LENGTH:
            raise AnalyticsValidationError(
                f"String too long: {len(value)} > {MAX_STRING_LENGTH}"
            )

        # HTML entity decode
        try:
            value = html.unescape(value)
            value = unquote(value)
        except Exception:
            pass

        # Remove SQL injection patterns
        for pattern in SQL_INJECTION_PATTERNS:
            value = re.sub(pattern, "", value, flags=re.IGNORECASE | re.MULTILINE)

        # Remove XSS patterns
        for pattern in XSS_PATTERNS:
            value = re.sub(pattern, "", value, flags=re.IGNORECASE | re.MULTILINE)

        # Remove control characters except newlines and tabs
        value = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", value)

        # Normalize whitespace
        value = re.sub(r"\s+", " ", value)

        # Final security check with bleach if available
        if HAS_BLEACH and bleach:
            value = bleach.clean(
                value,
                tags=ALLOWED_HTML_TAGS,
                attributes=ALLOWED_HTML_ATTRIBUTES,
                strip=True,
            )

        return value.strip()

    @staticmethod
    def validate_identifier(value: str, field_name: str = "identifier") -> str:
        """
        Validate identifier fields (user_id, organization_id, etc.)

        Args:
            value: Identifier value to validate
            field_name: Name of the field for error messages

        Returns:
            Validated identifier
        """
        if not isinstance(value, str):
            raise AnalyticsValidationError(f"{field_name} must be a string")

        value = value.strip()

        # Check for valid UUID format (common for IDs)
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        if not re.match(uuid_pattern, value, re.IGNORECASE):
            raise AnalyticsValidationError(f"{field_name} must be a valid UUID")

        return value

    @staticmethod
    def validate_component_name(value: str) -> str:
        """
        Validate component names (API endpoints, service names)

        Args:
            value: Component name to validate

        Returns:
            Validated component name
        """
        if not isinstance(value, str):
            raise AnalyticsValidationError("Component name must be a string")

        value = SecurityValidator.sanitize_string(value, 100).strip()

        # Allow only alphanumeric, underscore, dash, dot, forward slash
        if not re.match(r"^[a-zA-Z0-9_\-\.\/]+$", value):
            raise AnalyticsValidationError("Component name contains invalid characters")

        # Prevent directory traversal
        if ".." in value or value.startswith("/"):
            raise AnalyticsValidationError("Invalid component name format")

        return value

    @staticmethod
    def validate_search_query(value: str) -> str:
        """
        Validate search query strings

        Args:
            value: Search query to validate

        Returns:
            Validated search query
        """
        if not isinstance(value, str):
            raise AnalyticsValidationError("Search query must be a string")

        value = SecurityValidator.sanitize_string(value, 500).strip()

        # Additional validation for search queries
        if len(value) < 1:
            raise AnalyticsValidationError("Search query too short")

        # Remove excessive repetition
        value = re.sub(r"(.)\1{5,}", r"\1", value)

        return value

    @staticmethod
    def validate_numeric_range(
        value: Union[int, float],
        min_val: Optional[Union[int, float]] = None,
        max_val: Optional[Union[int, float]] = None,
        field_name: str = "value",
    ) -> Union[int, float]:
        """
        Validate numeric values within ranges

        Args:
            value: Numeric value to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            field_name: Name of the field for error messages

        Returns:
            Validated numeric value
        """
        if not isinstance(value, (int, float)):
            raise AnalyticsValidationError(f"{field_name} must be numeric")

        if min_val is not None and value < min_val:
            raise AnalyticsValidationError(
                f"{field_name} is below minimum ({min_val})"
            )

        if max_val is not None and value > max_val:
            raise AnalyticsValidationError(
                f"{field_name} is above maximum ({max_val})"
            )

        return value

    @staticmethod
    def validate_datetime_range(
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        max_range_days: int = 365,
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """
        Validate datetime range queries

        Args:
            start_date: Start date
            end_date: End date
            max_range_days: Maximum allowed range in days

        Returns:
            Tuple of validated (start_date, end_date)
        """
        if start_date and end_date:
            if start_date >= end_date:
                raise AnalyticsValidationError("Start time cannot be after end time")

            # Check range limit
            max_range = timedelta(days=max_range_days)
            if end_date - start_date > max_range:
                raise AnalyticsValidationError(
                    f"Date range cannot exceed {max_range_days} days"
                )

            # Don't allow future dates
            if end_date > datetime.utcnow():
                raise AnalyticsValidationError("End date cannot be in the future")

        return start_date, end_date

    @staticmethod
    def validate_list_input(
        value: List[Any],
        item_type_or_max_items: Any = None,
        max_items: int = MAX_LIST_ITEMS,
        field_name: str = "list",
    ) -> List[Any]:
        """
        Validate list inputs

        Args:
            value: List to validate
            item_type_or_max_items: Expected item type OR max items (legacy)
            max_items: Maximum number of items allowed
            field_name: Name of the field for error messages

        Returns:
            Validated list
        """
        if not isinstance(value, list):
            raise AnalyticsValidationError(f"{field_name} must be a list")

        # Backward-compatible calling conventions:
        # validate_list_input(items, str) -> enforce item type
        # validate_list_input(items, 10, "name") -> enforce max items
        item_type = None
        if isinstance(item_type_or_max_items, type):
            item_type = item_type_or_max_items
        elif isinstance(item_type_or_max_items, int):
            max_items = item_type_or_max_items
        elif item_type_or_max_items is not None:
            raise AnalyticsValidationError(
                f"{field_name} validator configuration is invalid"
            )

        if len(value) > max_items:
            raise AnalyticsValidationError(f"{field_name} has too many items")

        if item_type is not None:
            for idx, item in enumerate(value):
                if not isinstance(item, item_type):
                    raise AnalyticsValidationError(
                        f"Item at index {idx} is not of type {item_type.__name__}"
                    )

        return value

    @staticmethod
    def validate_pagination(limit: int, offset: int) -> tuple[int, int]:
        """
        Validate pagination parameters.
        """
        if not isinstance(limit, int) or limit < 1 or limit > 10000:
            raise AnalyticsValidationError("Limit must be between 1 and 10000")

        if not isinstance(offset, int) or offset < 0:
            raise AnalyticsValidationError("Offset must be >= 0")

        if offset > 100000:
            raise AnalyticsValidationError(
                "Offset too large, please use time-based filtering instead"
            )

        return limit, offset

    @staticmethod
    def validate_dict_input(
        value: Dict[str, Any],
        max_keys: int = MAX_QUERY_PARAMS,
        max_depth: int = MAX_NESTING_DEPTH,
        field_name: str = "dictionary",
    ) -> Dict[str, Any]:
        """
        Validate dictionary inputs (JSON objects)

        Args:
            value: Dictionary to validate
            max_keys: Maximum number of keys allowed
            max_depth: Maximum nesting depth
            field_name: Name of the field for error messages

        Returns:
            Validated dictionary
        """
        if not isinstance(value, dict):
            raise AnalyticsValidationError(f"{field_name} must be a dictionary")

        if len(value) > max_keys:
            raise AnalyticsValidationError(
                f"{field_name} cannot contain more than {max_keys} keys"
            )

        # Check nesting depth
        def check_depth(obj, current_depth=0):
            if current_depth > max_depth:
                raise AnalyticsValidationError(
                    f"{field_name} nesting depth exceeds {max_depth}"
                )

            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(k, str):
                        SecurityValidator.sanitize_string(k, 100)
                    check_depth(v, current_depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, current_depth + 1)

        check_depth(value)
        return value

    @staticmethod
    def validate_pagination(limit: int, offset: int) -> tuple[int, int]:
        """
        Validate pagination parameters

        Args:
            limit: Number of items to return
            offset: Number of items to skip

        Returns:
            Tuple of validated (limit, offset)
        """
        limit = SecurityValidator.validate_numeric_range(limit, 1, 10000, "limit")
        offset = SecurityValidator.validate_numeric_range(offset, 0, None, "offset")

        # Prevent excessive pagination
        if offset > 100000:
            raise AnalyticsValidationError(
                "Offset too large, please use time-based filtering instead"
            )

        return limit, offset


class QueryParameterValidator:
    """Validator for analytics query parameters"""

    @staticmethod
    def validate_pagination(limit: int, offset: int) -> tuple[int, int]:
        """
        Validate pagination parameters

        Args:
            limit: Number of items to return
            offset: Number of items to skip

        Returns:
            Tuple of validated (limit, offset)
        """
        # Delegate to SecurityValidator for implementation
        return SecurityValidator.validate_pagination(limit, offset)

    @staticmethod
    def validate_sort_fields(fields: List[str], allowed_fields: List[str]) -> List[str]:
        """
        Validate sort field names

        Args:
            fields: List of fields to sort by
            allowed_fields: List of allowed field names

        Returns:
            Validated list of sort fields
        """
        fields = SecurityValidator.validate_list_input(fields, 10, "sort fields")

        for field in fields:
            if field not in allowed_fields:
                raise AnalyticsValidationError(f"Invalid sort field: {field}")

        return fields

    @staticmethod
    def validate_group_by_fields(
        fields: List[str], allowed_fields: List[str]
    ) -> List[str]:
        """
        Validate group by field names

        Args:
            fields: List of fields to group by
            allowed_fields: List of allowed field names

        Returns:
            Validated list of group by fields
        """
        fields = SecurityValidator.validate_list_input(fields, 10, "group by fields")

        for field in fields:
            if field not in allowed_fields:
                raise AnalyticsValidationError(f"Invalid group by field: {field}")

        return fields

    @staticmethod
    def validate_time_bucket(bucket_size: str) -> str:
        """
        Validate time bucket size for aggregation

        Args:
            bucket_size: Time bucket size (minute, hour, day, week, month)

        Returns:
            Validated bucket size
        """
        allowed_buckets = ["minute", "hour", "day", "week", "month"]
        bucket_size = SecurityValidator.sanitize_string(bucket_size, 10).lower()

        if bucket_size not in allowed_buckets:
            raise AnalyticsValidationError(
                f"Invalid bucket size: {bucket_size}. Allowed: {allowed_buckets}"
            )

        return bucket_size


class DataQualityValidator:
    """Validator for data quality and completeness"""

    @staticmethod
    def calculate_completeness(
        data: Dict[str, Any], required_fields: List[str]
    ) -> float:
        """
        Calculate data completeness percentage

        Args:
            data: Data dictionary to check
            required_fields: List of required field names

        Returns:
            Completeness percentage (0-100)
        """
        if not required_fields:
            return 100.0

        present_fields = 0
        for field in required_fields:
            if field in data and data[field] is not None:
                if isinstance(data[field], str):
                    if data[field].strip():  # Non-empty string
                        present_fields += 1
                elif isinstance(data[field], (list, dict)):
                    if data[field]:  # Non-empty collection
                        present_fields += 1
                else:
                    present_fields += 1

        return (present_fields / len(required_fields)) * 100

    @staticmethod
    def validate_data_consistency(data_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate data consistency across multiple data points

        Args:
            data_points: List of data point dictionaries

        Returns:
            Consistency validation results
        """
        if not data_points:
            return {"is_consistent": True, "issues": []}

        issues = []

        # Check field consistency
        all_fields = set()
        for point in data_points:
            all_fields.update(point.keys())

        for i, point in enumerate(data_points):
            missing_fields = all_fields - set(point.keys())
            if missing_fields:
                issues.append(f"Data point {i} missing fields: {missing_fields}")

        # Check data type consistency
        field_types = {}
        for field in all_fields:
            types = set()
            for point in data_points:
                if field in point and point[field] is not None:
                    types.add(type(point[field]).__name__)

            if len(types) > 1:
                field_types[field] = list(types)

        if field_types:
            issues.append(f"Inconsistent data types: {field_types}")

        return {
            "is_consistent": len(issues) == 0,
            "issues": issues,
            "total_points": len(data_points),
            "fields_checked": list(all_fields),
        }


class AnalyticsInputSanitizer:
    """Main sanitizer class for analytics inputs"""

    def __init__(self):
        self.security_validator = SecurityValidator()
        self.query_validator = QueryParameterValidator()
        self.quality_validator = DataQualityValidator()

    def sanitize_query_params(
        self, params: Dict[str, Any], allowed_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Sanitize and validate query parameters

        Args:
            params: Raw query parameters
            allowed_fields: List of allowed field names

        Returns:
            Sanitized query parameters
        """
        if not isinstance(params, dict):
            raise AnalyticsValidationError("Query parameters must be a dictionary")

        # Validate overall structure
        sanitized = self.security_validator.validate_dict_input(params)

        # Sanitize each parameter
        result = {}
        for key, value in sanitized.items():
            # Sanitize key
            clean_key = self.security_validator.sanitize_string(str(key), 100)

            # Skip if field not in allowed list
            if allowed_fields and clean_key not in allowed_fields:
                continue

            # Sanitize value based on type
            if isinstance(value, str):
                result[clean_key] = self.security_validator.sanitize_string(value)
            elif isinstance(value, (int, float)):
                result[clean_key] = value
            elif isinstance(value, list):
                result[clean_key] = self.security_validator.validate_list_input(value)
            elif isinstance(value, dict):
                result[clean_key] = self.security_validator.validate_dict_input(value)
            elif isinstance(value, datetime):
                result[clean_key] = value
            else:
                # Skip unknown types
                continue

        return result

    def create_cache_key(self, params: Dict[str, Any]) -> str:
        """
        Create a secure cache key from query parameters

        Args:
            params: Sanitized query parameters

        Returns:
            Cache key hash
        """
        # Sort parameters for consistent key generation
        sorted_params = json.dumps(params, sort_keys=True, default=str)
        return hashlib.md5(sorted_params.encode()).hexdigest()


# Global sanitizer instance
analytics_sanitizer = AnalyticsInputSanitizer()
