"""
Unit tests for models utilities
"""

import json
import pytest
from unittest.mock import MagicMock

from sqlalchemy import String, TEXT
from sqlalchemy.dialects.postgresql import ARRAY as PostgreSQLARRAY

from src.models.utils import StringArray


class TestStringArray:
    """Test StringArray custom type"""

    def test_postgresql_dialect_uses_array_type(self):
        """Test that PostgreSQL dialect uses ARRAY type"""
        string_array = StringArray()
        
        # Mock PostgreSQL dialect
        mock_dialect = MagicMock()
        mock_dialect.name = "postgresql"
        mock_dialect.type_descriptor.return_value = "mocked_postgresql_array"
        
        result = string_array.load_dialect_impl(mock_dialect)
        
        # Should call type_descriptor with PostgreSQL ARRAY
        mock_dialect.type_descriptor.assert_called_once()
        assert result == "mocked_postgresql_array"

    def test_non_postgresql_dialect_uses_text_type(self):
        """Test that non-PostgreSQL dialects use TEXT type"""
        string_array = StringArray()
        
        # Mock SQLite dialect
        mock_dialect = MagicMock()
        mock_dialect.name = "sqlite"
        mock_dialect.type_descriptor.return_value = "mocked_text_type"
        
        result = string_array.load_dialect_impl(mock_dialect)
        
        # Should call type_descriptor with TEXT
        mock_dialect.type_descriptor.assert_called_once()
        assert result == "mocked_text_type"

    def test_process_bind_param_postgresql_passthrough(self):
        """Test that PostgreSQL passes values through unchanged"""
        string_array = StringArray()
        
        # Mock PostgreSQL dialect
        mock_dialect = MagicMock()
        mock_dialect.name = "postgresql"
        
        test_value = ["item1", "item2", "item3"]
        result = string_array.process_bind_param(test_value, mock_dialect)
        
        assert result == test_value

    def test_process_bind_param_postgresql_handles_none(self):
        """Test that PostgreSQL handles None values"""
        string_array = StringArray()
        
        mock_dialect = MagicMock()
        mock_dialect.name = "postgresql"
        
        result = string_array.process_bind_param(None, mock_dialect)
        assert result is None

    def test_process_bind_param_sqlite_converts_to_json(self):
        """Test that SQLite converts list to JSON string"""
        string_array = StringArray()
        
        # Mock SQLite dialect
        mock_dialect = MagicMock()
        mock_dialect.name = "sqlite"
        
        test_value = ["item1", "item2", "item3"]
        result = string_array.process_bind_param(test_value, mock_dialect)
        
        expected = json.dumps(test_value)
        assert result == expected

    def test_process_bind_param_sqlite_handles_none(self):
        """Test that SQLite handles None values"""
        string_array = StringArray()
        
        mock_dialect = MagicMock()
        mock_dialect.name = "sqlite"
        
        result = string_array.process_bind_param(None, mock_dialect)
        assert result is None

    def test_process_result_value_postgresql_passthrough(self):
        """Test that PostgreSQL passes result values through unchanged"""
        string_array = StringArray()
        
        mock_dialect = MagicMock()
        mock_dialect.name = "postgresql"
        
        test_value = ["result1", "result2", "result3"]
        result = string_array.process_result_value(test_value, mock_dialect)
        
        assert result == test_value

    def test_process_result_value_postgresql_handles_none(self):
        """Test that PostgreSQL handles None results"""
        string_array = StringArray()
        
        mock_dialect = MagicMock()
        mock_dialect.name = "postgresql"
        
        result = string_array.process_result_value(None, mock_dialect)
        assert result is None

    def test_process_result_value_sqlite_converts_from_json(self):
        """Test that SQLite converts JSON string back to list"""
        string_array = StringArray()
        
        mock_dialect = MagicMock()
        mock_dialect.name = "sqlite"
        
        test_list = ["item1", "item2", "item3"]
        json_string = json.dumps(test_list)
        
        result = string_array.process_result_value(json_string, mock_dialect)
        
        assert result == test_list

    def test_process_result_value_sqlite_handles_none(self):
        """Test that SQLite handles None results"""
        string_array = StringArray()
        
        mock_dialect = MagicMock()
        mock_dialect.name = "sqlite"
        
        result = string_array.process_result_value(None, mock_dialect)
        assert result is None

    def test_process_result_value_sqlite_handles_invalid_json(self):
        """Test that SQLite handles invalid JSON by returning empty list"""
        string_array = StringArray()
        
        mock_dialect = MagicMock()
        mock_dialect.name = "sqlite"
        
        # Test invalid JSON
        result = string_array.process_result_value("invalid json", mock_dialect)
        assert result == []

    def test_process_result_value_sqlite_handles_non_string(self):
        """Test that SQLite handles non-string values gracefully"""
        string_array = StringArray()
        
        mock_dialect = MagicMock()
        mock_dialect.name = "sqlite"
        
        # Test non-string value (should trigger TypeError in json.loads)
        result = string_array.process_result_value(123, mock_dialect)
        assert result == []

    def test_round_trip_postgresql(self):
        """Test round-trip conversion for PostgreSQL"""
        string_array = StringArray()
        
        mock_dialect = MagicMock()
        mock_dialect.name = "postgresql"
        
        original_value = ["test1", "test2", "test3"]
        
        # Bind (write to DB)
        bound_value = string_array.process_bind_param(original_value, mock_dialect)
        # Result (read from DB)
        result_value = string_array.process_result_value(bound_value, mock_dialect)
        
        assert result_value == original_value

    def test_round_trip_sqlite(self):
        """Test round-trip conversion for SQLite"""
        string_array = StringArray()
        
        mock_dialect = MagicMock()
        mock_dialect.name = "sqlite"
        
        original_value = ["test1", "test2", "test3"]
        
        # Bind (write to DB)
        bound_value = string_array.process_bind_param(original_value, mock_dialect)
        # Result (read from DB)
        result_value = string_array.process_result_value(bound_value, mock_dialect)
        
        assert result_value == original_value

    def test_empty_list_handling(self):
        """Test handling of empty lists"""
        string_array = StringArray()
        
        mock_sqlite_dialect = MagicMock()
        mock_sqlite_dialect.name = "sqlite"
        
        mock_postgresql_dialect = MagicMock()
        mock_postgresql_dialect.name = "postgresql"
        
        empty_list = []
        
        # Test SQLite
        sqlite_bound = string_array.process_bind_param(empty_list, mock_sqlite_dialect)
        sqlite_result = string_array.process_result_value(sqlite_bound, mock_sqlite_dialect)
        assert sqlite_result == empty_list
        
        # Test PostgreSQL
        pg_bound = string_array.process_bind_param(empty_list, mock_postgresql_dialect)
        pg_result = string_array.process_result_value(pg_bound, mock_postgresql_dialect)
        assert pg_result == empty_list

    def test_unicode_string_handling(self):
        """Test handling of unicode strings in arrays"""
        string_array = StringArray()
        
        mock_dialect = MagicMock()
        mock_dialect.name = "sqlite"
        
        unicode_list = ["hello", "世界", "🌍", "test"]
        
        # Should handle unicode correctly through JSON
        bound_value = string_array.process_bind_param(unicode_list, mock_dialect)
        result_value = string_array.process_result_value(bound_value, mock_dialect)
        
        assert result_value == unicode_list

    def test_different_dialect_names(self):
        """Test various dialect names"""
        string_array = StringArray()
        
        dialects_to_test = [
            ("postgresql", True),   # Should use ARRAY
            ("postgres", False),    # Should use TEXT (not exact match)
            ("sqlite", False),      # Should use TEXT
            ("mysql", False),       # Should use TEXT
            ("oracle", False),      # Should use TEXT
        ]
        
        test_value = ["test"]
        
        for dialect_name, should_be_postgresql in dialects_to_test:
            mock_dialect = MagicMock()
            mock_dialect.name = dialect_name
            
            bound_value = string_array.process_bind_param(test_value, mock_dialect)
            
            if should_be_postgresql:
                # PostgreSQL should pass through
                assert bound_value == test_value
            else:
                # Others should convert to JSON
                assert bound_value == json.dumps(test_value)