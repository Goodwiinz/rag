"""PubChem compound database connector via PUG REST API."""

from __future__ import annotations

import urllib.parse
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

_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_COMPOUND_URL = f"{_BASE_URL}/compound"


def _build_content(props: Dict[str, Any]) -> str:
    """Build a human-readable content string from compound properties."""
    parts: List[str] = []
    if iupac := props.get("IUPACName"):
        parts.append(f"IUPAC Name: {iupac}")
    if formula := props.get("MolecularFormula"):
        parts.append(f"Molecular Formula: {formula}")
    if weight := props.get("MolecularWeight"):
        parts.append(f"Molecular Weight: {weight}")
    if smiles := props.get("CanonicalSMILES"):
        parts.append(f"SMILES: {smiles}")
    if inchi := props.get("InChI"):
        parts.append(f"InChI: {inchi}")
    return "\n".join(parts)


def _parse_compound(compound: Dict[str, Any]) -> ConnectorResult:
    """Parse a single PUG REST compound record into a ConnectorResult."""
    cid = str(compound.get("CID", ""))
    props = compound.get("props", [])

    flat: Dict[str, Any] = {"CID": cid}
    for prop in props:
        label = prop.get("urn", {}).get("label", "")
        name = prop.get("urn", {}).get("name", "")
        value = prop.get("value", {})
        # Extract first available value type
        val = value.get("sval") or value.get("fval") or value.get("ival") or ""
        key = f"{label}/{name}" if name else label
        flat[key] = val

    iupac = flat.get("IUPAC Name/Preferred", flat.get("IUPAC Name/Traditional", ""))
    title = str(iupac) if iupac else f"CID {cid}"

    metadata = {
        "CID": cid,
        "IUPACName": iupac,
        "MolecularFormula": flat.get("Molecular Formula", ""),
        "MolecularWeight": flat.get("Molecular Weight", ""),
        "CanonicalSMILES": flat.get("SMILES/Canonical", ""),
        "InChI": flat.get("InChI/Standard", ""),
    }

    return ConnectorResult(
        id=cid,
        title=str(title),
        source="pubchem",
        url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
        content=_build_content(metadata),
        metadata=metadata,
        document_type="compound",
    )


class PubChemConnector(ExternalDBConnector):
    """PubChem compound search via the PUG REST API."""

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="pubchem",
            display_name="PubChem",
            description="NIH chemical compound database with 110M+ compounds",
            domains=[ConnectorDomain.CHEMISTRY],
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
        """Search PubChem by compound name, returning up to *max_results* hits."""
        encoded = urllib.parse.quote(query, safe="")
        cids_url = f"{_COMPOUND_URL}/name/{encoded}/cids/JSON"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Step 1: resolve name to CID list
                resp = await client.get(cids_url)
                resp.raise_for_status()
                cid_list = (
                    resp.json()
                    .get("IdentifierList", {})
                    .get("CID", [])[:max_results]
                )
                if not cid_list:
                    return []

                # Step 2: fetch full compound records for those CIDs
                cids_csv = ",".join(str(c) for c in cid_list)
                detail_url = f"{_COMPOUND_URL}/cid/{cids_csv}/JSON"
                detail_resp = await client.get(detail_url)
                detail_resp.raise_for_status()

            compounds = (
                detail_resp.json().get("PC_Compounds", [])
            )
            return [_parse_compound(c) for c in compounds]

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "pubchem_search_http_error",
                status=exc.response.status_code,
                query=query,
            )
            return []
        except Exception as exc:
            logger.error("pubchem_search_error", error=str(exc), query=query)
            return []

    async def fetch_by_id(self, record_id: str) -> Optional[ConnectorResult]:
        """Fetch a single compound by its CID."""
        url = f"{_COMPOUND_URL}/cid/{record_id}/JSON"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            compounds = resp.json().get("PC_Compounds", [])
            if not compounds:
                return None
            return _parse_compound(compounds[0])

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "pubchem_fetch_http_error",
                status=exc.response.status_code,
                cid=record_id,
            )
            return None
        except Exception as exc:
            logger.error("pubchem_fetch_error", error=str(exc), cid=record_id)
            return None
