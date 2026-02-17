from unittest.mock import MagicMock, patch

import httpx

from src.services.search.cohere_rerank_service import CohereRerankService


@patch("src.services.search.cohere_rerank_service.httpx.Client")
def test_rerank_sync_sets_404_failure_reason_and_falls_back(
    mock_http_client: MagicMock,
) -> None:
    service = CohereRerankService()
    service._enabled = True
    service.endpoint = "https://example.invalid/rerank"
    service.api_key = "test-key"
    service.model = "rerank-v3.5"

    request = httpx.Request("POST", service.endpoint)
    response = httpx.Response(404, request=request, text='{"error":"not found"}')
    http_error = httpx.HTTPStatusError(
        "Not Found", request=request, response=response
    )
    response_mock = MagicMock()
    response_mock.raise_for_status.side_effect = http_error
    response_mock.status_code = 404
    response_mock.text = '{"error":"not found"}'

    client_cm = MagicMock()
    client_cm.__enter__.return_value.post.return_value = response_mock
    mock_http_client.return_value = client_cm

    results = service.rerank_sync(
        query="test query",
        documents=[{"id": "doc-1", "content": "content", "relevance_score": 0.8}],
        top_n=1,
    )

    assert len(results) == 1
    assert service.last_failure["reason"] == "endpoint_not_found"
    assert service.last_failure["status_code"] == 404

