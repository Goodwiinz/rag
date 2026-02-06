import sys
from unittest.mock import MagicMock

# Mock spacy and other dependencies before importing service
sys.modules["spacy"] = MagicMock()
sys.modules["en_core_web_sm"] = MagicMock()
# sys.modules["bleach"] = MagicMock()  # Removed to avoid polluting other tests
sys.modules["tiktoken"] = MagicMock()
# Mock vector search service to avoid import errors if referenced
sys.modules["src.services.search.vector_search_service"] = MagicMock()

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Import after mocking
from src.services.search.fulltext_search_service import FullTextSearchService, ProcessingStatus
from sqlalchemy import text

class TestFullTextSearchService(unittest.TestCase):
    def setUp(self):
        self.service = FullTextSearchService()

    @patch("src.services.search.fulltext_search_service.get_db")
    def test_get_search_analytics_query_construction(self, mock_get_db):
        # Setup mock db
        mock_db_session = MagicMock()
        # get_db is a generator, so we mock it to yield the session
        mock_get_db.return_value = iter([mock_db_session])

        # Mock result
        mock_row = MagicMock()
        mock_row.total_documents = 10
        mock_row.avg_file_size = 1024.0
        mock_row.unique_types = 2
        mock_row.unique_uploaders = 3

        mock_result = MagicMock()
        mock_result.first.return_value = mock_row
        mock_db_session.execute.return_value = mock_result
        mock_db_session.__enter__.return_value = mock_db_session

        # Call method
        days = 30
        organization_id = "org-123"
        result = self.service.get_search_analytics(organization_id=organization_id, days=days)

        # Verify db.execute called
        self.assertTrue(mock_db_session.execute.called)

        # Get arguments passed to execute
        args, kwargs = mock_db_session.execute.call_args

        # args[0] should be the SQL string wrapped in text()
        # args[1] should be parameters dict

        query_arg = args[0]
        params_arg = args[1]

        # Verify parameters
        self.assertIn("cutoff_date", params_arg)
        self.assertNotIn("days", params_arg)

        self.assertIn("organization_id", params_arg)
        self.assertEqual(params_arg["organization_id"], organization_id)

        self.assertIn("completed_status", params_arg)
        self.assertEqual(params_arg["completed_status"], ProcessingStatus.COMPLETED.name)

        # Verify cutoff_date is approximately correct
        expected_cutoff = datetime.utcnow() - timedelta(days=days)
        actual_cutoff = params_arg["cutoff_date"]

        # Ensure actual_cutoff is a datetime
        self.assertIsInstance(actual_cutoff, datetime)

        # Allow small difference (e.g. 5 seconds)
        diff = abs((expected_cutoff - actual_cutoff).total_seconds())
        self.assertLess(diff, 5)

        # Verify query contains :cutoff_date and not INTERVAL
        # Note: query_arg is a sqlalchemy.sql.elements.TextClause, need to convert to string
        query_str = str(query_arg)
        self.assertIn(":cutoff_date", query_str)
        self.assertNotIn("INTERVAL ':days days'", query_str)

        # Verify result structure
        self.assertEqual(result["total_documents"], 10)
        self.assertEqual(result["avg_file_size_bytes"], 1024.0)

if __name__ == "__main__":
    unittest.main()
