"""BioServices bridge connector.

Wraps the ``bioservices`` Python library to provide access to ~70 biological
web services (KEGG, UniProt, ChEBI, Reactome, etc.) through the standard
ExternalDBConnector interface.

Requires: ``pip install bioservices``
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import structlog

from .base import (
    ConnectorCapability,
    ConnectorDomain,
    ConnectorInfo,
    ConnectorResult,
    ExternalDBConnector,
)

logger = structlog.get_logger(__name__)

# Services exposed through the bridge.  Each entry maps a short name to
# (bioservices_class_name, description, search_method, id_field).
_SUPPORTED_SERVICES: Dict[str, Dict[str, str]] = {
    "kegg": {
        "class": "KEGG",
        "desc": "KEGG pathway/compound database",
        "search": "find",
    },
    "chebi": {
        "class": "ChEBI",
        "desc": "Chemical Entities of Biological Interest",
        "search": "getLiteEntity",
    },
    "reactome": {
        "class": "Reactome",
        "desc": "Biological pathways and reactions",
        "search": "search_query",
    },
    "biomodels": {
        "class": "BioModels",
        "desc": "Mathematical models of biological systems",
        "search": "search",
    },
    "wikipathways": {
        "class": "WikiPathways",
        "desc": "Community-curated biological pathways",
        "search": "findPathwaysByText",
    },
}


def _bioservices_available() -> bool:
    try:
        import bioservices  # noqa: F401
        return True
    except ImportError:
        return False


class BioServicesBridgeConnector(ExternalDBConnector):
    """Bridge that exposes ~70 BioServices databases through one connector."""

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="bioservices",
            display_name="BioServices (70+ databases)",
            description=(
                "Bridge to the BioServices Python library providing access to "
                "KEGG, ChEBI, Reactome, BioModels, WikiPathways, and ~65 more "
                "biological web services."
            ),
            domains=[
                ConnectorDomain.BIOMEDICAL,
                ConnectorDomain.CHEMISTRY,
                ConnectorDomain.GENOMICS,
            ],
            capabilities=[ConnectorCapability.SEARCH],
            base_url="https://bioservices.readthedocs.io/",
            requires_api_key=False,
            rate_limit_per_second=2.0,
            max_results_per_query=50,
        )

    def is_available(self) -> bool:
        return _bioservices_available()

    async def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ConnectorResult]:
        if not _bioservices_available():
            logger.warning("bioservices not installed")
            return []

        service_name = (filters or {}).get("service", "kegg")
        if service_name not in _SUPPORTED_SERVICES:
            logger.warning("unsupported_bioservice", service=service_name)
            return []

        try:
            results = await asyncio.to_thread(
                self._sync_search, service_name, query, max_results
            )
            return results
        except Exception:
            logger.exception("bioservices_search_failed", service=service_name)
            return []

    def _sync_search(
        self, service_name: str, query: str, max_results: int
    ) -> List[ConnectorResult]:
        """Run the blocking BioServices call in a thread."""
        import bioservices  # noqa: F811

        svc_info = _SUPPORTED_SERVICES[service_name]
        cls = getattr(bioservices, svc_info["class"])
        svc = cls()

        method = getattr(svc, svc_info["search"])
        raw = method(query)

        return self._parse_results(service_name, raw, max_results)

    def _parse_results(
        self, service_name: str, raw: Any, max_results: int
    ) -> List[ConnectorResult]:
        results: List[ConnectorResult] = []

        if isinstance(raw, str):
            # KEGG returns newline-delimited results
            for line in raw.strip().split("\n")[:max_results]:
                parts = line.split("\t", 1)
                entry_id = parts[0].strip() if parts else ""
                title = parts[1].strip() if len(parts) > 1 else entry_id
                if entry_id:
                    results.append(
                        ConnectorResult(
                            id=entry_id,
                            title=title,
                            source=f"bioservices:{service_name}",
                            url=f"https://www.genome.jp/entry/{entry_id}",
                            content=title,
                            document_type="database_entry",
                            metadata={"service": service_name},
                        )
                    )
        elif isinstance(raw, list):
            for item in raw[:max_results]:
                if isinstance(item, dict):
                    entry_id = str(
                        item.get("id", item.get("stId", item.get("chebiId", "")))
                    )
                    title = str(
                        item.get("name", item.get("displayName", entry_id))
                    )
                    results.append(
                        ConnectorResult(
                            id=entry_id,
                            title=title,
                            source=f"bioservices:{service_name}",
                            url=f"https://reactome.org/content/detail/{entry_id}",
                            content=str(item.get("description", title)),
                            document_type="database_entry",
                            metadata={"service": service_name, "raw": item},
                        )
                    )
                elif isinstance(item, str):
                    results.append(
                        ConnectorResult(
                            id=item,
                            title=item,
                            source=f"bioservices:{service_name}",
                            url="",
                            content=item,
                            document_type="database_entry",
                            metadata={"service": service_name},
                        )
                    )
        elif isinstance(raw, dict):
            for key, val in list(raw.items())[:max_results]:
                results.append(
                    ConnectorResult(
                        id=str(key),
                        title=str(val) if isinstance(val, str) else str(key),
                        source=f"bioservices:{service_name}",
                        url="",
                        content=str(val)[:500] if val else "",
                        document_type="database_entry",
                        metadata={"service": service_name},
                    )
                )

        return results

    @classmethod
    def list_supported_services(cls) -> List[Dict[str, str]]:
        """Return the list of supported BioServices services."""
        return [
            {"name": name, "description": info["desc"]}
            for name, info in _SUPPORTED_SERVICES.items()
        ]
