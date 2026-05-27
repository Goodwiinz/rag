"""External database connector base protocol.

All external database connectors implement this interface, enabling the agent
to search and ingest from 250+ data sources through a single standard API.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ConnectorCapability(str, Enum):
    SEARCH = "search"
    FETCH = "fetch"
    BULK = "bulk"


class ConnectorDomain(str, Enum):
    BIOMEDICAL = "biomedical"
    CHEMISTRY = "chemistry"
    GENOMICS = "genomics"
    FINANCE = "finance"
    ECONOMIC = "economic"
    CLINICAL = "clinical"
    LITERATURE = "literature"
    PATENT = "patent"
    GENERAL = "general"


@dataclass(frozen=True)
class ConnectorInfo:
    """Static metadata describing a connector."""

    name: str
    display_name: str
    description: str
    domains: List[ConnectorDomain]
    capabilities: List[ConnectorCapability]
    base_url: str
    requires_api_key: bool = False
    api_key_env_var: Optional[str] = None
    rate_limit_per_second: float = 3.0
    max_results_per_query: int = 100


@dataclass
class ConnectorResult:
    """A single result returned by any connector's search or fetch."""

    id: str
    title: str
    source: str
    url: str
    content: str = ""
    authors: List[str] = field(default_factory=list)
    published_date: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    document_type: str = "article"

    def to_nous_document(self) -> Dict[str, Any]:
        """Transform into NOUS DocumentMetadata-compatible dict for ingestion."""
        return {
            "title": self.title,
            "content": self.content,
            "source_url": self.url,
            "authors": self.authors,
            "published_date": self.published_date,
            "document_type": self.document_type,
            "metadata": {
                "external_id": self.id,
                "source": self.source,
                **self.metadata,
            },
        }


class ExternalDBConnector(abc.ABC):
    """Abstract base class for all external database connectors.

    Subclasses must implement ``info``, ``search``, and ``fetch_by_id``.
    The ``transform_result`` hook can be overridden for custom post-processing.
    """

    @property
    @abc.abstractmethod
    def info(self) -> ConnectorInfo:
        """Return static metadata about this connector."""

    @abc.abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ConnectorResult]:
        """Search the external database and return a list of results."""

    async def fetch_by_id(self, record_id: str) -> Optional[ConnectorResult]:
        """Fetch a single record by its external ID.

        Default: not supported. Override when the database provides a fetch endpoint.
        """
        del record_id
        return None

    def is_available(self) -> bool:
        """Return True when the connector can serve requests (e.g. API key present)."""
        if not self.info.requires_api_key:
            return True
        import os
        env_var = self.info.api_key_env_var or ""
        return bool(os.environ.get(env_var))
