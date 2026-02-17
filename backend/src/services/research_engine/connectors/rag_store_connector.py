"""RAG Store source connector."""

from typing import Any, Callable, Coroutine, Dict, List

from src.services.research_engine.connectors.base import SourceConnector, SourceDocument


class RagStoreConnector(SourceConnector):
    """Connector that searches the local RAG store via a provided async function."""

    def __init__(
        self,
        search_fn: Callable[..., Coroutine[Any, Any, Dict[str, Any]]],
    ) -> None:
        self.search_fn = search_fn

    async def search(
        self, query: str, max_results: int = 50, **kwargs: Any
    ) -> List[SourceDocument]:
        """Search the local RAG store."""
        result = await self.search_fn(query, max_results)
        documents: List[SourceDocument] = []

        for item in result.get("results", []):
            documents.append(
                SourceDocument(
                    connector_type="rag_store",
                    external_id=item.get("id"),
                    title=item.get("title", ""),
                    full_text=item.get("content"),
                    metadata=item.get("metadata", {}),
                )
            )

        return documents
