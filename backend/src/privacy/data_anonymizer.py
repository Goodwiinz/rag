"""
Data anonymization utilities for analytics privacy compliance
Provides GDPR-compliant data anonymization for user analytics
"""

import hashlib
import logging
import re
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class DataAnonymizer:
    """
    Data anonymization utilities for analytics privacy compliance
    """

    # Hash salt for consistent anonymization (should be stored securely)
    HASH_SALT = "analytics_anonymization_salt_v1"

    @staticmethod
    def hash_value(value: str, preserve_length: bool = True) -> str:
        """
        Hash a value consistently for anonymization

        Args:
            value: Value to hash
            preserve_length: Whether to preserve the original length

        Returns:
            Hashed value
        """
        if not value:
            return value

        # Use HMAC with salt for consistent hashing
        hash_input = f"{DataAnonymizer.HASH_SALT}{value}"
        hashed = hashlib.sha256(hash_input.encode()).hexdigest()

        if preserve_length:
            # Truncate or pad to original length
            return (
                hashed[: len(value)]
                if len(hashed) >= len(value)
                else hashed.ljust(len(value), "0")
            )

        return hashed

    @staticmethod
    def anonymize_email(email: str) -> str:
        """
        Anonymize email address while preserving format

        Examples:
        john.doe@example.com -> j***.e***@e*****.com
        """
        if not email or "@" not in email:
            return email

        local, domain = email.split("@", 1)

        # Anonymize local part
        if len(local) <= 2:
            anonymized_local = "*" * len(local)
        else:
            anonymized_local = (
                local[0] + "*" * (len(local) - 2) + local[-1]
                if len(local) > 3
                else local[0] + "*"
            )

        # Anonymize domain (preserve top-level domain)
        if "." in domain:
            domain_parts = domain.rsplit(".", 1)
            main_domain = domain_parts[0]
            tld = domain_parts[1]

            if len(main_domain) <= 2:
                anonymized_domain = "*" * len(main_domain)
            else:
                anonymized_domain = (
                    main_domain[0] + "*" * (len(main_domain) - 2) + main_domain[-1]
                    if len(main_domain) > 3
                    else main_domain[0] + "*"
                )

            anonymized_email = f"{anonymized_local}@{anonymized_domain}.{tld}"
        else:
            anonymized_email = f"{anonymized_local}@{'*' * len(domain)}"

        return anonymized_email

    @staticmethod
    def anonymize_ip_address(ip: str) -> str:
        """
        Anonymize IP address by removing the last octet (IPv4) or last 64 bits (IPv6)

        Examples:
        192.168.1.100 -> 192.168.1.0
        2001:0db8:85a3:0000:0000:8a2e:0370:7334 -> 2001:0db8:85a3:0000:0000:8a2e:0370:0000
        """
        if not ip:
            return ip

        # IPv4
        if ":" not in ip:
            parts = ip.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{parts[2]}.0"

        # IPv6
        elif ":" in ip:
            parts = ip.split(":")
            if len(parts) == 8:
                # Zero out the last two segments
                return f"{parts[0]}:{parts[1]}:{parts[2]}:{parts[3]}:{parts[4]}:{parts[5]}:{parts[6]}:0000"

        return ip

    @staticmethod
    def anonymize_user_agent(user_agent: str) -> str:
        """
        Anonymize user agent by removing identifying information
        """
        if not user_agent:
            return user_agent

        # Remove version numbers and build identifiers
        anonymized = re.sub(r"\d+\.\d+(\.\d+)?", "X.X.X", user_agent)
        anonymized = re.sub(
            r"\b[0-9a-fA-F]{8,}\b", "XXXXXXXX", anonymized
        )  # Remove long hex strings
        anonymized = re.sub(
            r"\([^)]*\)", "(XXX)", anonymized
        )  # Anonymize parenthetical info

        return anonymized

    @staticmethod
    def anonymize_session_data(session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anonymize session data for analytics
        """
        if not session_data:
            return session_data

        anonymized = session_data.copy()

        # Anonymize common sensitive fields
        sensitive_fields = [
            "ip_address",
            "user_agent",
            "email",
            "name",
            "first_name",
            "last_name",
            "phone",
            "address",
            "location",
            "coordinates",
        ]

        for field in sensitive_fields:
            if field in anonymized:
                if field == "email":
                    anonymized[field] = DataAnonymizer.anonymize_email(
                        str(anonymized[field])
                    )
                elif field == "ip_address":
                    anonymized[field] = DataAnonymizer.anonymize_ip_address(
                        str(anonymized[field])
                    )
                elif field == "user_agent":
                    anonymized[field] = DataAnonymizer.anonymize_user_agent(
                        str(anonymized[field])
                    )
                else:
                    anonymized[field] = DataAnonymizer.hash_value(
                        str(anonymized[field])
                    )

        # Anonymize nested objects
        for key, value in anonymized.items():
            if isinstance(value, dict):
                anonymized[key] = DataAnonymizer.anonymize_session_data(value)
            elif isinstance(value, list):
                anonymized[key] = [
                    DataAnonymizer.anonymize_session_data(item)
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]

        return anonymized

    @staticmethod
    def anonymize_search_query(query: str, preserve_length: bool = True) -> str:
        """
        Anonymize search query while preserving analytics value

        This removes potentially sensitive information while keeping
        semantic patterns useful for analytics.
        """
        if not query:
            return query

        # Remove potential PII patterns
        anonymized = query

        # Remove email addresses
        anonymized = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "[EMAIL]",
            anonymized,
        )

        # Remove phone numbers
        anonymized = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]", anonymized)

        # Remove social security numbers
        anonymized = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]", anonymized)

        # Remove credit card numbers (basic pattern)
        anonymized = re.sub(
            r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[CARD]", anonymized
        )

        # Replace proper nouns with generic placeholders
        # This is a simplified approach - in production, you'd use NER
        words = anonymized.split()
        anonymized_words = []

        for word in words:
            # Capitalized words might be names/places
            if word.istitle() and len(word) > 3:
                anonymized_words.append("[PROPER_NOUN]")
            else:
                anonymized_words.append(word)

        anonymized = " ".join(anonymized_words)

        # If we want to completely anonymize but preserve length
        if preserve_length and query != anonymized:
            # Use hash but preserve some characteristics
            words = anonymized.split()
            hashed_words = []
            for word in words:
                if word.startswith("[") and word.endswith("]"):
                    hashed_words.append(word)  # Keep placeholders
                else:
                    # Hash the word but preserve length and first letter
                    if len(word) <= 2:
                        hashed_words.append(word[0] + "*")
                    else:
                        hash_suffix = DataAnonymizer.hash_value(word)[1 : len(word) - 1]
                        hashed_words.append(word[0] + hash_suffix + word[-1])

            return " ".join(hashed_words)

        return anonymized

    @staticmethod
    def anonymize_user_profile(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anonymize user profile data for analytics
        """
        if not user_data:
            return user_data

        anonymized = user_data.copy()

        # Handle specific user fields
        field_mappings = {
            "email": DataAnonymizer.anonymize_email,
            "first_name": lambda x: DataAnonymizer.hash_value(str(x))[:3] + "***",
            "last_name": lambda x: "***" + DataAnonymizer.hash_value(str(x))[-3:],
            "phone": lambda x: DataAnonymizer.hash_value(str(x))[:10],
            "address": lambda x: DataAnonymizer.hash_value(str(x)),
            "ip_address": DataAnonymizer.anonymize_ip_address,
            "user_agent": DataAnonymizer.anonymize_user_agent,
        }

        for field, anonymizer_func in field_mappings.items():
            if field in anonymized:
                try:
                    anonymized[field] = anonymizer_func(anonymized[field])
                except Exception as e:
                    logger.warning(f"Failed to anonymize field {field}: {e}")
                    anonymized[field] = "[ANONYMIZED]"

        # Generate consistent anonymous user ID
        if "id" in anonymized:
            original_id = str(anonymized["id"])
            anonymized["id"] = DataAnonymizer.hash_value(original_id)
            anonymized["original_id_hash"] = DataAnonymizer.hash_value(
                original_id + "original"
            )

        return anonymized

    @staticmethod
    def create_anonymous_user_id(original_user_id: str) -> str:
        """
        Create a consistent anonymous user ID
        """
        return DataAnonymizer.hash_value(f"user_{original_user_id}")

    @staticmethod
    def should_anonymize_data(
        user_consent: bool, data_type: str, retention_policy: Dict[str, Any]
    ) -> bool:
        """
        Determine if data should be anonymized based on consent and retention policies

        Args:
            user_consent: Whether user has consented to data processing
            data_type: Type of data being processed
            retention_policy: Retention policy configuration

        Returns:
            True if data should be anonymized
        """
        # Always anonymize if no consent
        if not user_consent:
            return True

        # Check retention policy for data type
        retention_days = retention_policy.get(f"{data_type}_retention_days", 365)

        # Check if data type requires anonymization by policy
        sensitive_types = ["personal", "contact", "location", "behavioral"]

        return data_type in sensitive_types or retention_days < retention_policy.get(
            "full_data_retention_days", 365
        )

    @staticmethod
    def apply_privacy_filters(
        data: Dict[str, Any],
        user_consent: bool = True,
        retention_policy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Apply privacy filters to analytics data based on consent and retention policies
        """
        if not retention_policy:
            retention_policy = {
                "personal_retention_days": 90,
                "behavioral_retention_days": 365,
                "full_data_retention_days": 730,
            }

        filtered_data = data.copy()

        # Filter sensitive fields based on consent
        if not user_consent:
            # Remove all potentially identifying fields
            sensitive_fields = ["email", "name", "ip_address", "user_agent", "location"]
            for field in sensitive_fields:
                filtered_data.pop(field, None)

        # Apply time-based retention
        if "timestamp" in filtered_data:
            timestamp = filtered_data["timestamp"]
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            days_old = (datetime.utcnow() - timestamp).days

            # Anonymize older data according to retention policies
            if days_old > retention_policy["personal_retention_days"]:
                filtered_data = DataAnonymizer.anonymize_session_data(filtered_data)

        return filtered_data
