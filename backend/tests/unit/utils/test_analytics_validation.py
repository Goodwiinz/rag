"""
Unit tests for analytics validation utilities
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.utils.analytics_validation import (
    SecurityValidator,
    QueryParameterValidator,
    AnalyticsValidationError,
    MAX_STRING_LENGTH,
    MAX_LIST_ITEMS
)


class TestSecurityValidator:
    """Test SecurityValidator class methods"""

    def test_sanitize_string_basic(self):
        """Test basic string sanitization"""
        validator = SecurityValidator()
        
        # Normal string should be unchanged
        result = validator.sanitize_string("Hello World")
        assert result == "Hello World"

    def test_sanitize_string_trim_whitespace(self):
        """Test that whitespace is trimmed"""
        validator = SecurityValidator()
        
        result = validator.sanitize_string("  Hello World  ")
        assert result == "Hello World"

    def test_sanitize_string_normalize_whitespace(self):
        """Test whitespace normalization"""
        validator = SecurityValidator()
        
        result = validator.sanitize_string("Hello    World\t\nTest")
        assert result == "Hello World Test"

    def test_sanitize_string_max_length(self):
        """Test max length enforcement"""
        validator = SecurityValidator()
        
        long_string = "x" * 100
        result = validator.sanitize_string(long_string, max_length=50)
        assert len(result) == 50
        assert result == "x" * 50

    def test_sanitize_string_global_max_length(self):
        """Test global max length limit"""
        validator = SecurityValidator()
        
        too_long_string = "x" * (MAX_STRING_LENGTH + 100)
        
        with pytest.raises(AnalyticsValidationError) as exc_info:
            validator.sanitize_string(too_long_string)
        
        assert "String too long" in str(exc_info.value)

    def test_sanitize_string_sql_injection_protection(self):
        """Test SQL injection pattern removal"""
        validator = SecurityValidator()
        
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "UNION SELECT * FROM passwords",
            "/*comment*/ DELETE FROM data"
        ]
        
        for malicious_input in malicious_inputs:
            result = validator.sanitize_string(malicious_input)
            
            # Should not contain dangerous SQL keywords
            assert "DROP" not in result.upper()
            assert "DELETE" not in result.upper()
            assert "UNION" not in result.upper()

        # Check proper SQL injection pattern with closing quote
        # The regex expects matched quotes: ' OR '1'='1'
        malicious_input = "test' OR '1'='1'"
        result = validator.sanitize_string(malicious_input)
        assert result != malicious_input
        assert "'1'='1'" not in result

    def test_sanitize_string_xss_protection(self):
        """Test XSS pattern removal"""
        validator = SecurityValidator()
        
        xss_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img onload='alert()' src='x'>",
            "<iframe src='malicious.html'></iframe>"
        ]
        
        for xss_input in xss_inputs:
            result = validator.sanitize_string(xss_input)
            
            # Should not contain script tags or javascript
            assert "<script" not in result.lower()
            assert "javascript:" not in result.lower()
            assert "onload" not in result.lower()
            assert "<iframe" not in result.lower()

    def test_sanitize_string_control_characters_removed(self):
        """Test control character removal"""
        validator = SecurityValidator()
        
        # String with control characters
        input_with_controls = "Hello\x00World\x08Test\x1F"
        result = validator.sanitize_string(input_with_controls)
        
        # Control characters should be removed
        assert result == "HelloWorldTest"

    def test_sanitize_string_non_string_input(self):
        """Test that non-string input raises error"""
        validator = SecurityValidator()
        
        with pytest.raises(AnalyticsValidationError) as exc_info:
            validator.sanitize_string(123)
        
        assert "Expected string" in str(exc_info.value)

    def test_sanitize_string_with_bleach(self):
        """Test sanitization when bleach is available"""
        # We assume bleach is installed (we'll fix requirements) or mocking works if we do it right
        # Since 'bleach' might not be imported in module scope if missing, we patch sys.modules

        mock_bleach = MagicMock()
        mock_bleach.clean.return_value = "cleaned_string"

        with patch.dict('sys.modules', {'bleach': mock_bleach}):
            # Need to reload or ensure HAS_BLEACH is True.
            # But wait, HAS_BLEACH is determined at import time.
            # So patching sys.modules AFTER import won't change HAS_BLEACH.
            # We can patch HAS_BLEACH directly on the module instance if we import it.

            from src.utils import analytics_validation

            with patch.object(analytics_validation, 'HAS_BLEACH', True):
                with patch.object(analytics_validation, 'bleach', mock_bleach, create=True):
                    validator = SecurityValidator()
                    result = validator.sanitize_string("test input")

                    mock_bleach.clean.assert_called_once()
                    assert result == "cleaned_string"

    def test_validate_identifier_valid_uuid(self):
        """Test valid UUID identifier"""
        validator = SecurityValidator()
        
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = validator.validate_identifier(valid_uuid)
        
        assert result == valid_uuid

    def test_validate_identifier_uppercase_uuid(self):
        """Test uppercase UUID identifier"""
        validator = SecurityValidator()
        
        uuid_upper = "550E8400-E29B-41D4-A716-446655440000"
        result = validator.validate_identifier(uuid_upper)
        
        assert result == uuid_upper

    def test_validate_identifier_invalid_format(self):
        """Test invalid identifier format"""
        validator = SecurityValidator()
        
        invalid_ids = [
            "not-a-uuid",
            "550e8400-e29b-41d4-a716",  # Too short
            "550e8400-e29b-41d4-a716-446655440000-extra",  # Too long
            "550g8400-e29b-41d4-a716-446655440000",  # Invalid character
            ""
        ]
        
        for invalid_id in invalid_ids:
            with pytest.raises(AnalyticsValidationError) as exc_info:
                validator.validate_identifier(invalid_id)
            
            assert "must be a valid UUID" in str(exc_info.value)

    def test_validate_identifier_non_string(self):
        """Test non-string identifier"""
        validator = SecurityValidator()
        
        with pytest.raises(AnalyticsValidationError) as exc_info:
            validator.validate_identifier(123)
        
        assert "must be a string" in str(exc_info.value)

    def test_validate_identifier_custom_field_name(self):
        """Test custom field name in error messages"""
        validator = SecurityValidator()
        
        with pytest.raises(AnalyticsValidationError) as exc_info:
            validator.validate_identifier("invalid", field_name="user_id")
        
        assert "user_id must be a valid UUID" in str(exc_info.value)

    def test_validate_identifier_whitespace_trimmed(self):
        """Test that whitespace is trimmed"""
        validator = SecurityValidator()
        
        uuid_with_space = "  550e8400-e29b-41d4-a716-446655440000  "
        result = validator.validate_identifier(uuid_with_space)
        
        assert result == "550e8400-e29b-41d4-a716-446655440000"

    def test_validate_search_query_basic(self):
        """Test basic search query validation"""
        validator = SecurityValidator()
        
        normal_query = "search for documents"
        result = validator.validate_search_query(normal_query)
        
        assert result == normal_query

    def test_validate_search_query_sanitization(self):
        """Test search query sanitization"""
        validator = SecurityValidator()
        
        malicious_query = "search'; DROP TABLE docs; --"
        result = validator.validate_search_query(malicious_query)
        
        # Should be sanitized but still usable
        assert "search" in result.lower()
        assert "drop" not in result.lower()

    def test_validate_numeric_range_valid(self):
        """Test valid numeric range validation"""
        validator = SecurityValidator()
        
        result = validator.validate_numeric_range(5.5, min_val=0, max_val=10)
        assert result == 5.5

    def test_validate_numeric_range_below_minimum(self):
        """Test numeric value below minimum"""
        validator = SecurityValidator()
        
        with pytest.raises(AnalyticsValidationError) as exc_info:
            validator.validate_numeric_range(-1, min_val=0, max_val=10)
        
        # Actual error: "value must be >= 0"
        assert "must be >=" in str(exc_info.value)

    def test_validate_numeric_range_above_maximum(self):
        """Test numeric value above maximum"""
        validator = SecurityValidator()
        
        with pytest.raises(AnalyticsValidationError) as exc_info:
            validator.validate_numeric_range(15, min_val=0, max_val=10)
        
        # Actual error: "value must be <= 10"
        assert "must be <=" in str(exc_info.value)

    def test_validate_numeric_range_non_numeric(self):
        """Test non-numeric value validation"""
        validator = SecurityValidator()
        
        with pytest.raises(AnalyticsValidationError) as exc_info:
            validator.validate_numeric_range("not_a_number", min_val=0, max_val=10)
        
        assert "must be numeric" in str(exc_info.value)

    def test_validate_datetime_range_valid(self):
        """Test valid datetime range"""
        validator = SecurityValidator()
        
        now = datetime.now()
        start_time = now - timedelta(hours=1)
        
        result_start, result_end = validator.validate_datetime_range(start_time, now)
        
        assert result_start == start_time
        assert result_end == now

    def test_validate_datetime_range_start_after_end(self):
        """Test start time after end time"""
        validator = SecurityValidator()
        
        now = datetime.now()
        future_time = now + timedelta(hours=1)
        
        with pytest.raises(AnalyticsValidationError) as exc_info:
            validator.validate_datetime_range(future_time, now)
        
        # Actual error: "start_date must be before end_date"
        assert "start_date must be before end_date" in str(exc_info.value)

    def test_validate_list_input_valid(self):
        """Test valid list input"""
        validator = SecurityValidator()
        
        test_list = ["item1", "item2", "item3"]
        result = validator.validate_list_input(test_list, max_items=10)
        
        assert result == test_list

    def test_validate_list_input_too_long(self):
        """Test list that's too long"""
        validator = SecurityValidator()
        
        long_list = ["item"] * (MAX_LIST_ITEMS + 1)
        
        with pytest.raises(AnalyticsValidationError) as exc_info:
            validator.validate_list_input(long_list)

        assert "cannot contain more than" in str(exc_info.value)

    def test_validate_list_input_wrong_type(self):
        """Test input is not a list"""
        validator = SecurityValidator()

        with pytest.raises(AnalyticsValidationError) as exc_info:
            validator.validate_list_input("not a list")

        assert "must be a list" in str(exc_info.value)

    def test_validate_dict_input_valid(self):
        """Test valid dictionary input"""
        validator = SecurityValidator()
        
        test_dict = {"key1": "value1", "key2": "value2"}
        result = validator.validate_dict_input(test_dict)
        
        assert result == test_dict

    def test_validate_dict_input_non_dict(self):
        """Test non-dictionary input"""
        validator = SecurityValidator()
        
        with pytest.raises(AnalyticsValidationError) as exc_info:
            validator.validate_dict_input("not_a_dict")
        
        assert "must be a dictionary" in str(exc_info.value)

    def test_validate_pagination_valid(self):
        """Test valid pagination parameters"""
        validator = QueryParameterValidator()
        
        limit, offset = validator.validate_pagination(20, 40)
        
        assert limit == 20
        assert offset == 40

    def test_validate_pagination_invalid_limit(self):
        """Test invalid pagination limit"""
        validator = QueryParameterValidator()
        
        with pytest.raises(AnalyticsValidationError) as exc_info:
            validator.validate_pagination(0, 10)  # limit must be > 0
        
        # limit < min_val (1) -> "limit must be >= 1"
        assert "must be >=" in str(exc_info.value)

    def test_validate_pagination_invalid_offset(self):
        """Test invalid pagination offset"""
        validator = QueryParameterValidator()
        
        with pytest.raises(AnalyticsValidationError) as exc_info:
            validator.validate_pagination(10, -1)  # offset must be >= 0
        
        # offset < min_val (0) -> "offset must be >= 0"
        assert "must be >=" in str(exc_info.value)


class TestAnalyticsValidationError:
    """Test custom exception class"""

    def test_exception_message(self):
        """Test exception with custom message"""
        message = "Custom validation error"
        
        with pytest.raises(AnalyticsValidationError) as exc_info:
            raise AnalyticsValidationError(message)
        
        assert str(exc_info.value) == message

    def test_exception_inheritance(self):
        """Test that it's properly inherited from Exception"""
        error = AnalyticsValidationError("test")
        assert isinstance(error, Exception)


class TestConstants:
    """Test module constants"""

    def test_max_string_length_reasonable(self):
        """Test that MAX_STRING_LENGTH is reasonable"""
        assert MAX_STRING_LENGTH > 1000
        assert MAX_STRING_LENGTH < 100000

    def test_max_list_items_reasonable(self):
        """Test that MAX_LIST_ITEMS is reasonable"""
        assert MAX_LIST_ITEMS >= 100
        assert MAX_LIST_ITEMS <= 10000