"""PubMed biomedical literature connector via NCBI E-utilities."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx
import structlog
from defusedxml import ElementTree as ET

from .base import (
    ConnectorCapability,
    ConnectorDomain,
    ConnectorInfo,
    ConnectorResult,
    ExternalDBConnector,
)

logger = structlog.get_logger(__name__)

_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_ESEARCH = f"{_BASE_URL}/esearch.fcgi"
_EFETCH = f"{_BASE_URL}/efetch.fcgi"


def _build_content(article: Dict[str, Any]) -> str:
    parts: List[str] = []
    if abstract := article.get("abstract"):
        parts.append(f"Abstract: {abstract}")
    if journal := article.get("journal"):
        parts.append(f"Journal: {journal}")
    if doi := article.get("doi"):
        parts.append(f"DOI: {doi}")
    return "\n".join(parts)


def _parse_pubmed_article(article_elem: Any) -> Optional[ConnectorResult]:
    try:
        pmid_elem = article_elem.find(".//PMID")
        pmid = pmid_elem.text if pmid_elem is not None else ""
        if not pmid:
            return None

        title_elem = article_elem.find(".//ArticleTitle")
        title = title_elem.text if title_elem is not None else f"PMID {pmid}"

        abstract_parts = [
            (e.text or "")
            for e in article_elem.findall(".//Abstract/AbstractText")
        ]
        abstract = " ".join(filter(None, abstract_parts))

        journal_elem = article_elem.find(".//Journal/Title")
        journal = journal_elem.text if journal_elem is not None else ""

        authors: List[str] = []
        for author in article_elem.findall(".//Author"):
            last = author.findtext("LastName") or ""
            initials = author.findtext("Initials") or ""
            if last:
                authors.append(f"{last} {initials}".strip())

        pub_year_elem = article_elem.find(".//PubDate/Year")
        pub_year = pub_year_elem.text if pub_year_elem is not None else None

        doi = ""
        for aid in article_elem.findall(".//ArticleId"):
            if aid.get("IdType") == "doi":
                doi = aid.text or ""
                break

        metadata = {
            "pmid": pmid,
            "abstract": abstract,
            "journal": journal,
            "doi": doi,
        }

        return ConnectorResult(
            id=pmid,
            title=title or f"PMID {pmid}",
            source="pubmed",
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            content=_build_content(metadata),
            authors=authors[:10],
            published_date=pub_year,
            metadata=metadata,
            document_type="article",
        )
    except Exception as exc:
        logger.warning("pubmed_parse_error", error=str(exc))
        return None


class PubMedConnector(ExternalDBConnector):
    """PubMed (NCBI) biomedical literature search."""

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="pubmed",
            display_name="PubMed",
            description="NCBI biomedical literature database with 35M+ citations",
            domains=[ConnectorDomain.BIOMEDICAL, ConnectorDomain.LITERATURE],
            capabilities=[ConnectorCapability.SEARCH, ConnectorCapability.FETCH],
            base_url=_BASE_URL,
            requires_api_key=False,
            api_key_env_var="NCBI_API_KEY",
            rate_limit_per_second=3.0,
            max_results_per_query=200,
        )

    def _api_key_params(self) -> Dict[str, str]:
        if key := os.environ.get("NCBI_API_KEY"):
            return {"api_key": key}
        return {}

    async def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ConnectorResult]:
        del filters  # PubMed filters supported via query syntax (e.g. "x[mh]")
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": str(min(max_results, self.info.max_results_per_query)),
            "retmode": "json",
            **self._api_key_params(),
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                search_resp = await client.get(_ESEARCH, params=params)
                search_resp.raise_for_status()
                pmids = (
                    search_resp.json()
                    .get("esearchresult", {})
                    .get("idlist", [])
                )
                if not pmids:
                    return []

                fetch_params = {
                    "db": "pubmed",
                    "id": ",".join(pmids),
                    "rettype": "abstract",
                    "retmode": "xml",
                    **self._api_key_params(),
                }
                fetch_resp = await client.get(_EFETCH, params=fetch_params)
                fetch_resp.raise_for_status()

            root = ET.fromstring(fetch_resp.text)
            results = [
                r
                for article in root.findall(".//PubmedArticle")
                if (r := _parse_pubmed_article(article)) is not None
            ]
            return results

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "pubmed_search_http_error",
                status=exc.response.status_code,
                query=query,
            )
            return []
        except Exception as exc:
            logger.error("pubmed_search_error", error=str(exc), query=query)
            return []

    async def fetch_by_id(self, record_id: str) -> Optional[ConnectorResult]:
        params = {
            "db": "pubmed",
            "id": record_id,
            "rettype": "abstract",
            "retmode": "xml",
            **self._api_key_params(),
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(_EFETCH, params=params)
                resp.raise_for_status()
            root = ET.fromstring(resp.text)
            article = root.find(".//PubmedArticle")
            if article is None:
                return None
            return _parse_pubmed_article(article)
        except Exception as exc:
            logger.error("pubmed_fetch_error", error=str(exc), pmid=record_id)
            return None
