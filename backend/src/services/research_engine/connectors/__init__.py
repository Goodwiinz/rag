"""Source connectors for the research engine."""

from src.services.research_engine.connectors.arxiv_connector import ArxivConnector
from src.services.research_engine.connectors.base import SourceConnector, SourceDocument
from src.services.research_engine.connectors.rag_store_connector import RagStoreConnector
from src.services.research_engine.connectors.semantic_scholar_connector import (
    SemanticScholarConnector,
)

__all__ = [
    "ArxivConnector",
    "RagStoreConnector",
    "SemanticScholarConnector",
    "SourceConnector",
    "SourceDocument",
]
