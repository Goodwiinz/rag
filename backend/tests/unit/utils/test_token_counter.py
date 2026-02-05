"""
Unit tests for token counting utilities
"""

import pytest
from unittest.mock import patch, MagicMock
import sys

from src.utils.token_counter import (
    count_tokens,
    estimate_tokens,
    count_message_tokens,
    CHARS_PER_TOKEN_ESTIMATE
)


class TestCountTokens:
    """Test count_tokens function"""

    def test_empty_text_returns_zero(self):
        """Test that empty text returns 0 tokens"""
        assert count_tokens("") == 0
        assert count_tokens(None) == 0

    def test_fallback_to_estimation_when_tiktoken_unavailable(self):
        """Test fallback to estimation when tiktoken is not available"""
        # Force ImportError by setting sys.modules entry to None
        with patch.dict("sys.modules", {"tiktoken": None}):
            text = "Hello world"
            result = count_tokens(text)
            expected = estimate_tokens(text)
            assert result == expected

    def test_uses_tiktoken_when_available(self):
        """Test that tiktoken is used when available"""
        mock_tiktoken = MagicMock()
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens
        mock_tiktoken.get_encoding.return_value = mock_encoding

        # Patch sys.modules so 'import tiktoken' returns our mock
        with patch.dict("sys.modules", {"tiktoken": mock_tiktoken}):
            result = count_tokens("Hello world")

            assert result == 5
            mock_tiktoken.get_encoding.assert_called_once_with("cl100k_base")
            mock_encoding.encode.assert_called_once_with("Hello world")

    def test_model_specific_encoding(self):
        """Test that model-specific encodings are selected correctly"""
        mock_tiktoken = MagicMock()
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = [1, 2, 3]
        mock_tiktoken.get_encoding.return_value = mock_encoding

        with patch.dict("sys.modules", {"tiktoken": mock_tiktoken}):
            # Test GPT-4 model
            count_tokens("test", model="gpt-4")
            mock_tiktoken.get_encoding.assert_called_with("cl100k_base")

            # Test GPT-3.5 model
            count_tokens("test", model="gpt-3.5-turbo")
            mock_tiktoken.get_encoding.assert_called_with("cl100k_base")

            # Test older model
            count_tokens("test", model="text-davinci-003")
            mock_tiktoken.get_encoding.assert_called_with("p50k_base")

    def test_handles_tiktoken_encoding_errors(self):
        """Test fallback when tiktoken encoding fails"""
        mock_tiktoken = MagicMock()
        mock_tiktoken.get_encoding.side_effect = Exception("Encoding failed")

        with patch.dict("sys.modules", {"tiktoken": mock_tiktoken}):
            text = "Hello world"
            result = count_tokens(text)
            expected = estimate_tokens(text)
            assert result == expected


class TestEstimateTokens:
    """Test estimate_tokens function"""

    def test_empty_text_returns_zero(self):
        """Test that empty text returns 0 tokens"""
        assert estimate_tokens("") == 0
        assert estimate_tokens(None) == 0

    def test_single_word(self):
        """Test estimation for a single word"""
        word = "hello"
        expected = max(1, int(len(word) / CHARS_PER_TOKEN_ESTIMATE))
        assert estimate_tokens(word) == expected

    def test_multiple_words(self):
        """Test estimation for multiple words"""
        text = "Hello world, how are you today?"
        normalized = " ".join(text.split())  # Normalize whitespace
        expected = max(1, int(len(normalized) / CHARS_PER_TOKEN_ESTIMATE))
        assert estimate_tokens(text) == expected

    def test_excessive_whitespace_normalized(self):
        """Test that excessive whitespace is normalized"""
        text = "Hello    world    with    lots    of    spaces"
        normalized_text = "Hello world with lots of spaces"
        expected = max(1, int(len(normalized_text) / CHARS_PER_TOKEN_ESTIMATE))
        assert estimate_tokens(text) == expected

    def test_minimum_one_token(self):
        """Test that result is at least 1 token for non-empty text"""
        # Very short text should still be 1 token
        result = estimate_tokens("a")
        assert result >= 1

    def test_long_text(self):
        """Test estimation for longer text"""
        text = "This is a much longer piece of text that should result in multiple tokens. " * 10
        normalized = " ".join(text.split())
        expected = max(1, int(len(normalized) / CHARS_PER_TOKEN_ESTIMATE))
        assert estimate_tokens(text) == expected


class TestCountMessageTokens:
    """Test count_message_tokens function"""

    def test_includes_role_overhead(self):
        """Test that message token count includes role overhead"""
        content = "Hello world"
        content_tokens = estimate_tokens(content)
        expected = content_tokens + 4  # 4 token overhead
        
        result = count_message_tokens(content, estimate_only=True)
        assert result == expected

    def test_different_roles(self):
        """Test that different roles work but overhead is same"""
        content = "Hello world"
        
        user_tokens = count_message_tokens(content, role="user", estimate_only=True)
        assistant_tokens = count_message_tokens(content, role="assistant", estimate_only=True)
        system_tokens = count_message_tokens(content, role="system", estimate_only=True)
        
        # All should have same overhead regardless of role
        assert user_tokens == assistant_tokens == system_tokens

    @patch('src.utils.token_counter.count_tokens')
    def test_uses_accurate_counting_when_not_estimate_only(self, mock_count_tokens):
        """Test that accurate counting is used when estimate_only=False"""
        mock_count_tokens.return_value = 10
        
        result = count_message_tokens("test content", estimate_only=False)
        
        mock_count_tokens.assert_called_once_with("test content")
        assert result == 14  # 10 content + 4 overhead

    def test_estimate_only_mode(self):
        """Test that estimate_only mode uses estimation"""
        content = "This is test content"
        result = count_message_tokens(content, estimate_only=True)
        
        expected_content = estimate_tokens(content)
        expected_total = expected_content + 4
        assert result == expected_total

    def test_empty_content(self):
        """Test message tokens with empty content"""
        result = count_message_tokens("", estimate_only=True)
        assert result == 4  # Just the overhead


class TestTokenCounterConstants:
    """Test token counter constants and assumptions"""

    def test_chars_per_token_reasonable(self):
        """Test that CHARS_PER_TOKEN_ESTIMATE is reasonable"""
        assert 2.0 <= CHARS_PER_TOKEN_ESTIMATE <= 5.0
        assert CHARS_PER_TOKEN_ESTIMATE == 3.5

    def test_estimation_consistency(self):
        """Test that estimation is consistent"""
        text = "The quick brown fox jumps over the lazy dog"
        result1 = estimate_tokens(text)
        result2 = estimate_tokens(text)
        assert result1 == result2

    def test_estimation_scales_with_length(self):
        """Test that estimation scales appropriately with text length"""
        short_text = "Hello"
        long_text = short_text * 10
        
        short_tokens = estimate_tokens(short_text)
        long_tokens = estimate_tokens(long_text)
        
        # Long text should have significantly more tokens
        assert long_tokens > short_tokens * 5
