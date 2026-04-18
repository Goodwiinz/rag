"""Unit tests for the external database connector architecture."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.connectors import connector_registry
from src.services.connectors.base import (
    ConnectorCapability,
    ConnectorDomain,
    ConnectorInfo,
    ConnectorResult,
    ExternalDBConnector,
)


# ---------------------------------------------------------------------------
# Base / Registry tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_connector_registry_has_all_builtin_connectors() -> None:
    """Registry should expose all 11 built-in connectors (10 + bioservices bridge)."""
    expected = {
        "pubmed",
        "uniprot",
        "chembl",
        "pubchem",
        "sec_edgar",
        "fred",
        "alpha_vantage",
        "zinc",
        "cosmic",
        "clinical_trials",
        "bioservices",
    }
    actual = {c.info.name for c in connector_registry.list_all()}
    assert expected.issubset(actual), f"Missing: {expected - actual}"


@pytest.mark.unit
def test_search_by_domain() -> None:
    biomedical = connector_registry.search_by_domain(ConnectorDomain.BIOMEDICAL)
    names = {c.info.name for c in biomedical}
    assert "pubmed" in names
    assert "fred" not in names  # FRED is finance, not biomedical


@pytest.mark.unit
def test_search_by_capability() -> None:
    """Lookup by capability filters to *available* connectors only.

    Connectors that need API keys (FRED, Alpha Vantage, COSMIC) or extra
    packages (BioServices) drop out when those preconditions aren't met,
    so the absolute count depends on the runtime environment.
    """
    searchers = connector_registry.search_by_capability(ConnectorCapability.SEARCH)
    names = {c.info.name for c in searchers}
    # These 7 require neither an API key nor an external library.
    keyless = {
        "pubmed",
        "uniprot",
        "chembl",
        "pubchem",
        "sec_edgar",
        "zinc",
        "clinical_trials",
    }
    assert keyless.issubset(names), f"Missing always-available: {keyless - names}"


@pytest.mark.unit
def test_connector_result_to_nous_document() -> None:
    result = ConnectorResult(
        id="123",
        title="Test Paper",
        source="pubmed",
        url="https://example.com/123",
        content="abstract text",
        authors=["Doe J"],
        published_date="2024",
        metadata={"journal": "Nature"},
    )
    doc = result.to_nous_document()
    assert doc["title"] == "Test Paper"
    assert doc["metadata"]["external_id"] == "123"
    assert doc["metadata"]["source"] == "pubmed"
    assert doc["metadata"]["journal"] == "Nature"


@pytest.mark.unit
def test_is_available_when_no_api_key_required() -> None:
    pubmed = connector_registry.get("pubmed")
    assert pubmed is not None
    assert pubmed.is_available() is True


@pytest.mark.unit
def test_is_available_respects_api_key_env_var() -> None:
    fred = connector_registry.get("fred")
    assert fred is not None

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("FRED_API_KEY", None)
        assert fred.is_available() is False

    with patch.dict(os.environ, {"FRED_API_KEY": "xyz"}):
        assert fred.is_available() is True


# ---------------------------------------------------------------------------
# Connector contract tests (each connector exposes valid info)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "name",
    [
        "pubmed",
        "uniprot",
        "chembl",
        "pubchem",
        "sec_edgar",
        "fred",
        "alpha_vantage",
        "zinc",
        "cosmic",
        "clinical_trials",
        "bioservices",
    ],
)
def test_connector_info_is_valid(name: str) -> None:
    connector = connector_registry.get(name)
    assert connector is not None
    info = connector.info
    assert info.name == name
    assert info.display_name
    assert info.description
    assert info.domains
    assert info.capabilities
    assert info.base_url.startswith("http") or info.base_url.startswith("https")
    assert info.rate_limit_per_second > 0


# ---------------------------------------------------------------------------
# Custom connector registration test
# ---------------------------------------------------------------------------


class _FakeConnector(ExternalDBConnector):
    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="fake",
            display_name="Fake DB",
            description="test",
            domains=[ConnectorDomain.GENERAL],
            capabilities=[ConnectorCapability.SEARCH],
            base_url="https://example.com",
        )

    async def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ConnectorResult]:
        del filters
        return [
            ConnectorResult(
                id=f"fake-{i}",
                title=f"{query} #{i}",
                source="fake",
                url="https://example.com",
            )
            for i in range(min(max_results, 3))
        ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_custom_connector_can_be_registered_and_searched() -> None:
    fake = _FakeConnector()
    connector_registry.register(fake)

    try:
        retrieved = connector_registry.get("fake")
        assert retrieved is not None
        assert retrieved is fake

        results = await retrieved.search("hello", max_results=2)
        assert len(results) == 2
        assert results[0].title == "hello #0"
    finally:
        connector_registry._connectors.pop("fake", None)


# ---------------------------------------------------------------------------
# PubChem search (mocked HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pubchem_search_parses_compounds() -> None:
    from src.services.connectors.pubchem import PubChemConnector

    cids_payload = {"IdentifierList": {"CID": [2244]}}
    detail_payload = {
        "PC_Compounds": [
            {
                "CID": 2244,
                "props": [
                    {
                        "urn": {"label": "IUPAC Name", "name": "Preferred"},
                        "value": {"sval": "2-acetoxybenzoic acid"},
                    },
                    {
                        "urn": {"label": "Molecular Formula"},
                        "value": {"sval": "C9H8O4"},
                    },
                ],
            }
        ]
    }

    cids_resp = MagicMock()
    cids_resp.json.return_value = cids_payload
    cids_resp.raise_for_status = MagicMock()

    detail_resp = MagicMock()
    detail_resp.json.return_value = detail_payload
    detail_resp.raise_for_status = MagicMock()

    fake_client = MagicMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    fake_client.get = AsyncMock(side_effect=[cids_resp, detail_resp])

    with patch("httpx.AsyncClient", return_value=fake_client):
        connector = PubChemConnector()
        results = await connector.search("aspirin", max_results=1)

    assert len(results) == 1
    assert results[0].source == "pubchem"
    assert "2-acetoxybenzoic acid" in results[0].title
    assert results[0].metadata["CID"] == "2244"
