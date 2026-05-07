"""Shared LLM factory for lightweight agent auxiliary tasks.

Centralises the build logic for classifier, compactor, reflection,
planner, and memory-store LLMs so the deployment name is configured
once via ``AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`` (env/settings).
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from src.core.config import get_settings
from src.core.openai_endpoint import classify_openai_endpoint

logger = logging.getLogger(__name__)

_DEFAULT_LIGHTWEIGHT_MODEL = "model-router"


def _resolve_lightweight_deployment() -> str:
    settings = get_settings()
    return settings.AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT or _DEFAULT_LIGHTWEIGHT_MODEL


def build_lightweight_llm(
    *,
    temperature: float = 0,
    max_tokens: int = 512,
    request_timeout: float | None = None,
) -> BaseChatModel:
    """Build a LangChain chat model for lightweight auxiliary tasks.

    Uses the same Azure/OpenAI config resolution as ``graph._build_llm``
    but targets the lightweight deployment configured via
    ``AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`` (defaults to model-router).
    """
    settings = get_settings()

    endpoint = (
        settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT or ""
    )
    api_key = settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY or ""
    api_version = (
        settings.AZURE_OPENAI_CHAT_API_VERSION or settings.AZURE_OPENAI_API_VERSION
    )
    deployment = _resolve_lightweight_deployment()
    logger.info("Lightweight LLM deployment resolved to: %s", deployment)

    if not endpoint or not api_key:
        raise RuntimeError(
            "Azure/OpenAI chat endpoint and API key must be configured. "
            "Set AZURE_OPENAI_CHAT_ENDPOINT + AZURE_OPENAI_CHAT_API_KEY "
            "(or the non-CHAT variants)."
        )

    extra: dict[str, Any] = {}
    if request_timeout is not None:
        extra["request_timeout"] = request_timeout

    if classify_openai_endpoint(endpoint) == "openai_compatible":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=deployment,
            api_key=api_key,
            base_url=endpoint,
            temperature=temperature,
            max_tokens=max_tokens,
            **extra,
        )

    from langchain_openai import AzureChatOpenAI

    return AzureChatOpenAI(
        azure_deployment=deployment,
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
        temperature=temperature,
        max_tokens=max_tokens,
        **extra,
    )


def get_lightweight_model_name() -> str:
    """Return the configured lightweight model/deployment name."""
    return _resolve_lightweight_deployment()
