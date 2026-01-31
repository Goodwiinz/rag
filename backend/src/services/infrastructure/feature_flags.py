"""
Feature Flags Service for Multimodal RAG System
Integrates with LaunchDarkly for feature flag management
"""

import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

try:
    import launchdarkly_server_sdk as ld

    LAUNCHDARKLY_AVAILABLE = True
except ImportError:
    LAUNCHDARKLY_AVAILABLE = False
    logging.warning("LaunchDarkly SDK not available. Using mock implementation.")

logger = logging.getLogger(__name__)


class FeatureFlag(Enum):
    """Feature flag enumeration"""

    MULTIMODAL_PROCESSING = "multimodal-processing"
    ADVANCED_ANALYTICS = "advanced-analytics"
    EVALUATION_METRICS = "evaluation-metrics"
    REAL_TIME_PROCESSING = "real-time-processing"
    EXPERIMENTAL_UI = "experimental-ui"
    AI_MODEL_OPTIMIZATION = "ai-model-optimization"
    FILE_UPLOAD_LIMITS = "file-upload-limits"
    SEARCH_RESULT_COUNT = "search-result-count"


@dataclass
class UserContext:
    """User context for feature flag evaluation"""

    user_id: str
    email: str
    name: Optional[str] = None
    custom_attributes: Optional[Dict[str, Any]] = None


class FeatureFlagService:
    """Service for managing feature flags"""

    def __init__(self):
        self._client = None
        self._initialized = False
        self._mock_flags = {}

        # Try to initialize LaunchDarkly client
        if LAUNCHDARKLY_AVAILABLE and os.getenv("LAUNCHDARKLY_SDK_KEY"):
            try:
                self._initialize_launchdarkly()
            except Exception as e:
                logger.error(f"Failed to initialize LaunchDarkly: {e}")
                self._load_mock_flags()
        else:
            logger.info("LaunchDarkly not configured, using mock implementation")
            self._load_mock_flags()

    def _initialize_launchdarkly(self):
        """Initialize LaunchDarkly client"""
        sdk_key = os.getenv("LAUNCHDARKLY_SDK_KEY")
        if not sdk_key:
            raise ValueError("LAUNCHDARKLY_SDK_KEY environment variable not set")

        config = ld.Config(sdk_key)
        config.offline = os.getenv("ENVIRONMENT") == "development"

        self._client = ld.LDClient(config)
        self._initialized = True
        logger.info("LaunchDarkly client initialized successfully")

    def _load_mock_flags(self):
        """Load mock flags for development/testing"""
        mock_config_path = os.path.join(
            os.path.dirname(__file__), "../../feature-flags/launchdarkly-config.json"
        )

        try:
            if os.path.exists(mock_config_path):
                with open(mock_config_path, "r") as f:
                    config = json.load(f)

                # Extract default values from configuration
                for flag_key, flag_config in config.get("flags", {}).items():
                    default_rule = flag_config.get("defaultRule", {})
                    if "variation" in default_rule:
                        variations = flag_config.get("variations", [])
                        variation_index = default_rule["variation"]
                        if variation_index < len(variations):
                            self._mock_flags[flag_key] = variations[variation_index][
                                "value"
                            ]
        except Exception as e:
            logger.error(f"Failed to load mock flags: {e}")

        # Default fallback values
        default_flags = {
            "multimodal-processing": False,
            "advanced-analytics": True,
            "evaluation-metrics": True,
            "real-time-processing": False,
            "experimental-ui": False,
            "ai-model-optimization": "standard",
            "file-upload-limits": 100,
            "search-result-count": 10,
        }

        for flag_key, default_value in default_flags.items():
            if flag_key not in self._mock_flags:
                self._mock_flags[flag_key] = default_value

    def is_enabled(
        self,
        flag: FeatureFlag,
        user_context: Optional[UserContext] = None,
        default_value: bool = False,
    ) -> bool:
        """
        Check if a feature flag is enabled

        Args:
            flag: Feature flag to check
            user_context: User context for evaluation
            default_value: Default value if flag is not found

        Returns:
            True if flag is enabled, False otherwise
        """
        flag_key = flag.value

        if self._initialized and self._client:
            try:
                ld_user = (
                    self._create_ld_user(user_context)
                    if user_context
                    else ld.User("anonymous")
                )
                result = self._client.variation(flag_key, ld_user, default_value)
                return bool(result)
            except Exception as e:
                logger.error(f"Error evaluating LaunchDarkly flag {flag_key}: {e}")
                return self._mock_flags.get(flag_key, default_value)
        else:
            return bool(self._mock_flags.get(flag_key, default_value))

    def get_variation(
        self,
        flag: FeatureFlag,
        user_context: Optional[UserContext] = None,
        default_value: Any = None,
    ) -> Any:
        """
        Get the variation value for a feature flag

        Args:
            flag: Feature flag to check
            user_context: User context for evaluation
            default_value: Default value if flag is not found

        Returns:
            The variation value
        """
        flag_key = flag.value

        if self._initialized and self._client:
            try:
                ld_user = (
                    self._create_ld_user(user_context)
                    if user_context
                    else ld.User("anonymous")
                )
                return self._client.variation(flag_key, ld_user, default_value)
            except Exception as e:
                logger.error(f"Error evaluating LaunchDarkly flag {flag_key}: {e}")
                return self._mock_flags.get(flag_key, default_value)
        else:
            return self._mock_flags.get(flag_key, default_value)

    def _create_ld_user(
        self, user_context: UserContext
    ) -> Any:  # Returns ld.User when available
        """Create LaunchDarkly user object from UserContext"""
        ld_user = ld.User(user_context.user_id)
        ld_user.email = user_context.email
        if user_context.name:
            ld_user.name = user_context.name

        if user_context.custom_attributes:
            for key, value in user_context.custom_attributes.items():
                ld_user.custom[key] = value

        return ld_user

    def get_all_flags(
        self, user_context: Optional[UserContext] = None
    ) -> Dict[str, Any]:
        """
        Get all feature flags for a user

        Args:
            user_context: User context for evaluation

        Returns:
            Dictionary of all flag values
        """
        if self._initialized and self._client:
            try:
                ld_user = (
                    self._create_ld_user(user_context)
                    if user_context
                    else ld.User("anonymous")
                )
                all_flags = self._client.all_flags_state(ld_user)
                return {
                    flag_key: flag_value.value
                    for flag_key, flag_value in all_flags.to_values_map().items()
                }
            except Exception as e:
                logger.error(f"Error getting all flags from LaunchDarkly: {e}")
                return self._mock_flags.copy()
        else:
            return self._mock_flags.copy()

    def identify_user(self, user_context: UserContext):
        """
        Identify a user for analytics and targeting

        Args:
            user_context: User context to identify
        """
        if self._initialized and self._client:
            try:
                ld_user = self._create_ld_user(user_context)
                self._client.identify(ld_user)
                logger.info(f"Identified user: {user_context.user_id}")
            except Exception as e:
                logger.error(f"Error identifying user in LaunchDarkly: {e}")

    def track_event(
        self,
        event_name: str,
        user_context: Optional[UserContext] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        """
        Track a custom event for analytics

        Args:
            event_name: Name of the event
            user_context: User context
            data: Additional event data
        """
        if self._initialized and self._client:
            try:
                ld_user = (
                    self._create_ld_user(user_context)
                    if user_context
                    else ld.User("anonymous")
                )
                self._client.track(event_name, ld_user, data or {})
                logger.debug(f"Tracked event: {event_name}")
            except Exception as e:
                logger.error(f"Error tracking event in LaunchDarkly: {e}")

    def flush(self):
        """Flush pending events"""
        if self._initialized and self._client:
            try:
                self._client.flush()
            except Exception as e:
                logger.error(f"Error flushing LaunchDarkly events: {e}")

    def close(self):
        """Close the feature flag client"""
        if self._initialized and self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.error(f"Error closing LaunchDarkly client: {e}")


# Global feature flag service instance
feature_flag_service = FeatureFlagService()


# Convenience functions
def is_multimodal_processing_enabled(
    user_context: Optional[UserContext] = None,
) -> bool:
    """Check if multimodal processing is enabled"""
    return feature_flag_service.is_enabled(
        FeatureFlag.MULTIMODAL_PROCESSING, user_context
    )


def is_advanced_analytics_enabled(user_context: Optional[UserContext] = None) -> bool:
    """Check if advanced analytics is enabled"""
    return feature_flag_service.is_enabled(FeatureFlag.ADVANCED_ANALYTICS, user_context)


def is_evaluation_metrics_enabled(user_context: Optional[UserContext] = None) -> bool:
    """Check if evaluation metrics are enabled"""
    return feature_flag_service.is_enabled(FeatureFlag.EVALUATION_METRICS, user_context)


def is_real_time_processing_enabled(user_context: Optional[UserContext] = None) -> bool:
    """Check if real-time processing is enabled"""
    return feature_flag_service.is_enabled(
        FeatureFlag.REAL_TIME_PROCESSING, user_context
    )


def get_file_upload_limit(user_context: Optional[UserContext] = None) -> int:
    """Get the file upload limit in MB"""
    return feature_flag_service.get_variation(
        FeatureFlag.FILE_UPLOAD_LIMITS, user_context, 100
    )


def get_search_result_count(user_context: Optional[UserContext] = None) -> int:
    """Get the search result count"""
    return feature_flag_service.get_variation(
        FeatureFlag.SEARCH_RESULT_COUNT, user_context, 10
    )


def get_ai_model_type(user_context: Optional[UserContext] = None) -> str:
    """Get the AI model type to use"""
    return feature_flag_service.get_variation(
        FeatureFlag.AI_MODEL_OPTIMIZATION, user_context, "standard"
    )
