"""Shared LLM factory for lightweight agent auxiliary tasks.

Centralises the build logic so the deployment name is configured
once via ``AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`` (env/settings).
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from src.core.config import get_settings

logger = logging.getLogger(__name__)

_DEFAULT_LIGHTWEIGHT_MODEL = "model-router"


def _resolve_lightweight_deployment() -> str:
    settings = get_settings()
    deployment = getattr(settings, "AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT", None)
    return deployment or _DEFAULT_LIGHTWEIGHT_MODEL


def build_lightweight_llm(
    *,
    temperature: float = 0,
    max_tokens: int = 512,
    request_timeout: float | None = None,
    use_responses_api: bool | None = None,
) -> BaseChatModel:
    """Build a LangChain chat model for lightweight auxiliary tasks.

    Targets the deployment configured via
    ``AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`` (defaults to ``model-router``).
    """
    settings = get_settings()
    deployment = _resolve_lightweight_deployment()

    endpoint = getattr(settings, "AZURE_OPENAI_CHAT_ENDPOINT", None) or getattr(
        settings, "AZURE_OPENAI_ENDPOINT", ""
    )
    api_key = getattr(settings, "AZURE_OPENAI_CHAT_API_KEY", None) or getattr(
        settings, "AZURE_OPENAI_API_KEY", ""
    )
    api_version = getattr(settings, "AZURE_OPENAI_CHAT_API_VERSION", None) or getattr(
        settings, "AZURE_OPENAI_API_VERSION", "2024-06-01"
    )

    logger.info("Lightweight LLM deployment resolved to: %s", deployment)

    if not endpoint or not api_key:
        raise RuntimeError(
            "Azure/OpenAI chat endpoint and API key must be configured. "
            "Set AZURE_OPENAI_CHAT_ENDPOINT + AZURE_OPENAI_CHAT_API_KEY "
            "(or the non-CHAT variants)."
        )

    _accepts_temperature = not deployment.startswith("gpt-5")

    if request_timeout is None:
        request_timeout = getattr(settings, "AGENT_LIGHTWEIGHT_REQUEST_TIMEOUT", 30.0)
    max_retries = getattr(settings, "AGENT_LLM_MAX_RETRIES", 2)

    extra: dict[str, Any] = {
        "request_timeout": request_timeout,
        "max_retries": max_retries,
    }
    if _accepts_temperature:
        extra["temperature"] = temperature
    extra["use_responses_api"] = (
        False if use_responses_api is None else use_responses_api
    )

    reasoning_effort = getattr(
        settings, "AGENT_LIGHTWEIGHT_REASONING_EFFORT", "minimal"
    )
    if deployment.startswith("gpt-5") and reasoning_effort:
        extra["reasoning_effort"] = reasoning_effort

    from src.core.openai_endpoint import classify_openai_endpoint

    if classify_openai_endpoint(endpoint) == "openai_compatible":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=deployment,
            api_key=api_key,
            base_url=endpoint,
            max_tokens=max_tokens,
            **extra,
        )

    from langchain_openai import AzureChatOpenAI

    return AzureChatOpenAI(
        azure_deployment=deployment,
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
        max_tokens=max_tokens,
        **extra,
    )


def get_lightweight_model_name() -> str:
    """Return the configured lightweight model/deployment name."""
    return _resolve_lightweight_deployment()
