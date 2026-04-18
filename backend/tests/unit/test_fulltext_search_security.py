
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import text
from datetime import datetime
from src.services.search.fulltext_search_service import FullTextSearchService

@pytest.fixture
def mock_db_session():
    mock_session = MagicMock()
    mock_session.execute.return_value.first.return_value = MagicMock(
        total_documents=10,
        avg_file_size=1024.0,
        unique_types=2,
        unique_uploaders=3
    )
    # Ensure session works as context manager
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = None
    return mock_session

def test_get_search_analytics_valid_query(mock_db_session):
    service = FullTextSearchService()

    with patch('src.services.search.fulltext_search_service.get_db_sync') as mock_get_db:
        # Mock generator behavior: get_db_sync() returns a generator
        mock_generator = MagicMock()
        mock_generator.__next__.return_value = mock_db_session
        mock_get_db.return_value = mock_generator

        service.get_search_analytics(organization_id="org1", days=30)

        # Verify the query was executed
        assert mock_db_session.execute.called

        # Inspect the SQL passed to execute
        call_args = mock_db_session.execute.call_args
        sql_arg = call_args[0][0] # The first argument is text() object
        params = call_args[0][1] # The second argument is params dict

        sql_str = str(sql_arg)

        # Verify fix:
        # 1. INTERVAL should NOT be present
        assert "INTERVAL" not in sql_str
        # 2. cutoff_date should be a parameter
        assert ":cutoff_date" in sql_str
        # 3. cutoff_date parameter should be a datetime object
        assert isinstance(params["cutoff_date"], datetime)
        # 4. organization_id parameter should be passed
        assert params["organization_id"] == "org1"
