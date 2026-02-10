"""
Cache key management utilities for RAG Analytics
Provides standardized cache key generation and management
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union


@dataclass
class CacheKeyComponents:
    """Components for building cache keys"""

    service: str  # Service name (e.g., 'quality_metrics', 'user_behavior')
    organization_id: str  # Organization identifier
    entity_type: str  # Entity type (e.g., 'document', 'user', 'session')
    entity_id: Optional[str] = None  # Specific entity ID
    filters: Optional[Dict[str, Any]] = None  # Query filters
    time_range: Optional[tuple] = None  # Time range tuple (start, end)
    parameters: Optional[Dict[str, Any]] = None  # Additional parameters


class CacheKeyBuilder:
    """Builder for creating standardized cache keys"""

    # Cache key prefixes
    ANALYTICS_PREFIX = "analytics"
    QUALITY_METRICS_PREFIX = "quality"
    USER_BEHAVIOR_PREFIX = "behavior"
    PERFORMANCE_PREFIX = "perf"
    EVENTS_PREFIX = "events"
    REPORTS_PREFIX = "reports"
    JOBS_PREFIX = "jobs"
    RECOMMENDATIONS_PREFIX = "recommendations"
    DASHBOARD_PREFIX = "dashboard"

    # Separator for key components
    SEPARATOR = ":"

    @staticmethod
    def _hash_component(component: Any) -> str:
        """Create a consistent hash for a cache key component"""
        if isinstance(component, (dict, list)):
            component_str = json.dumps(component, sort_keys=True, default=str)
        else:
            component_str = str(component)

        # Use MD5 for non-security cache key generation (usedforsecurity=False)
        return hashlib.md5(component_str.encode(), usedforsecurity=False).hexdigest()

    @staticmethod
    def _normalize_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize filters for consistent cache keys"""
        if not filters:
            return {}

        # Sort keys and normalize values
        normalized = {}
        for key in sorted(filters.keys()):
            value = filters[key]

            # Handle special cases
            if isinstance(value, (list, tuple)):
                normalized[key] = sorted(value)
            elif isinstance(value, datetime):
                normalized[key] = value.isoformat()
            elif isinstance(value, (dict, set)):
                normalized[key] = json.dumps(value, sort_keys=True, default=str)
            else:
                normalized[key] = value

        return normalized

    @staticmethod
    def _normalize_time_range(time_range: Optional[tuple]) -> Optional[tuple]:
        """Normalize time range for consistent cache keys"""
        if not time_range:
            return None

        start, end = time_range

        # Convert to ISO format if datetime objects
        if isinstance(start, datetime):
            start = start.isoformat()
        if isinstance(end, datetime):
            end = end.isoformat()

        return (start, end)

    @classmethod
    def build_key(
        cls,
        prefix: str,
        service: str,
        organization_id: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        time_range: Optional[tuple] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build a complete cache key"""

        # Normalize components
        normalized_filters = cls._normalize_filters(filters) if filters else {}
        normalized_time_range = cls._normalize_time_range(time_range)
        normalized_params = cls._normalize_filters(parameters) if parameters else {}

        # Create hash components for complex data
        filters_hash = (
            cls._hash_component(normalized_filters)
            if normalized_filters
            else "nofilters"
        )
        time_hash = (
            cls._hash_component(normalized_time_range)
            if normalized_time_range
            else "notime"
        )
        params_hash = (
            cls._hash_component(normalized_params) if normalized_params else "noparams"
        )

        # Build key components
        components = [prefix, service, entity_type, organization_id]

        if entity_id:
            components.append(entity_id)

        # Add hash components
        components.extend([filters_hash, time_hash, params_hash])

        return cls.SEPARATOR.join(components)

    @classmethod
    def build_quality_metrics_key(
        cls,
        organization_id: str,
        document_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        time_range: Optional[tuple] = None,
    ) -> str:
        """Build cache key for quality metrics"""
        return cls.build_key(
            prefix=cls.ANALYTICS_PREFIX,
            service=cls.QUALITY_METRICS_PREFIX,
            organization_id=organization_id,
            entity_type="document",
            entity_id=document_id,
            filters=filters,
            time_range=time_range,
        )

    @classmethod
    def build_user_behavior_key(
        cls,
        organization_id: str,
        user_id: Optional[str] = None,
        entity_type: str = "session",
        filters: Optional[Dict[str, Any]] = None,
        time_range: Optional[tuple] = None,
    ) -> str:
        """Build cache key for user behavior analytics"""
        return cls.build_key(
            prefix=cls.ANALYTICS_PREFIX,
            service=cls.USER_BEHAVIOR_PREFIX,
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=user_id,
            filters=filters,
            time_range=time_range,
        )

    @classmethod
    def build_performance_metrics_key(
        cls,
        organization_id: str,
        component: Optional[str] = None,
        entity_type: str = "system",
        filters: Optional[Dict[str, Any]] = None,
        time_range: Optional[tuple] = None,
    ) -> str:
        """Build cache key for performance metrics"""
        return cls.build_key(
            prefix=cls.ANALYTICS_PREFIX,
            service=cls.PERFORMANCE_PREFIX,
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=component,
            filters=filters,
            time_range=time_range,
        )

    @classmethod
    def build_events_key(
        cls,
        organization_id: str,
        event_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        time_range: Optional[tuple] = None,
    ) -> str:
        """Build cache key for analytics events"""
        return cls.build_key(
            prefix=cls.ANALYTICS_PREFIX,
            service=cls.EVENTS_PREFIX,
            organization_id=organization_id,
            entity_type="event",
            entity_id=event_type,
            filters=filters,
            time_range=time_range,
        )

    @classmethod
    def build_dashboard_key(
        cls,
        organization_id: str,
        dashboard_type: str,
        filters: Optional[Dict[str, Any]] = None,
        time_range: Optional[tuple] = None,
    ) -> str:
        """Build cache key for dashboard data"""
        return cls.build_key(
            prefix=cls.ANALYTICS_PREFIX,
            service=cls.DASHBOARD_PREFIX,
            organization_id=organization_id,
            entity_type=dashboard_type,
            filters=filters,
            time_range=time_range,
        )

    @classmethod
    def build_recommendations_key(
        cls,
        organization_id: str,
        recommendation_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build cache key for recommendations"""
        return cls.build_key(
            prefix=cls.ANALYTICS_PREFIX,
            service=cls.RECOMMENDATIONS_PREFIX,
            organization_id=organization_id,
            entity_type="recommendation",
            entity_id=recommendation_type,
            filters=filters,
        )

    @classmethod
    def build_job_key(
        cls,
        organization_id: str,
        job_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build cache key for background jobs"""
        return cls.build_key(
            prefix=cls.ANALYTICS_PREFIX,
            service=cls.JOBS_PREFIX,
            organization_id=organization_id,
            entity_type="job",
            entity_id=job_type,
            filters=filters,
        )

    @classmethod
    def build_report_key(
        cls,
        organization_id: str,
        report_type: str,
        filters: Optional[Dict[str, Any]] = None,
        time_range: Optional[tuple] = None,
    ) -> str:
        """Build cache key for reports"""
        return cls.build_key(
            prefix=cls.ANALYTICS_PREFIX,
            service=cls.REPORTS_PREFIX,
            organization_id=organization_id,
            entity_type=report_type,
            filters=filters,
            time_range=time_range,
        )


class CacheKeyPattern:
    """Patterns for cache key invalidation"""

    @staticmethod
    def organization_pattern(organization_id: str) -> str:
        """Pattern for all keys belonging to an organization"""
        return f"*:{CacheKeyBuilder.SEPARATOR}{organization_id}{CacheKeyBuilder.SEPARATOR}*"

    @staticmethod
    def service_pattern(service: str) -> str:
        """Pattern for all keys belonging to a service"""
        return f"*{CacheKeyBuilder.SEPARATOR}{service}{CacheKeyBuilder.SEPARATOR}*"

    @staticmethod
    def entity_type_pattern(entity_type: str) -> str:
        """Pattern for all keys of a specific entity type"""
        return f"*{CacheKeyBuilder.SEPARATOR}{entity_type}{CacheKeyBuilder.SEPARATOR}*"

    @staticmethod
    def quality_metrics_pattern(organization_id: Optional[str] = None) -> str:
        """Pattern for quality metrics keys"""
        if organization_id:
            return f"*{CacheKeyBuilder.SEPARATOR}{CacheKeyBuilder.QUALITY_METRICS_PREFIX}{CacheKeyBuilder.SEPARATOR}*{CacheKeyBuilder.SEPARATOR}{organization_id}{CacheKeyBuilder.SEPARATOR}*"
        return f"*{CacheKeyBuilder.SEPARATOR}{CacheKeyBuilder.QUALITY_METRICS_PREFIX}{CacheKeyBuilder.SEPARATOR}*"

    @staticmethod
    def user_behavior_pattern(organization_id: Optional[str] = None) -> str:
        """Pattern for user behavior keys"""
        if organization_id:
            return f"*{CacheKeyBuilder.SEPARATOR}{CacheKeyBuilder.USER_BEHAVIOR_PREFIX}{CacheKeyBuilder.SEPARATOR}*{CacheKeyBuilder.SEPARATOR}{organization_id}{CacheKeyBuilder.SEPARATOR}*"
        return f"*{CacheKeyBuilder.SEPARATOR}{CacheKeyBuilder.USER_BEHAVIOR_PREFIX}{CacheKeyBuilder.SEPARATOR}*"

    @staticmethod
    def performance_pattern(organization_id: Optional[str] = None) -> str:
        """Pattern for performance metrics keys"""
        if organization_id:
            return f"*{CacheKeyBuilder.SEPARATOR}{CacheKeyBuilder.PERFORMANCE_PREFIX}{CacheKeyBuilder.SEPARATOR}*{CacheKeyBuilder.SEPARATOR}{organization_id}{CacheKeyBuilder.SEPARATOR}*"
        return f"*{CacheKeyBuilder.SEPARATOR}{CacheKeyBuilder.PERFORMANCE_PREFIX}{CacheKeyBuilder.SEPARATOR}*"

    @staticmethod
    def dashboard_pattern(organization_id: Optional[str] = None) -> str:
        """Pattern for dashboard keys"""
        if organization_id:
            return f"*{CacheKeyBuilder.SEPARATOR}{CacheKeyBuilder.DASHBOARD_PREFIX}{CacheKeyBuilder.SEPARATOR}*{CacheKeyBuilder.SEPARATOR}{organization_id}{CacheKeyBuilder.SEPARATOR}*"
        return f"*{CacheKeyBuilder.SEPARATOR}{CacheKeyBuilder.DASHBOARD_PREFIX}{CacheKeyBuilder.SEPARATOR}*"


class CacheKeyValidator:
    """Validator for cache keys and patterns"""

    @staticmethod
    def is_valid_key(key: str) -> bool:
        """Validate if a cache key is properly formatted"""
        if not key or not isinstance(key, str):
            return False

        # Check minimum components
        components = key.split(CacheKeyBuilder.SEPARATOR)
        if len(components) < 4:  # prefix:service:entity:org
            return False

        # Check for valid prefixes
        valid_prefixes = [CacheKeyBuilder.ANALYTICS_PREFIX]

        if components[0] not in valid_prefixes:
            return False

        return True

    @staticmethod
    def is_analytics_key(key: str) -> bool:
        """Check if key is an analytics cache key"""
        return key.startswith(
            f"{CacheKeyBuilder.ANALYTICS_PREFIX}{CacheKeyBuilder.SEPARATOR}"
        )

    @staticmethod
    def extract_organization_id(key: str) -> Optional[str]:
        """Extract organization ID from cache key"""
        if not CacheKeyValidator.is_valid_key(key):
            return None

        components = key.split(CacheKeyBuilder.SEPARATOR)

        # Organization ID is typically the 4th component
        if len(components) >= 4:
            return components[3]

        return None

    @staticmethod
    def extract_service(key: str) -> Optional[str]:
        """Extract service from cache key"""
        if not CacheKeyValidator.is_valid_key(key):
            return None

        components = key.split(CacheKeyBuilder.SEPARATOR)

        # Service is the 2nd component
        if len(components) >= 2:
            return components[1]

        return None

    @staticmethod
    def extract_entity_type(key: str) -> Optional[str]:
        """Extract entity type from cache key"""
        if not CacheKeyValidator.is_valid_key(key):
            return None

        components = key.split(CacheKeyBuilder.SEPARATOR)

        # Entity type is the 3rd component
        if len(components) >= 3:
            return components[2]

        return None

    @staticmethod
    def group_keys_by_organization(keys: List[str]) -> Dict[str, List[str]]:
        """Group cache keys by organization ID"""
        grouped = {}

        for key in keys:
            if not CacheKeyValidator.is_valid_key(key):
                continue

            org_id = CacheKeyValidator.extract_organization_id(key)
            if org_id:
                if org_id not in grouped:
                    grouped[org_id] = []
                grouped[org_id].append(key)

        return grouped

    @staticmethod
    def group_keys_by_service(keys: List[str]) -> Dict[str, List[str]]:
        """Group cache keys by service"""
        grouped = {}

        for key in keys:
            if not CacheKeyValidator.is_valid_key(key):
                continue

            service = CacheKeyValidator.extract_service(key)
            if service:
                if service not in grouped:
                    grouped[service] = []
                grouped[service].append(key)

        return grouped


# Convenience functions for common cache operations
def build_cache_key(cache_type: str, **kwargs) -> str:
    """Convenience function to build cache keys"""

    builders = {
        "quality_metrics": CacheKeyBuilder.build_quality_metrics_key,
        "user_behavior": CacheKeyBuilder.build_user_behavior_key,
        "performance_metrics": CacheKeyBuilder.build_performance_metrics_key,
        "events": CacheKeyBuilder.build_events_key,
        "dashboard": CacheKeyBuilder.build_dashboard_key,
        "recommendations": CacheKeyBuilder.build_recommendations_key,
        "jobs": CacheKeyBuilder.build_job_key,
        "reports": CacheKeyBuilder.build_report_key,
    }

    builder = builders.get(cache_type)
    if not builder:
        raise ValueError(f"Unknown cache type: {cache_type}")

    return builder(**kwargs)


def build_cache_pattern(pattern_type: str, **kwargs) -> str:
    """Convenience function to build cache patterns"""

    patterns = {
        "organization": CacheKeyPattern.organization_pattern,
        "quality_metrics": CacheKeyPattern.quality_metrics_pattern,
        "user_behavior": CacheKeyPattern.user_behavior_pattern,
        "performance": CacheKeyPattern.performance_pattern,
        "dashboard": CacheKeyPattern.dashboard_pattern,
    }

    pattern_builder = patterns.get(pattern_type)
    if not pattern_builder:
        raise ValueError(f"Unknown pattern type: {pattern_type}")

    return pattern_builder(**kwargs)
