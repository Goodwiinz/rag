"""ZINC purchasable compounds database connector."""

from __future__ import annotations

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

_BASE_URL = "https://zinc20.docking.org"


def _parse_substance(sub: Dict[str, Any]) -> ConnectorResult:
    zinc_id = sub.get("zinc_id") or sub.get("preferred_name") or ""
    smiles = sub.get("smiles", "")

    parts: List[str] = []
    if smiles:
        parts.append(f"SMILES: {smiles}")
    if mw := sub.get("mwt"):
        parts.append(f"Molecular Weight: {mw}")
    if logp := sub.get("logp"):
        parts.append(f"LogP: {logp}")
    if rb := sub.get("rb"):
        parts.append(f"Rotatable Bonds: {rb}")
    if hba := sub.get("hba"):
        parts.append(f"H-Bond Acceptors: {hba}")
    if hbd := sub.get("hbd"):
        parts.append(f"H-Bond Donors: {hbd}")

    metadata = {
        "zinc_id": zinc_id,
        "smiles": smiles,
        "mwt": sub.get("mwt"),
        "logp": sub.get("logp"),
        "purchasable": sub.get("purchasable"),
    }

    return ConnectorResult(
        id=zinc_id,
        title=zinc_id or "Unknown ZINC compound",
        source="zinc",
        url=f"{_BASE_URL}/substances/{zinc_id}/",
        content="\n".join(parts),
        metadata=metadata,
        document_type="compound",
    )


class ZINCConnector(ExternalDBConnector):
    """ZINC database of purchasable, drug-like compounds for virtual screening."""

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="zinc",
            display_name="ZINC",
            description="230M+ purchasable compounds for virtual screening and docking",
            domains=[ConnectorDomain.CHEMISTRY],
            capabilities=[ConnectorCapability.SEARCH, ConnectorCapability.FETCH],
            base_url=_BASE_URL,
            rate_limit_per_second=2.0,
            max_results_per_query=100,
        )

    async def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ConnectorResult]:
        del filters  # ZINC uses query-string filters via the q param
        url = f"{_BASE_URL}/substances/search/"
        params: Dict[str, Any] = {
            "q": query,
            "page_size": min(max_results, self.info.max_results_per_query),
            "output_format": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
            data = resp.json()
            substances = data.get("results", []) if isinstance(data, dict) else data
            return [_parse_substance(s) for s in substances[:max_results]]
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "zinc_search_http_error",
                status=exc.response.status_code,
                query=query,
            )
            return []
        except Exception as exc:
            logger.error("zinc_search_error", error=str(exc), query=query)
            return []

    async def fetch_by_id(self, record_id: str) -> Optional[ConnectorResult]:
        url = f"{_BASE_URL}/substances/{record_id}.json"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            return _parse_substance(resp.json())
        except Exception as exc:
            logger.error("zinc_fetch_error", error=str(exc), id=record_id)
            return None
