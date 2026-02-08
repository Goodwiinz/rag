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
        # Setup mock db session
        mock_db_session = MagicMock()
        mock_db_session.__enter__.return_value = mock_db_session

        # Use side_effect to return a fresh iterator each time (though called once)
        mock_get_db.side_effect = lambda: iter([mock_db_session])

        # Mock result
        mock_row = MagicMock()
        mock_row.total_documents = 10
        mock_row.avg_file_size = 1024.0
        mock_row.unique_types = 2
        mock_row.unique_uploaders = 3

        mock_result = MagicMock()
        mock_result.first.return_value = mock_row
        mock_db_session.execute.return_value = mock_result

        # Call method
        days = 30
        organization_id = "org-123"
        result = self.service.get_search_analytics(organization_id=organization_id, days=days)

        # Verify get_db called
        self.assertTrue(mock_get_db.called, "get_db was not called")

        # Verify db.execute called
        # We check mock_db_session.execute
        if not mock_db_session.execute.called:
            print(f"DEBUG: get_db calls: {mock_get_db.mock_calls}")
            print(f"DEBUG: session calls: {mock_db_session.mock_calls}")

        self.assertTrue(mock_db_session.execute.called, f"db.execute not called. Session calls: {mock_db_session.mock_calls}")

        # Get arguments passed to execute
        args, kwargs = mock_db_session.execute.call_args

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

        # Verify query contains :cutoff_date
        query_str = str(query_arg)
        self.assertIn(":cutoff_date", query_str)
        self.assertNotIn("INTERVAL ':days days'", query_str)

        # Verify result structure
        self.assertEqual(result["total_documents"], 10)
        self.assertEqual(result["avg_file_size_bytes"], 1024.0)

if __name__ == "__main__":
    unittest.main()
