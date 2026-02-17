"""Semantic Scholar source connector."""

from typing import Any, Dict, List, Optional

import httpx

from src.services.research_engine.connectors.base import SourceConnector, SourceDocument


class SemanticScholarConnector(SourceConnector):
    """Connector for the Semantic Scholar API."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key

    async def search(
        self, query: str, max_results: int = 50, **kwargs: Any
    ) -> List[SourceDocument]:
        """Search Semantic Scholar for papers matching the query."""
        params: Dict[str, Any] = {
            "query": query,
            "limit": max_results,
            "fields": "paperId,title,abstract,authors,url",
        }

        headers: Dict[str, str] = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params=params,
                headers=headers,
            )
            response.raise_for_status()

        data = response.json()
        documents: List[SourceDocument] = []

        for paper in data.get("data", []):
            authors = [a["name"] for a in paper.get("authors", [])]
            documents.append(
                SourceDocument(
                    connector_type="semantic_scholar",
                    external_id=paper.get("paperId"),
                    title=paper.get("title", ""),
                    authors=authors,
                    abstract=paper.get("abstract"),
                    url=paper.get("url"),
                )
            )

        return documents
