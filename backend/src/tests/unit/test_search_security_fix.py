
import sys
import os
from unittest.mock import MagicMock

# Set environment to use SQLite
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ASYNC_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Mock dependencies to avoid installing everything
sys.modules['cryptography'] = MagicMock()
sys.modules['cryptography.fernet'] = MagicMock()
sys.modules['cryptography.hazmat'] = MagicMock()
sys.modules['cryptography.hazmat.backends'] = MagicMock()
sys.modules['cryptography.hazmat.primitives'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.hashes'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.hmac'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.padding'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.serialization'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.asymmetric'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.asymmetric.padding'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.asymmetric.rsa'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.ciphers'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.ciphers.algorithms'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.ciphers.modes'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.ciphers.aead'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.kdf'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.kdf.hkdf'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.kdf.pbkdf2'] = MagicMock()

sys.modules['spacy'] = MagicMock()
sys.modules['asyncpg'] = MagicMock()

mock_aiosqlite = MagicMock()
mock_aiosqlite.sqlite_version_info = (3, 40, 0)
sys.modules['aiosqlite'] = mock_aiosqlite

sys.modules['psycopg2'] = MagicMock()
sys.modules['redis'] = MagicMock()
sys.modules['openai'] = MagicMock()
sys.modules['tiktoken'] = MagicMock()
sys.modules['tenacity'] = MagicMock()
sys.modules['defusedxml'] = MagicMock()
sys.modules['kagglehub'] = MagicMock()
sys.modules['bleach'] = MagicMock()
sys.modules['pypdf'] = MagicMock()
sys.modules['email_validator'] = MagicMock()
sys.modules['structlog'] = MagicMock()
sys.modules['bcrypt'] = MagicMock()
sys.modules['jose'] = MagicMock()
sys.modules['httpx'] = MagicMock()

import pytest
from unittest.mock import patch
from datetime import datetime, timedelta
from sqlalchemy import text
from src.services.search.fulltext_search_service import FullTextSearchService, ProcessingStatus

class TestSearchSecurityFix:
    @patch('src.services.search.fulltext_search_service.get_db_sync')
    def test_get_search_analytics_parameterized_query(self, mock_get_db_sync):
        # Setup mock DB session
        mock_db = MagicMock()
        mock_db.__enter__.return_value = mock_db

        # Mock generator behavior for get_db_sync()
        mock_generator = MagicMock()
        mock_generator.__next__.return_value = mock_db
        mock_get_db_sync.return_value = mock_generator

        # Setup mock result
        mock_result = MagicMock()
        mock_result.first.return_value = MagicMock(
            total_documents=10,
            avg_file_size=1024,
            unique_types=2,
            unique_uploaders=3
        )
        mock_db.execute.return_value = mock_result

        # Initialize service
        service = FullTextSearchService()

        # Call the method
        days = 30
        analytics = service.get_search_analytics(organization_id="org-123", days=days)

        # Verify the query execution
        assert mock_db.execute.called
        args, kwargs = mock_db.execute.call_args

        # Verify SQL query structure (no INTERVAL string injection)
        sql_query = str(args[0])
        assert "INTERVAL ':days days'" not in sql_query
        assert "created_at >= :cutoff_date" in sql_query

        # Verify parameters binding
        params = args[1]
        assert "cutoff_date" in params
        assert isinstance(params["cutoff_date"], datetime)
        # Check that cutoff_date is approximately correct (within 5 seconds)
        expected_date = datetime.utcnow() - timedelta(days=days)
        assert abs((params["cutoff_date"] - expected_date).total_seconds()) < 5.0
        assert params["organization_id"] == "org-123"
