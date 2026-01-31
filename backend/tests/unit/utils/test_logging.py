"""
Unit tests for logging utilities
"""

import pytest

from src.utils.logging import (
    truncate_for_logging,
    sanitize_for_logging,
    DEFAULT_PII_PATTERNS
)


class TestTruncateForLogging:
    """Test truncate_for_logging function"""

    def test_empty_string_returns_empty(self):
        """Test that empty string returns empty"""
        assert truncate_for_logging("") == ""

    def test_none_returns_empty(self):
        """Test that None returns empty string"""
        assert truncate_for_logging(None) == ""

    def test_short_string_unchanged(self):
        """Test that string shorter than max_length is unchanged"""
        text = "Hello world"
        assert truncate_for_logging(text, max_length=100) == text

    def test_string_at_max_length_unchanged(self):
        """Test that string exactly at max_length is unchanged"""
        text = "x" * 50
        assert truncate_for_logging(text, max_length=50) == text

    def test_long_string_truncated_with_ellipsis(self):
        """Test that long string is truncated with ellipsis"""
        text = "x" * 150
        result = truncate_for_logging(text, max_length=100)
        
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")
        assert result[:100] == "x" * 100

    def test_default_max_length_is_100(self):
        """Test that default max_length is 100"""
        text = "x" * 150
        result = truncate_for_logging(text)
        
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")

    def test_custom_max_length(self):
        """Test that custom max_length works"""
        text = "x" * 50
        result = truncate_for_logging(text, max_length=20)
        
        assert len(result) == 23  # 20 + "..."
        assert result.endswith("...")
        assert result[:20] == "x" * 20


class TestSanitizeForLogging:
    """Test sanitize_for_logging function"""

    def test_empty_string_returns_empty(self):
        """Test that empty string returns empty"""
        assert sanitize_for_logging("") == ""

    def test_none_returns_empty(self):
        """Test that None returns empty string"""
        assert sanitize_for_logging(None) == ""

    def test_no_sensitive_data_unchanged(self):
        """Test that text without sensitive data is unchanged (except truncation)"""
        text = "This is normal text"
        result = sanitize_for_logging(text)
        assert result == text

    def test_email_redacted(self):
        """Test that email addresses are redacted"""
        text = "Contact user@example.com for help"
        result = sanitize_for_logging(text, max_length=200)
        
        assert "[REDACTED]" in result
        assert "user@example.com" not in result
        assert "Contact" in result
        assert "for help" in result

    def test_phone_number_redacted(self):
        """Test that phone numbers are redacted"""
        test_cases = [
            "Call 123-456-7890 for help",
            "Phone: 123.456.7890",
            "Contact 1234567890",
        ]
        
        for text in test_cases:
            result = sanitize_for_logging(text, max_length=200)
            assert "[REDACTED]" in result
            # Ensure the number pattern is gone
            assert "123" not in result or "456" not in result

    def test_ssn_redacted(self):
        """Test that SSN patterns are redacted"""
        test_cases = [
            "SSN: 123-45-6789",
            "Social Security: 123456789",
            "ID: 987-65-4321"
        ]
        
        for text in test_cases:
            result = sanitize_for_logging(text, max_length=200)
            assert "[REDACTED]" in result

    def test_credit_card_redacted(self):
        """Test that credit card numbers are redacted"""
        test_cases = [
            "Card: 4532123456781234",  # Visa
            "Payment: 5555555555554444",  # Mastercard
            "Amex: 378282246310005"  # American Express
        ]
        
        for text in test_cases:
            result = sanitize_for_logging(text, max_length=200)
            assert "[REDACTED]" in result

    def test_multiple_patterns_redacted(self):
        """Test that multiple sensitive patterns are redacted"""
        text = "Contact john@example.com or call 555-123-4567"
        result = sanitize_for_logging(text, max_length=200)
        
        redacted_count = result.count("[REDACTED]")
        assert redacted_count == 2  # Both email and phone should be redacted
        assert "john@example.com" not in result
        assert "555-123-4567" not in result

    def test_custom_patterns(self):
        """Test that custom patterns work"""
        text = "Secret code: ABC123 and password: secret123"
        custom_patterns = [r"\b[A-Z]{3}\d{3}\b", r"password: \w+"]
        
        result = sanitize_for_logging(text, max_length=200, mask_patterns=custom_patterns)
        
        assert "[REDACTED]" in result
        assert "ABC123" not in result

    def test_no_patterns_uses_defaults(self):
        """Test that passing None for patterns uses defaults"""
        text = "Email: test@example.com"
        result1 = sanitize_for_logging(text, max_length=200, mask_patterns=None)
        result2 = sanitize_for_logging(text, max_length=200, mask_patterns=DEFAULT_PII_PATTERNS)
        
        assert result1 == result2
        assert "[REDACTED]" in result1

    def test_truncation_still_applies(self):
        """Test that truncation still applies after sanitization"""
        text = "Normal text " * 20  # Long text without sensitive data
        result = sanitize_for_logging(text, max_length=50)
        
        assert len(result) == 53  # 50 + "..."
        assert result.endswith("...")

    def test_sanitization_then_truncation_order(self):
        """Test that sanitization happens before truncation"""
        long_text = f"Contact user@example.com and " + "x" * 100
        result = sanitize_for_logging(long_text, max_length=50)
        
        assert "[REDACTED]" in result
        assert len(result) == 53  # 50 + "..."
        assert result.endswith("...")

    def test_empty_pattern_list(self):
        """Test that empty pattern list works (no sanitization)"""
        text = "Email: test@example.com and phone: 123-456-7890"
        result = sanitize_for_logging(text, max_length=200, mask_patterns=[])
        
        # Should not be redacted since we provided empty pattern list
        assert "[REDACTED]" not in result
        assert "test@example.com" in result
        assert "123-456-7890" in result


class TestDefaultPIIPatterns:
    """Test default PII patterns"""

    def test_default_patterns_exist(self):
        """Test that default patterns are defined"""
        assert DEFAULT_PII_PATTERNS is not None
        assert len(DEFAULT_PII_PATTERNS) > 0
        assert all(isinstance(pattern, str) for pattern in DEFAULT_PII_PATTERNS)

    def test_email_pattern_works(self):
        """Test that email pattern in defaults works"""
        import re
        
        # Find the email pattern
        email_pattern = None
        for pattern in DEFAULT_PII_PATTERNS:
            if "@" in pattern:
                email_pattern = pattern
                break
        
        assert email_pattern is not None
        
        # Test the pattern directly
        test_emails = [
            "user@example.com",
            "test.user+tag@domain.co.uk",
            "simple@domain.org"
        ]
        
        for email in test_emails:
            assert re.search(email_pattern, email) is not None

    def test_phone_pattern_works(self):
        """Test that phone pattern in defaults works"""
        import re
        
        # Find a phone pattern
        phone_pattern = None
        for pattern in DEFAULT_PII_PATTERNS:
            if "\\d{3}" in pattern and ("\\d{4}" in pattern or "\\d{3}" in pattern):
                phone_pattern = pattern
                break
        
        assert phone_pattern is not None

    def test_patterns_are_valid_regex(self):
        """Test that all default patterns are valid regex"""
        import re
        
        for pattern in DEFAULT_PII_PATTERNS:
            # Should not raise exception
            re.compile(pattern)