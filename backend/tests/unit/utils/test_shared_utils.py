"""
Unit tests for shared utility functions
"""

import pytest
import hashlib
import json
from unittest.mock import patch, MagicMock

from src.shared.utils import (
    hash_string,
    generate_cache_key,
    sanitize_filename,
    format_file_size,
    get_correlation_id
)


class TestHashString:
    """Test hash_string function"""

    def test_sha256_default_algorithm(self):
        """Test that SHA256 is the default algorithm"""
        text = "hello world"
        result = hash_string(text)
        
        # Verify it's SHA256
        expected = hashlib.sha256(text.encode('utf-8')).hexdigest()
        assert result == expected
        assert len(result) == 64  # SHA256 produces 64 character hex

    def test_different_algorithms(self):
        """Test that different algorithms work"""
        text = "test string"
        
        sha1_result = hash_string(text, algorithm="sha1")
        md5_result = hash_string(text, algorithm="md5")
        sha256_result = hash_string(text, algorithm="sha256")
        
        # All should be different
        assert sha1_result != md5_result != sha256_result
        assert len(sha1_result) == 40  # SHA1 produces 40 character hex
        assert len(md5_result) == 32   # MD5 produces 32 character hex
        assert len(sha256_result) == 64  # SHA256 produces 64 character hex

    def test_consistent_hashing(self):
        """Test that hashing is consistent"""
        text = "consistent test"
        
        result1 = hash_string(text)
        result2 = hash_string(text)
        
        assert result1 == result2

    def test_different_strings_different_hashes(self):
        """Test that different strings produce different hashes"""
        text1 = "string one"
        text2 = "string two"
        
        hash1 = hash_string(text1)
        hash2 = hash_string(text2)
        
        assert hash1 != hash2

    def test_empty_string(self):
        """Test hashing empty string"""
        result = hash_string("")
        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected

    def test_unicode_strings(self):
        """Test hashing unicode strings"""
        text = "Hello 世界 🌍"
        result = hash_string(text)
        expected = hashlib.sha256(text.encode('utf-8')).hexdigest()
        assert result == expected


class TestGenerateCacheKey:
    """Test generate_cache_key function"""

    def test_prefix_only(self):
        """Test cache key with prefix only"""
        result = generate_cache_key("test")
        assert result == "test"

    def test_prefix_with_simple_args(self):
        """Test cache key with simple positional arguments"""
        result = generate_cache_key("users", "123", "profile")
        assert result == "users:123:profile"

    def test_prefix_with_kwargs(self):
        """Test cache key with keyword arguments"""
        result = generate_cache_key("search", query="hello", limit=10)
        assert "search" in result
        assert "query:hello" in result
        assert "limit:10" in result
        # Keywords should be sorted for consistency
        parts = result.split(":")
        assert parts[0] == "search"

    def test_complex_objects_hashed(self):
        """Test that complex objects are hashed"""
        complex_obj = {"nested": {"data": [1, 2, 3]}, "value": "test"}
        result = generate_cache_key("complex", complex_obj)
        
        parts = result.split(":")
        assert parts[0] == "complex"
        assert len(parts[1]) == 64  # Should be SHA256 hash

    def test_mixed_argument_types(self):
        """Test mixing simple and complex arguments"""
        result = generate_cache_key(
            "mixed",
            "simple_arg",
            42,
            True,
            complex_data={"key": "value"},
            simple_param="test"
        )
        
        assert result.startswith("mixed:")
        assert "simple_arg" in result
        assert "42" in result
        assert "True" in result

    def test_consistent_with_same_inputs(self):
        """Test that same inputs always produce same key"""
        args = ("prefix", "arg1", 123)
        kwargs = {"param1": "value1", "param2": {"nested": "data"}}
        
        result1 = generate_cache_key(*args, **kwargs)
        result2 = generate_cache_key(*args, **kwargs)
        
        assert result1 == result2

    def test_different_with_different_inputs(self):
        """Test that different inputs produce different keys"""
        result1 = generate_cache_key("test", arg="value1")
        result2 = generate_cache_key("test", arg="value2")
        
        assert result1 != result2

    def test_kwargs_order_independence(self):
        """Test that kwargs order doesn't affect the key"""
        result1 = generate_cache_key("test", a="1", b="2", c="3")
        result2 = generate_cache_key("test", c="3", a="1", b="2")
        
        assert result1 == result2

    def test_boolean_values(self):
        """Test boolean values in cache key"""
        result = generate_cache_key("test", active=True, deleted=False)
        assert "active:True" in result
        assert "deleted:False" in result


class TestSanitizeFilename:
    """Test sanitize_filename function"""

    def test_safe_filename_unchanged(self):
        """Test that safe filename is unchanged"""
        safe_name = "document_file.txt"
        assert sanitize_filename(safe_name) == safe_name

    def test_dangerous_characters_replaced(self):
        """Test that dangerous characters are replaced with underscore"""
        dangerous_chars = '<>:"/\\|?*'
        for char in dangerous_chars:
            filename = f"file{char}name.txt"
            result = sanitize_filename(filename)
            assert char not in result
            assert "_" in result

    def test_control_characters_removed(self):
        """Test that control characters are removed"""
        # Test some control characters
        filename = "file\x00\x1f\x7f\x9fname.txt"
        result = sanitize_filename(filename)
        assert result == "filename.txt"

    def test_long_filename_truncated(self):
        """Test that very long filenames are truncated"""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        
        assert len(result) <= 255
        assert result.endswith(".txt")  # Extension should be preserved

    def test_long_filename_without_extension(self):
        """Test truncation of long filename without extension"""
        long_name = "a" * 300
        result = sanitize_filename(long_name)
        
        assert len(result) <= 255
        assert result == "a" * 255

    def test_extension_preserved_in_truncation(self):
        """Test that extension is preserved when truncating"""
        long_name = "a" * 300 + ".document"
        result = sanitize_filename(long_name)
        
        assert len(result) <= 255
        assert result.endswith(".document")
        # Check that the name part was truncated
        expected_name_length = 255 - len(".document") - 1  # -1 for the dot
        assert result.startswith("a" * expected_name_length)

    def test_complex_filename_sanitization(self):
        """Test complex filename with multiple issues"""
        bad_filename = 'file<>name:with"bad|chars*.txt'
        result = sanitize_filename(bad_filename)
        
        assert result == "file__name_with_bad_chars_.txt"

    def test_empty_filename(self):
        """Test empty filename"""
        result = sanitize_filename("")
        assert result == ""

    def test_filename_only_dangerous_chars(self):
        """Test filename with only dangerous characters"""
        result = sanitize_filename('<>:"/\\|?*')
        assert result == "_" * 9  # All 9 chars replaced with underscore


class TestFormatFileSize:
    """Test format_file_size function"""

    def test_zero_bytes(self):
        """Test formatting zero bytes"""
        assert format_file_size(0) == "0 B"

    def test_bytes_under_1024(self):
        """Test formatting bytes under 1024"""
        assert format_file_size(512) == "512.0 B"
        assert format_file_size(1) == "1.0 B"
        assert format_file_size(1023) == "1023.0 B"

    def test_kilobytes(self):
        """Test formatting kilobytes"""
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1536) == "1.5 KB"
        assert format_file_size(2048) == "2.0 KB"

    def test_megabytes(self):
        """Test formatting megabytes"""
        assert format_file_size(1024 * 1024) == "1.0 MB"
        assert format_file_size(1024 * 1024 * 2.5) == "2.5 MB"

    def test_gigabytes(self):
        """Test formatting gigabytes"""
        assert format_file_size(1024 * 1024 * 1024) == "1.0 GB"
        assert format_file_size(int(1024 * 1024 * 1024 * 1.5)) == "1.5 GB"

    def test_terabytes(self):
        """Test formatting terabytes"""
        assert format_file_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"

    def test_very_large_size(self):
        """Test very large size stays at TB"""
        huge_size = 1024 * 1024 * 1024 * 1024 * 5
        result = format_file_size(huge_size)
        assert result == "5.0 TB"

    def test_decimal_precision(self):
        """Test that decimal precision is 1"""
        size = int(1024 * 1.23456)
        result = format_file_size(size)
        assert ".2 KB" in result  # Should round to 1 decimal

    def test_edge_cases(self):
        """Test edge cases around unit boundaries"""
        # Just under KB boundary
        assert format_file_size(1023) == "1023.0 B"
        # Just at KB boundary
        assert format_file_size(1024) == "1.0 KB"
        # Just under MB boundary
        assert format_file_size(1024 * 1024 - 1) == "1024.0 KB"


class TestGetCorrelationId:
    """Test get_correlation_id function"""

    def test_returns_existing_correlation_id(self):
        """Test that existing correlation ID is returned"""
        # Mock request object
        mock_request = MagicMock()
        mock_request.state.correlation_id = "existing-id-123"
        
        result = get_correlation_id(mock_request)
        assert result == "existing-id-123"

    def test_generates_new_id_when_none_exists(self):
        """Test that new ID is generated when none exists"""
        # Mock request object without correlation_id
        mock_request = MagicMock()
        del mock_request.state.correlation_id  # Make it raise AttributeError
        mock_request.state.correlation_id = None  # Reset after delete

        with patch('src.shared.utils.uuid.uuid4') as mock_uuid:
            # Use __str__ magic method mocking
            mock_uuid.return_value.__str__.return_value = "new-uuid-123"

            # When getattr fails, it should generate new UUID
            mock_request.state = MagicMock()
            del mock_request.state.correlation_id

            result = get_correlation_id(mock_request)
            mock_uuid.assert_called_once()
            assert result == "new-uuid-123"
            
    def test_handles_missing_state_attribute(self):
        """Test handling when state doesn't have correlation_id"""
        mock_request = MagicMock()
        # Create state but without correlation_id attribute
        mock_request.state = MagicMock(spec=[])
        
        with patch('src.shared.utils.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__.return_value = "fallback-uuid-456"

            result = get_correlation_id(mock_request)
            mock_uuid.assert_called_once()
            assert result == "fallback-uuid-456"

    def test_returns_string_uuid(self):
        """Test that result is always a string"""
        mock_request = MagicMock()
        mock_request.state.correlation_id = "test-id"
        
        result = get_correlation_id(mock_request)
        assert isinstance(result, str)
        assert len(result) > 0