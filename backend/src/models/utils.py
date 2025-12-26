"""
Database utility types and functions
"""

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ARRAY as PostgreSQLARRAY
from sqlalchemy.types import TypeDecorator, TEXT
import json

class StringArray(TypeDecorator):
    """Custom Array type that works with both SQLite and PostgreSQL"""

    impl = TEXT

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgreSQLARRAY(String))
        else:
            return dialect.type_descriptor(TEXT())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        # Convert list to JSON string for SQLite
        if dialect.name != 'postgresql':
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        # Convert JSON string back to list for SQLite
        if dialect.name != 'postgresql':
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                return []
        return value