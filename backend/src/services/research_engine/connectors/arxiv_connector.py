"""ArXiv source connector."""

import asyncio
import logging
from typing import Any, List

import httpx
from defusedxml import ElementTree as ET

from src.services.research_engine.connectors.base import SourceConnector, SourceDocument

ATOM_NS = "http://www.w3.org/2005/Atom"

logger = logging.getLogger(__name__)

# arXiv asks for one request every three seconds from a single connection,
# across every machine you control. The ingestion service enforces that with a
# Redis slot reservation shared by all pods; this connector used to skip it
# entirely and hit the API directly from Celery, which is the one path that can
# get the whole platform rate-limited on behalf of everything else.
_MAX_ATTEMPTS = 2
_REQUEST_TIMEOUT_S = 30.0


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

        from src.services.arxiv.arxiv_service import (
            _acquire_arxiv_rate_slot,
            _retry_after_seconds,
        )

        response = None
        for attempt in range(_MAX_ATTEMPTS):
            # Reserve a slot on the shared cross-pod gate before every attempt,
            # including retries — a retry that skips the gate is exactly the
            # burst the gate exists to prevent.
            slot_wait = await _acquire_arxiv_rate_slot()
            if slot_wait:
                await asyncio.sleep(slot_wait)

            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_S) as client:
                # https, not http: the plain-HTTP endpoint redirects and sends
                # the query in clear text on the way.
                response = await client.get(
                    "https://export.arxiv.org/api/query",
                    params=params,
                    follow_redirects=True,
                )

            if response.status_code == 429 and attempt < _MAX_ATTEMPTS - 1:
                wait = _retry_after_seconds(response.headers, default=3.0)
                logger.warning(
                    "arXiv rate limited (429) in research connector; "
                    "retrying in %ss",
                    wait,
                )
                await asyncio.sleep(wait)
                continue

            response.raise_for_status()
            break

        if response is None:  # pragma: no cover - loop always assigns
            return []

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
