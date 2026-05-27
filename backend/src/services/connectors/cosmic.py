"""COSMIC cancer mutation database connector.

NOTE: COSMIC requires authentication (academic licence) for full data download.
This connector exposes the COSMIC public API endpoints for gene/mutation lookups.
"""

from __future__ import annotations

import base64
import os
from typing import Any, Dict, List, Optional

import httpx
import structlog

from .base import (
    ConnectorCapability,
    ConnectorDomain,
    ConnectorInfo,
    ConnectorResult,
    ExternalDBConnector,
)

logger = structlog.get_logger(__name__)

_BASE_URL = "https://cancer.sanger.ac.uk/cosmic"
_API_BASE_URL = "https://cancer.sanger.ac.uk/api/v1"


def _parse_gene(record: Dict[str, Any]) -> ConnectorResult:
    gene = record.get("gene_symbol") or record.get("symbol") or ""
    parts: List[str] = []
    if name := record.get("gene_name"):
        parts.append(f"Name: {name}")
    if chrom := record.get("chromosome"):
        parts.append(f"Chromosome: {chrom}")
    if mutations := record.get("mutation_count"):
        parts.append(f"Mutation Count: {mutations}")
    if samples := record.get("sample_count"):
        parts.append(f"Sample Count: {samples}")

    return ConnectorResult(
        id=gene,
        title=gene or "Unknown gene",
        source="cosmic",
        url=f"{_BASE_URL}/gene/analysis?ln={gene}",
        content="\n".join(parts),
        metadata=record,
        document_type="gene",
    )


class COSMICConnector(ExternalDBConnector):
    """COSMIC: Catalogue Of Somatic Mutations In Cancer."""

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="cosmic",
            display_name="COSMIC",
            description="Curated database of somatic mutations in cancer (Cancer Gene Census)",
            domains=[ConnectorDomain.BIOMEDICAL, ConnectorDomain.GENOMICS],
            capabilities=[ConnectorCapability.SEARCH],
            base_url=_BASE_URL,
            requires_api_key=True,
            api_key_env_var="COSMIC_AUTH",
            rate_limit_per_second=2.0,
            max_results_per_query=50,
        )

    def _auth_headers(self) -> Dict[str, str]:
        creds = os.environ.get("COSMIC_AUTH")
        if not creds:
            return {}
        if ":" in creds:
            encoded = base64.b64encode(creds.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        return {"Authorization": f"Basic {creds}"}

    async def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ConnectorResult]:
        del filters  # COSMIC public lookup is gene-based, no extra filtering
        if not self.is_available():
            logger.warning("cosmic_not_authenticated")
            return [
                ConnectorResult(
                    id=query,
                    title=f"COSMIC: {query}",
                    source="cosmic",
                    url=f"{_BASE_URL}/gene/analysis?ln={query}",
                    content=(
                        "COSMIC requires academic authentication. "
                        "Set COSMIC_AUTH env var as 'email:password' to enable API access."
                    ),
                    metadata={"gene_symbol": query, "auth_required": True},
                    document_type="gene",
                )
            ]

        url = f"{_API_BASE_URL}/genes/{query}"
        try:
            async with httpx.AsyncClient(
                timeout=30.0, headers=self._auth_headers()
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return [_parse_gene(r) for r in data[:max_results]]
            return [_parse_gene(data)]
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "cosmic_search_http_error",
                status=exc.response.status_code,
                query=query,
            )
            return []
        except Exception as exc:
            logger.error("cosmic_search_error", error=str(exc), query=query)
            return []
