"""Alpha Vantage financial market data connector."""

from __future__ import annotations

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

_BASE_URL = "https://www.alphavantage.co/query"


def _format_quote(symbol: str, quote: Dict[str, Any]) -> str:
    parts = [
        f"Symbol: {symbol}",
        f"Price: {quote.get('05. price', 'N/A')}",
        f"Change: {quote.get('09. change', 'N/A')} "
        f"({quote.get('10. change percent', 'N/A')})",
        f"Volume: {quote.get('06. volume', 'N/A')}",
        f"Latest Trading Day: {quote.get('07. latest trading day', 'N/A')}",
    ]
    return "\n".join(parts)


class AlphaVantageConnector(ExternalDBConnector):
    """Alpha Vantage real-time and historical market data."""

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="alpha_vantage",
            display_name="Alpha Vantage",
            description="Stock prices, forex, crypto, technical indicators, fundamentals",
            domains=[ConnectorDomain.FINANCE],
            capabilities=[ConnectorCapability.SEARCH, ConnectorCapability.FETCH],
            base_url=_BASE_URL,
            requires_api_key=True,
            api_key_env_var="ALPHA_VANTAGE_API_KEY",
            rate_limit_per_second=0.083,
            max_results_per_query=10,
        )

    def _api_key(self) -> Optional[str]:
        return os.environ.get("ALPHA_VANTAGE_API_KEY")

    async def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ConnectorResult]:
        del filters  # Alpha Vantage SYMBOL_SEARCH does not support filtering
        api_key = self._api_key()
        if not api_key:
            logger.warning("alpha_vantage_no_api_key")
            return []

        params = {
            "function": "SYMBOL_SEARCH",
            "keywords": query,
            "apikey": api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(_BASE_URL, params=params)
                resp.raise_for_status()
            matches = resp.json().get("bestMatches", [])[:max_results]
            results = []
            for match in matches:
                symbol = match.get("1. symbol", "")
                name = match.get("2. name", symbol)
                metadata = {
                    "symbol": symbol,
                    "name": name,
                    "type": match.get("3. type", ""),
                    "region": match.get("4. region", ""),
                    "currency": match.get("8. currency", ""),
                    "match_score": match.get("9. matchScore", ""),
                }
                results.append(
                    ConnectorResult(
                        id=symbol,
                        title=f"{symbol} — {name}",
                        source="alpha_vantage",
                        url=f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}",
                        content=f"Symbol: {symbol}\nName: {name}\nType: {metadata['type']}\nRegion: {metadata['region']}",
                        metadata=metadata,
                        document_type="security",
                    )
                )
            return results
        except Exception as exc:
            logger.error("alpha_vantage_search_error", error=str(exc), query=query)
            return []

    async def fetch_by_id(self, record_id: str) -> Optional[ConnectorResult]:
        api_key = self._api_key()
        if not api_key:
            return None

        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": record_id,
            "apikey": api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(_BASE_URL, params=params)
                resp.raise_for_status()
            quote = resp.json().get("Global Quote", {})
            if not quote:
                return None
            return ConnectorResult(
                id=record_id,
                title=f"{record_id} Quote",
                source="alpha_vantage",
                url=f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={record_id}",
                content=_format_quote(record_id, quote),
                metadata={"symbol": record_id, "quote": quote},
                document_type="quote",
            )
        except Exception as exc:
            logger.error("alpha_vantage_fetch_error", error=str(exc), symbol=record_id)
            return None
