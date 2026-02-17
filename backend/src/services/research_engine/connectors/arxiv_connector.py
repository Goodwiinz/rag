"""ArXiv source connector."""

import xml.etree.ElementTree as ET
from typing import Any, List

import httpx

from src.services.research_engine.connectors.base import SourceConnector, SourceDocument

ATOM_NS = "http://www.w3.org/2005/Atom"


class ArxivConnector(SourceConnector):
    """Connector for the arXiv API."""

    async def search(
        self, query: str, max_results: int = 50, **kwargs: Any
    ) -> List[SourceDocument]:
        """Search arXiv for papers matching the query."""
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://export.arxiv.org/api/query",
                params=params,
            )
            response.raise_for_status()

        root = ET.fromstring(response.text)
        documents: List[SourceDocument] = []

        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            entry_id = entry.findtext(f"{{{ATOM_NS}}}id", default="")
            title = entry.findtext(f"{{{ATOM_NS}}}title", default="")
            summary = entry.findtext(f"{{{ATOM_NS}}}summary", default="")
            authors = [
                author.findtext(f"{{{ATOM_NS}}}name", default="")
                for author in entry.findall(f"{{{ATOM_NS}}}author")
            ]

            documents.append(
                SourceDocument(
                    connector_type="arxiv",
                    external_id=entry_id,
                    title=title,
                    authors=authors,
                    abstract=summary,
                    url=entry_id,
                )
            )

        return documents
