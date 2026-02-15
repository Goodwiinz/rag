import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.getcwd())

# Import the service
# We rely on installed packages for dependencies
from src.services.search.fulltext_search_service import FullTextSearchService


class TestSecurityIssue(unittest.TestCase):
    def test_get_search_analytics_sql_injection_pattern(self):
        service = FullTextSearchService()

        # Mock DB session
        mock_db = MagicMock()
        mock_result = MagicMock()
        # Mock row result
        mock_row = MagicMock()
        mock_row.total_documents = 100
        mock_row.avg_file_size = 1024
        mock_row.unique_types = 5
        mock_row.unique_uploaders = 2

        mock_result.first.return_value = mock_row
        mock_db.execute.return_value = mock_result

        # Mock get_db to return our mock_db
        # We need to patch where it is imported in the service module
        with patch(
            "src.services.search.fulltext_search_service.get_db",
            return_value=iter([mock_db]),
        ):
            service.get_search_analytics(days=30)

            # Check the arguments passed to db.execute
            call_args = mock_db.execute.call_args
            if call_args:
                sql_obj = call_args[0][0]  # The first arg is the text() object
                # text() object string representation contains the SQL
                sql_str = str(sql_obj)
                print(f"\nGenerated SQL:\n{sql_str}")

                # Assert that the problematic pattern DOES NOT exist
                self.assertNotIn(
                    "INTERVAL ':days days'",
                    sql_str,
                    "Vulnerability still present: INTERVAL ':days days'",
                )
                # Assert that the fix pattern exists
                self.assertIn(
                    ":cutoff_date",
                    sql_str,
                    "Fix verification: :cutoff_date parameter missing",
                )


if __name__ == "__main__":
    unittest.main()
