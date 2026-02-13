
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import text
from src.services.search.fulltext_search_service import FullTextSearchService
from src.models.document import ProcessingStatus

class TestFullTextSearchAnalytics:

    @pytest.fixture
    def service(self):
        return FullTextSearchService()

    @pytest.fixture
    def mock_db_session(self):
        session = MagicMock()
        # Mock context manager behavior
        session.__enter__.return_value = session
        session.__exit__.return_value = None
        return session

    def test_get_search_analytics_query_construction(self, service, mock_db_session):
        """Test that get_search_analytics constructs a valid query with bind parameters"""

        # Mock get_db to return our mock session
        with patch('src.services.search.fulltext_search_service.get_db') as mock_get_db:
            mock_get_db.return_value = iter([mock_db_session])

            # Call the method
            days = 30
            service.get_search_analytics(days=days)

            # Verify execute was called
            assert mock_db_session.execute.called

            # Get the args passed to execute
            call_args = mock_db_session.execute.call_args
            sql_clause = call_args[0][0]
            params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]

            sql_str = str(sql_clause)

            # Check for the fix (we expect this to fail initially if we were running against real DB,
            # but here we are checking the constructed SQL string)

            # In the buggy version, it uses INTERVAL ':days days'
            # In the fixed version, it should use :cutoff_date

            print(f"Generated SQL: {sql_str}")
            print(f"Params: {params}")

            # Verify the fix
            assert ":cutoff_date" in sql_str
            assert "cutoff_date" in params
            assert "':days days'" not in sql_str
