"""ChEMBL bioactive molecules database connector via REST API."""

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

_BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"


def _build_content(molecule: Dict[str, Any]) -> str:
    parts: List[str] = []
    if struct := molecule.get("molecule_structures", {}):
        if smiles := struct.get("canonical_smiles"):
            parts.append(f"SMILES: {smiles}")
    if props := molecule.get("molecule_properties", {}):
        if mw := props.get("full_mwt"):
            parts.append(f"Molecular Weight: {mw}")
        if logp := props.get("alogp"):
            parts.append(f"AlogP: {logp}")
        if rule := props.get("ro5_pass"):
            parts.append(f"Ro5: {rule}")
    if mtype := molecule.get("molecule_type"):
        parts.append(f"Type: {mtype}")
    return "\n".join(parts)


def _parse_molecule(mol: Dict[str, Any]) -> ConnectorResult:
    chembl_id = mol.get("molecule_chembl_id", "")
    pref_name = mol.get("pref_name") or chembl_id

    metadata = {
        "chembl_id": chembl_id,
        "molecule_type": mol.get("molecule_type"),
        "max_phase": mol.get("max_phase"),
        "indication_class": mol.get("indication_class"),
    }
    if struct := mol.get("molecule_structures", {}):
        metadata["smiles"] = struct.get("canonical_smiles", "")
        metadata["inchi_key"] = struct.get("standard_inchi_key", "")

    return ConnectorResult(
        id=chembl_id,
        title=pref_name,
        source="chembl",
        url=f"https://www.ebi.ac.uk/chembl/compound_report_card/{chembl_id}/",
        content=_build_content(mol),
        metadata=metadata,
        document_type="compound",
    )


class ChEMBLConnector(ExternalDBConnector):
    """ChEMBL bioactive molecule and drug discovery data."""

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="chembl",
            display_name="ChEMBL",
            description="Bioactive molecules with drug-like properties (2.4M+ compounds)",
            domains=[ConnectorDomain.CHEMISTRY, ConnectorDomain.BIOMEDICAL],
            capabilities=[ConnectorCapability.SEARCH, ConnectorCapability.FETCH],
            base_url=_BASE_URL,
            rate_limit_per_second=5.0,
            max_results_per_query=100,
        )

    async def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ConnectorResult]:
        del filters  # filtering happens via ChEMBL field-suffixed query params
        params = {
            "molecule_synonyms__molecule_synonym__icontains": query,
            "limit": min(max_results, self.info.max_results_per_query),
            "format": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(f"{_BASE_URL}/molecule.json", params=params)
                resp.raise_for_status()
            molecules = resp.json().get("molecules", [])
            return [_parse_molecule(m) for m in molecules]
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "chembl_search_http_error",
                status=exc.response.status_code,
                query=query,
            )
            return []
        except Exception as exc:
            logger.error("chembl_search_error", error=str(exc), query=query)
            return []

    async def fetch_by_id(self, record_id: str) -> Optional[ConnectorResult]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(f"{_BASE_URL}/molecule/{record_id}.json")
                resp.raise_for_status()
            return _parse_molecule(resp.json())
        except Exception as exc:
            logger.error("chembl_fetch_error", error=str(exc), id=record_id)
            return None
