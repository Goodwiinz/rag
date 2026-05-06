"""External database connector registry.

Provides a central registry for discovering and accessing external database
connectors.  Import ``connector_registry`` to search across all registered
connectors, or import individual connectors directly.
"""

from __future__ import annotations

from threading import Lock
from typing import Dict, List, Optional

from .base import (
    ConnectorCapability,
    ConnectorDomain,
    ConnectorInfo,
    ConnectorResult,
    ExternalDBConnector,
)


class ConnectorRegistry:
    """Thread-safe singleton that holds all registered connectors."""

    _instance: Optional[ConnectorRegistry] = None
    _lock = Lock()
    _connectors: Dict[str, ExternalDBConnector]

    def __new__(cls) -> ConnectorRegistry:
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._connectors = {}
        return cls._instance

    def register(self, connector: ExternalDBConnector) -> None:
        self._connectors[connector.info.name] = connector

    def get(self, name: str) -> Optional[ExternalDBConnector]:
        return self._connectors.get(name)

    def list_all(self) -> List[ExternalDBConnector]:
        return list(self._connectors.values())

    def list_available(self) -> List[ExternalDBConnector]:
        return [c for c in self._connectors.values() if c.is_available()]

    def search_by_domain(self, domain: ConnectorDomain) -> List[ExternalDBConnector]:
        return [
            c
            for c in self._connectors.values()
            if domain in c.info.domains and c.is_available()
        ]

    def search_by_capability(
        self, capability: ConnectorCapability
    ) -> List[ExternalDBConnector]:
        return [
            c
            for c in self._connectors.values()
            if capability in c.info.capabilities and c.is_available()
        ]

    @property
    def count(self) -> int:
        return len(self._connectors)

    @property
    def available_count(self) -> int:
        return len(self.list_available())


# Module-level singleton
connector_registry = ConnectorRegistry()


def _register_builtin_connectors() -> None:
    """Lazily import and register all built-in connectors."""
    from .pubmed import PubMedConnector
    from .uniprot import UniProtConnector
    from .chembl import ChEMBLConnector
    from .pubchem import PubChemConnector
    from .sec_edgar import SECEdgarConnector
    from .fred import FREDConnector
    from .alpha_vantage import AlphaVantageConnector
    from .zinc import ZINCConnector
    from .cosmic import COSMICConnector
    from .clinical_trials import ClinicalTrialsConnector
    from .bioservices_bridge import BioServicesBridgeConnector

    for cls in (
        PubMedConnector,
        UniProtConnector,
        ChEMBLConnector,
        PubChemConnector,
        SECEdgarConnector,
        FREDConnector,
        AlphaVantageConnector,
        ZINCConnector,
        COSMICConnector,
        ClinicalTrialsConnector,
        BioServicesBridgeConnector,
    ):
        connector_registry.register(cls())


_register_builtin_connectors()

__all__ = [
    "ConnectorCapability",
    "ConnectorDomain",
    "ConnectorInfo",
    "ConnectorResult",
    "ExternalDBConnector",
    "ConnectorRegistry",
    "connector_registry",
]
