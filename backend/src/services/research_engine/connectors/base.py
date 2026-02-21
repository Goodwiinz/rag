"""Base classes for source connectors."""

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SourceDocument:
    """A document retrieved from a source connector."""

    connector_type: str
    external_id: Optional[str] = None
    title: str = ""
    authors: List[str] = field(default_factory=list)
    abstract: Optional[str] = None
    url: Optional[str] = None
    full_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_hash: Optional[str] = None

    def compute_hash(self) -> None:
        """Compute SHA-256 hash of title + abstract + full_text."""
        parts = [
            self.title or "",
            self.abstract or "",
            self.full_text or "",
        ]
        combined = "".join(parts)
        self.content_hash = hashlib.sha256(combined.encode()).hexdigest()


class SourceConnector(ABC):
    """Abstract base class for source connectors."""

    @abstractmethod
    async def search(
        self, query: str, max_results: int = 50, **kwargs: Any
    ) -> List[SourceDocument]:
        """Search the source for documents matching the query."""
        ...
