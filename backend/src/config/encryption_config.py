"""
Encryption configuration for the RAG system.

This module provides configuration settings for:
- Encryption algorithms and parameters
- Key management settings
- Field encryption policies
- Security requirements
"""

import os
from typing import Any, Dict, List, Optional

from pydantic import BaseSettings, Field, validator

from ..core.encryption import EncryptionAlgorithm, EncryptionKeyType


class EncryptionConfig(BaseSettings):
    """Configuration settings for encryption system"""

    # Master key configuration
    master_key_env_var: str = Field(
        default="ENCRYPTION_MASTER_KEY",
        description="Environment variable containing the master encryption key",
    )

    master_key_rotation_days: int = Field(
        default=365,
        ge=30,
        le=730,
        description="Days between master key rotations (30-730 days)",
    )

    # Data key configuration
    data_key_rotation_days: int = Field(
        default=90,
        ge=7,
        le=365,
        description="Days between data key rotations (7-365 days)",
    )

    file_key_rotation_days: int = Field(
        default=180,
        ge=30,
        le=365,
        description="Days between file key rotations (30-365 days)",
    )

    # Algorithm settings
    default_encryption_algorithm: str = Field(
        default=EncryptionAlgorithm.AES256_GCM,
        description="Default encryption algorithm",
    )

    pbkdf2_iterations: int = Field(
        default=100000,
        ge=50000,
        le=1000000,
        description="PBKDF2 iterations for key derivation",
    )

    # Field encryption settings
    auto_encrypt_request_fields: bool = Field(
        default=True, description="Automatically encrypt sensitive fields in requests"
    )

    auto_mask_response_fields: bool = Field(
        default=True, description="Automatically mask sensitive fields in responses"
    )

    # Sensitive field patterns
    sensitive_field_patterns: List[str] = Field(
        default=[
            "ssn",
            "social_security",
            "tax_id",
            "ein",
            "credit_card",
            "bank_account",
            "routing",
            "password",
            "secret",
            "token",
            "api_key",
            "private_key",
            "certificate",
            "passport",
            "driver_license",
            "birth_date",
            "email",
            "phone",
            "address",
            "first_name",
            "last_name",
            "full_name",
        ],
        description="Field patterns that trigger automatic encryption",
    )

    # File encryption settings
    max_file_size_for_encryption: int = Field(
        default=100 * 1024 * 1024,  # 100MB
        ge=1,
        description="Maximum file size for encryption in bytes",
    )

    encrypted_file_extensions: List[str] = Field(
        default=[
            ".pdf",
            ".doc",
            ".docx",
            ".txt",
            ".rtf",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".mp3",
            ".wav",
            ".flac",
            ".aac",
            ".mp4",
            ".avi",
            ".mov",
            ".wmv",
        ],
        description="File extensions that should be encrypted",
    )

    # Key management settings
    max_key_versions: int = Field(
        default=10, ge=3, le=50, description="Maximum number of key versions to retain"
    )

    key_backup_enabled: bool = Field(
        default=True, description="Enable automatic key backup"
    )

    key_backup_retention_days: int = Field(
        default=2555, ge=365, description="Days to retain key backups"  # 7 years
    )

    # Audit settings
    audit_encryption_operations: bool = Field(
        default=True, description="Audit all encryption operations"
    )

    audit_retention_days: int = Field(
        default=2555,  # 7 years
        ge=365,
        description="Days to retain encryption audit logs",
    )

    # Performance settings
    encryption_cache_enabled: bool = Field(
        default=True, description="Enable encryption operation caching"
    )

    encryption_cache_ttl: int = Field(
        default=3600,  # 1 hour
        ge=60,
        description="Cache TTL for encryption operations in seconds",
    )

    # Compliance settings
    gdpr_compliance_enabled: bool = Field(
        default=True, description="Enable GDPR compliance features"
    )

    data_retention_days: int = Field(
        default=2555,  # 7 years
        ge=365,
        description="Default data retention period in days",
    )

    # Security settings
    require_key_rotation_alerts: bool = Field(
        default=True, description="Alert when keys need rotation"
    )

    key_rotation_warning_days: int = Field(
        default=14, ge=1, le=30, description="Days before key rotation to send warning"
    )

    max_failed_decrypt_attempts: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum failed decrypt attempts before alerting",
    )

    # Integration settings
    integrate_with_rbac: bool = Field(
        default=True, description="Integrate encryption with RBAC system"
    )

    integrate_with_audit: bool = Field(
        default=True, description="Integrate encryption with audit system"
    )

    @validator("default_encryption_algorithm")
    def validate_encryption_algorithm(cls, v):
        """Validate encryption algorithm"""
        valid_algorithms = [EncryptionAlgorithm.AES256_GCM, EncryptionAlgorithm.FERNET]
        if v not in valid_algorithms:
            raise ValueError(
                f"Invalid encryption algorithm. Must be one of: {valid_algorithms}"
            )
        return v

    @validator("master_key_env_var")
    def validate_master_key_env_var(cls, v):
        """Validate master key environment variable name"""
        if not v or not v.strip():
            raise ValueError("Master key environment variable cannot be empty")
        return v.strip()

    class Config:
        env_prefix = "ENCRYPTION_"
        case_sensitive = False


class EncryptionPolicyConfig:
    """Configuration for encryption policies"""

    # Data classification policies
    data_classification_policies = {
        "public": {
            "encrypt_at_rest": False,
            "encrypt_in_transit": True,
            "field_encryption": False,
            "audit_access": False,
        },
        "internal": {
            "encrypt_at_rest": True,
            "encrypt_in_transit": True,
            "field_encryption": True,
            "audit_access": True,
        },
        "confidential": {
            "encrypt_at_rest": True,
            "encrypt_in_transit": True,
            "field_encryption": True,
            "audit_access": True,
            "strict_access_control": True,
        },
        "restricted": {
            "encrypt_at_rest": True,
            "encrypt_in_transit": True,
            "field_encryption": True,
            "audit_access": True,
            "strict_access_control": True,
            "require_approval": True,
        },
    }

    # Field-specific encryption policies
    field_encryption_policies = {
        "email": {
            "encrypt": True,
            "algorithm": EncryptionAlgorithm.AES256_GCM,
            "key_rotation_days": 90,
            "mask_in_response": True,
            "audit_access": True,
        },
        "phone": {
            "encrypt": True,
            "algorithm": EncryptionAlgorithm.AES256_GCM,
            "key_rotation_days": 90,
            "mask_in_response": True,
            "audit_access": True,
        },
        "ssn": {
            "encrypt": True,
            "algorithm": EncryptionAlgorithm.AES256_GCM,
            "key_rotation_days": 60,
            "mask_in_response": True,
            "audit_access": True,
            "strict_access": True,
        },
        "credit_card": {
            "encrypt": True,
            "algorithm": EncryptionAlgorithm.AES256_GCM,
            "key_rotation_days": 30,
            "mask_in_response": True,
            "audit_access": True,
            "strict_access": True,
            "pci_compliance": True,
        },
        "address": {
            "encrypt": True,
            "algorithm": EncryptionAlgorithm.AES256_GCM,
            "key_rotation_days": 180,
            "mask_in_response": False,
            "audit_access": True,
        },
        "notes": {
            "encrypt": True,
            "algorithm": EncryptionAlgorithm.AES256_GCM,
            "key_rotation_days": 90,
            "mask_in_response": False,
            "audit_access": True,
        },
    }

    # File encryption policies
    file_encryption_policies = {
        "document": {
            "encrypt": True,
            "algorithm": EncryptionAlgorithm.AES256_GCM,
            "key_rotation_days": 180,
            "virus_scan": True,
            "audit_access": True,
        },
        "image": {
            "encrypt": True,
            "algorithm": EncryptionAlgorithm.AES256_GCM,
            "key_rotation_days": 180,
            "scan_content": True,
            "audit_access": True,
        },
        "audio": {
            "encrypt": True,
            "algorithm": EncryptionAlgorithm.AES256_GCM,
            "key_rotation_days": 180,
            "transcript_encrypt": True,
            "audit_access": True,
        },
        "video": {
            "encrypt": True,
            "algorithm": EncryptionAlgorithm.AES256_GCM,
            "key_rotation_days": 180,
            "transcript_encrypt": True,
            "audit_access": True,
        },
    }


class EncryptionComplianceConfig:
    """Configuration for compliance requirements"""

    # GDPR requirements
    gdpr_requirements = {
        "data_minimization": True,
        "purpose_limitation": True,
        "storage_limitation": True,
        "accuracy": True,
        "security": True,
        "accountability": True,
        "data_subject_rights": True,
        "consent_management": True,
        "breach_notification": True,
        "data_protection_officer": True,
    }

    # PCI DSS requirements
    pci_dss_requirements = {
        "encrypt_cardholder_data": True,
        "strong_cryptography": True,
        "key_management": True,
        "access_control": True,
        "audit_logging": True,
        "network_security": True,
        "secure_development": True,
        "vulnerability_testing": True,
        "information_security": True,
    }

    # HIPAA requirements
    hipaa_requirements = {
        "administrative_safeguards": True,
        "physical_safeguards": True,
        "technical_safeguards": True,
        "organizational_requirements": True,
        "policies_procedures": True,
        "breach_notification": True,
    }


# Global configuration instance
encryption_config = EncryptionConfig()


def get_encryption_config() -> EncryptionConfig:
    """Get global encryption configuration"""
    return encryption_config


def get_field_encryption_policy(field_name: str) -> Optional[Dict[str, Any]]:
    """Get encryption policy for a specific field"""
    policies = EncryptionPolicyConfig.field_encryption_policies

    # Exact match
    if field_name in policies:
        return policies[field_name]

    # Pattern match
    field_lower = field_name.lower()
    for pattern, policy in policies.items():
        if pattern in field_lower:
            return policy

    return None


def get_file_encryption_policy(file_type: str) -> Optional[Dict[str, Any]]:
    """Get encryption policy for a specific file type"""
    return EncryptionPolicyConfig.file_encryption_policies.get(file_type)


def is_sensitive_field(field_name: str) -> bool:
    """Check if a field is considered sensitive"""
    field_lower = field_name.lower()
    patterns = encryption_config.sensitive_field_patterns

    return any(pattern in field_lower for pattern in patterns)


def should_encrypt_field(field_name: str, field_value: Any) -> bool:
    """Determine if a field should be encrypted"""
    # Skip None values
    if field_value is None:
        return False

    # Check if field is sensitive
    if not is_sensitive_field(field_name):
        return False

    # Check field-specific policy
    policy = get_field_encryption_policy(field_name)
    if policy:
        return policy.get("encrypt", True)

    # Default to encrypt sensitive fields
    return True


def should_mask_field(field_name: str) -> bool:
    """Determine if a field should be masked in responses"""
    policy = get_field_encryption_policy(field_name)
    if policy:
        return policy.get("mask_in_response", True)

    # Default to mask sensitive fields
    return is_sensitive_field(field_name)


def get_encryption_algorithm_for_field(field_name: str) -> str:
    """Get the encryption algorithm for a specific field"""
    policy = get_field_encryption_policy(field_name)
    if policy:
        return policy.get("algorithm", encryption_config.default_encryption_algorithm)

    return encryption_config.default_encryption_algorithm


def get_key_rotation_days_for_field(field_name: str) -> int:
    """Get key rotation interval for a specific field"""
    policy = get_field_encryption_policy(field_name)
    if policy:
        return policy.get("key_rotation_days", encryption_config.data_key_rotation_days)

    return encryption_config.data_key_rotation_days


def validate_master_key() -> bool:
    """Validate that master key is properly configured"""
    master_key_b64 = os.getenv(encryption_config.master_key_env_var)
    if not master_key_b64:
        return False

    try:
        import base64

        master_key = base64.b64decode(master_key_b64.encode())
        return len(master_key) == 32  # 256 bits
    except Exception:
        return False


def get_compliance_requirements() -> Dict[str, Dict[str, bool]]:
    """Get all compliance requirements"""
    return {
        "gdpr": EncryptionComplianceConfig.gdpr_requirements,
        "pci_dss": EncryptionComplianceConfig.pci_dss_requirements,
        "hipaa": EncryptionComplianceConfig.hipaa_requirements,
    }


def is_compliance_enabled(compliance_type: str) -> bool:
    """Check if a specific compliance type is enabled"""
    compliance_map = {
        "gdpr": encryption_config.gdpr_compliance_enabled,
        "pci_dss": True,  # Always enabled for financial data
        "hipaa": os.getenv("HIPAA_COMPLIANCE", "false").lower() == "true",
    }

    return compliance_map.get(compliance_type.lower(), False)
