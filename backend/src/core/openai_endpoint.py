"""Helpers for routing Azure and OpenAI-compatible model endpoints."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

EndpointKind = Literal["azure", "openai_compatible"]


def _parse_endpoint(endpoint: str) -> tuple[str, str]:
    normalized = endpoint.strip()
    if "://" not in normalized:
        normalized = f"https://{normalized}"

    parsed = urlparse(normalized)
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return host, path


def classify_openai_endpoint(endpoint: str) -> EndpointKind:
    """Classify an endpoint for Azure/OpenAI client routing.

    - Bare Azure resource endpoints use the AzureOpenAI / AzureChatOpenAI clients.
    - Explicit ``/openai/v1`` or generic ``/v1`` paths use OpenAI-compatible clients.
    - Deployment-specific URLs are rejected.
    """

    _, path = _parse_endpoint(endpoint)

    if (
        "/openai/deployments/" in path
        or path.endswith("/chat/completions")
        or path.endswith("/embeddings")
    ):
        raise ValueError(
            "Configure the Azure resource endpoint only, not a deployment-specific URL. "
            "Set the endpoint to the resource base and provide the deployment name separately."
        )

    if path.endswith("/openai/v1") or path.endswith("/v1"):
        return "openai_compatible"

    return "azure"


def is_openai_compatible_endpoint(endpoint: str) -> bool:
    """Return True when the endpoint should be used with an OpenAI-compatible client."""

    return classify_openai_endpoint(endpoint) == "openai_compatible"
