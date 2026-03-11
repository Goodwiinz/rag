"""
Encrypted field models for sensitive data storage.

This module provides SQLAlchemy field types that automatically encrypt
and decrypt sensitive data using the core encryption utilities.
"""

import json
import logging
from typing import Any, Optional, Type, Union

from sqlalchemy import TEXT, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import Mutable, MutableDict

from ..core.encryption import (
    EncryptionError,
    decrypt_sensitive_field,
    encrypt_sensitive_field,
    get_field_encryption,
)

logger = logging.getLogger(__name__)


class EncryptedType(TypeDecorator):
    """Base class for encrypted field types"""

    impl = TEXT

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        """Encrypt value before storing in database"""
        if value is None:
            return None

        try:
            # For column-level encryption, we need the field name
            # This will be handled by the column definition
            return encrypt_sensitive_field(
                value, getattr(self, "_field_name", "unknown")
            )
        except EncryptionError as e:
            logger.error(f"Failed to encrypt field: {str(e)}")
            raise

    def process_result_value(self, value: Optional[str], dialect) -> Any:
        """Decrypt value after retrieving from database"""
        if value is None:
            return None

        try:
            return decrypt_sensitive_field(
                value, getattr(self, "_field_name", "unknown")
            )
        except (EncryptionError, Exception) as e:
            # Enhanced fallback: catch any exception during decryption
            # This handles both key errors and malformed (legacy plaintext) data
            logger.warning(f"Decryption failed for field {getattr(self, '_field_name', 'unknown')} (returning raw value): {str(e)}")
            return value

    def copy(self, **kwargs):
        """Create a copy of the type with field name"""
        new_type = self.__class__()
        new_type._field_name = kwargs.get(
            "field_name", getattr(self, "_field_name", "unknown")
        )
        return new_type


class EncryptedString(EncryptedType):
    """Encrypted string field type"""

    pass


class EncryptedText(EncryptedType):
    """Encrypted text field type for longer content"""

    impl = TEXT


class EncryptedJSON(EncryptedType):
    """Encrypted JSON field type"""

    impl = TEXT

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        """Convert JSON to string and encrypt"""
        if value is None:
            return None

        # Convert to JSON string if not already string
        if not isinstance(value, str):
            value = json.dumps(value)

        return super().process_bind_param(value, dialect)

    def process_result_value(self, value: Optional[str], dialect) -> Any:
        """Decrypt and parse JSON"""
        decrypted_value = super().process_result_value(value, dialect)

        if decrypted_value is None:
            return None

        try:
            return json.loads(decrypted_value)
        except (json.JSONDecodeError, TypeError):
            # Return as string if JSON parsing fails
            return decrypted_value


class EncryptedEmail(EncryptedString):
    """Encrypted email field type with validation"""

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        """Validate and encrypt email"""
        if value is None:
            return None

        # Basic email validation
        if isinstance(value, str) and "@" not in value:
            raise ValueError("Invalid email format")

        return super().process_bind_param(value, dialect)


class EncryptedPhone(EncryptedString):
    """Encrypted phone number field type with validation"""

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        """Validate and encrypt phone number"""
        if value is None:
            return None

        # Basic phone validation - remove common formatting
        if isinstance(value, str):
            # Remove spaces, dashes, parentheses
            clean_phone = "".join(c for c in value if c.isdigit())
            if len(clean_phone) < 10:
                raise ValueError("Phone number must have at least 10 digits")
            value = clean_phone

        return super().process_bind_param(value, dialect)


class EncryptedSSN(EncryptedString):
    """Encrypted Social Security Number field type with strict validation"""

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        """Validate and encrypt SSN"""
        if value is None:
            return None

        if isinstance(value, str):
            # Remove dashes and spaces
            clean_ssn = "".join(c for c in value if c.isdigit())
            if len(clean_ssn) != 9:
                raise ValueError("SSN must be exactly 9 digits")
            value = clean_ssn

        return super().process_bind_param(value, dialect)


class EncryptedCreditCard(EncryptedString):
    """Encrypted credit card number field type with validation"""

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        """Validate and encrypt credit card number"""
        if value is None:
            return None

        if isinstance(value, str):
            # Remove spaces and dashes
            clean_card = "".join(c for c in value if c.isdigit())
            if len(clean_card) < 13 or len(clean_card) > 19:
                raise ValueError("Credit card number must be 13-19 digits")

            # Luhn algorithm validation
            if not self._validate_luhn(clean_card):
                raise ValueError("Invalid credit card number")
            value = clean_card

        return super().process_bind_param(value, dialect)

    def _validate_luhn(self, card_number: str) -> bool:
        """Validate credit card number using Luhn algorithm"""
        total = 0
        reverse_digits = card_number[::-1]

        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n = (n // 10) + (n % 10)
            total += n

        return total % 10 == 0


class EncryptedAddress(EncryptedJSON):
    """Encrypted address field type"""

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        """Validate and encrypt address"""
        if value is None:
            return None

        # Ensure address has required fields
        if isinstance(value, dict):
            required_fields = ["street", "city", "country"]
            for field in required_fields:
                if field not in value:
                    raise ValueError(f"Address missing required field: {field}")

        return super().process_bind_param(value, dialect)


# Mutable types for SQLAlchemy
class EncryptedMutableDict(MutableDict):
    """Mutable dictionary for encrypted JSON fields"""

    @classmethod
    def coerce(cls, key, value):
        """Coerce value to EncryptedMutableDict"""
        if value is None:
            return None

        if isinstance(value, dict):
            return cls(value)

        return super().coerce(key, value)


# Register mutable types
EncryptedJSON = EncryptedMutableDict.as_mutable(EncryptedJSON)


# Factory function for creating encrypted columns with field names
def encrypted_column(column_type: Type[EncryptedType], field_name: str, **kwargs):
    """
    Create an encrypted column with field name for context

    Args:
        column_type: Encrypted field type class
        field_name: Name of the field for encryption context
        **kwargs: Additional column arguments

    Returns:
        SQLAlchemy column with encryption
    """
    from sqlalchemy import Column

    # Create instance and set field name
    encrypted_type = column_type()
    encrypted_type._field_name = field_name

    return Column(encrypted_type, **kwargs)


# Convenience functions for common encrypted fields
def encrypted_string(field_name: str, **kwargs):
    """Create encrypted string column"""
    return encrypted_column(EncryptedString, field_name, **kwargs)


def encrypted_text(field_name: str, **kwargs):
    """Create encrypted text column"""
    return encrypted_column(EncryptedText, field_name, **kwargs)


def encrypted_email(field_name: str, **kwargs):
    """Create encrypted email column"""
    return encrypted_column(EncryptedEmail, field_name, **kwargs)


def encrypted_phone(field_name: str, **kwargs):
    """Create encrypted phone column"""
    return encrypted_column(EncryptedPhone, field_name, **kwargs)


def encrypted_ssn(field_name: str, **kwargs):
    """Create encrypted SSN column"""
    return encrypted_column(EncryptedSSN, field_name, **kwargs)


def encrypted_credit_card(field_name: str, **kwargs):
    """Create encrypted credit card column"""
    return encrypted_column(EncryptedCreditCard, field_name, **kwargs)


def encrypted_address(field_name: str, **kwargs):
    """Create encrypted address column"""
    return encrypted_column(EncryptedAddress, field_name, **kwargs)


def encrypted_json(field_name: str, **kwargs):
    """Create encrypted JSON column"""
    return encrypted_column(EncryptedJSON, field_name, **kwargs)
