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


def _main_chat_deployment() -> str:
    """The configured chat deployment — same chain ``_build_llm`` below uses."""
    settings = get_settings()
    return (
        settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
        or settings.AZURE_OPENAI_DEPLOYMENT_NAME
        or ""
    )


# Cache built chat models keyed by the builder's input args. Constructing a
# ChatOpenAI/AzureChatOpenAI spins up an HTTP client (~30-50ms); the synthesis
# path previously rebuilt one on every turn. deployment / reasoning_effort /
# max_retries / resolved request_timeout are settings-derived and stable at
# runtime, so they need not be part of the key — the same assumption the
# classifier / compactor / reflection single-instance caches already rely on.
_LIGHTWEIGHT_LLM_CACHE: dict[tuple, BaseChatModel] = {}
_SYNTHESIS_LLM_CACHE: dict[tuple, BaseChatModel] = {}


def reset_llm_caches() -> None:
    """Clear the factory's per-args LLM caches.

    For tests that exercise the real builders and need a fresh instance.
    """
    _LIGHTWEIGHT_LLM_CACHE.clear()
    _SYNTHESIS_LLM_CACHE.clear()


def _resolve_lightweight_deployment() -> str:
    """Lightweight deployment, falling back to the main chat deployment.

    The fallback used to be ``model-router``, which meant an unset or blank
    secret silently put the router back inside the agent loop — the exact
    configuration that produced the 30s timeout cap on research_llm_node
    (trace 019e1da5). Falling back to the configured chat deployment keeps a
    misconfigured environment on the model the operator actually chose, and
    makes "one deployment everywhere" the natural result of leaving the
    per-role overrides unset.
    """
    settings = get_settings()
    return settings.AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT or _main_chat_deployment()


def _resolve_synthesis_deployment() -> str:
    """Synthesis deploy falls back to lightweight, then the main deployment."""
    settings = get_settings()
    return (
        settings.AZURE_OPENAI_SYNTHESIS_DEPLOYMENT
        or settings.AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT
        or _main_chat_deployment()
    )


def _build_chat_llm(
    deployment: str,
    *,
    role_label: str,
    temperature: float = 0,
    max_tokens: int = 512,
    request_timeout: float | None = None,
    use_responses_api: bool | None = None,
    reasoning_effort: str | None = None,
    max_retries: int | None = None,
) -> BaseChatModel:
    """Shared core builder for lightweight + synthesis LLMs.

    Keeps the gpt-5 family quirks (no temperature, reasoning_effort)
    and Azure vs OpenAI-compatible endpoint selection in one place.
    """
    settings = get_settings()

    endpoint = (
        settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT or ""
    )
    api_key = settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY or ""
    api_version = (
        settings.AZURE_OPENAI_CHAT_API_VERSION or settings.AZURE_OPENAI_API_VERSION
    )
    logger.info("%s LLM deployment resolved to: %s", role_label, deployment)

    if not endpoint or not api_key:
        raise RuntimeError(
            "Azure/OpenAI chat endpoint and API key must be configured. "
            "Set AZURE_OPENAI_CHAT_ENDPOINT + AZURE_OPENAI_CHAT_API_KEY "
            "(or the non-CHAT variants)."
        )

    # All gpt-5 family deployments (gpt-5, gpt-5-mini, gpt-5-nano, etc.)
    # reject the `temperature` parameter — Azure returns 400. Skip it
    # rather than maintaining an explicit allowlist as new sizes ship.
    _accepts_temperature = not deployment.startswith("gpt-5")

    # Bound LLM call wall-clock + cap retries. Lightweight callers (classifier,
    # planner, reflection) get a shorter ceiling than the main agent so a stuck
    # model-router call cannot block the whole turn.
    if request_timeout is None:
        request_timeout = settings.AGENT_LIGHTWEIGHT_REQUEST_TIMEOUT
    if max_retries is None:
        max_retries = settings.AGENT_LLM_MAX_RETRIES

    extra: dict[str, Any] = {
        "request_timeout": request_timeout,
        "max_retries": max_retries,
    }
    if _accepts_temperature:
        extra["temperature"] = temperature
    # Default to Chat Completions API. langchain-openai auto-routes gpt-5
    # family + reasoning_effort to Azure Responses API, which currently
    # rejects multi-part / tool_call messages with "Unsupported data type".
    # Callers can opt back in by passing use_responses_api=True explicitly.
    extra["use_responses_api"] = (
        False if use_responses_api is None else use_responses_api
    )

    # gpt-5 family supports reasoning_effort. Lightweight tasks (classifier,
    # reflection, planner complexity check) default to "minimal".
    if deployment.startswith("gpt-5") and reasoning_effort:
        extra["reasoning_effort"] = reasoning_effort

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


def build_lightweight_llm(
    *,
    temperature: float = 0,
    max_tokens: int = 512,
    request_timeout: float | None = None,
    use_responses_api: bool | None = None,
) -> BaseChatModel:
    """Build a LangChain chat model for lightweight auxiliary tasks.

    Targets the deployment configured via
    ``AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT``, falling back to the main chat
    deployment. Used by classifier, planner complexity check, reflection,
    compactor — never a tool-calling turn.
    """
    key = (temperature, max_tokens, request_timeout, use_responses_api)
    cached = _LIGHTWEIGHT_LLM_CACHE.get(key)
    if cached is not None:
        return cached
    settings = get_settings()
    llm = _build_chat_llm(
        _resolve_lightweight_deployment(),
        role_label="Lightweight",
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=request_timeout,
        use_responses_api=use_responses_api,
        reasoning_effort=settings.AGENT_LIGHTWEIGHT_REASONING_EFFORT or None,
    )
    _LIGHTWEIGHT_LLM_CACHE[key] = llm
    return llm


def build_synthesis_llm(
    *,
    temperature: float = 0,
    max_tokens: int = 4096,
    request_timeout: float | None = None,
    use_responses_api: bool | None = None,
) -> BaseChatModel:
    """Build a LangChain chat model for post-tool prose synthesis.

    Targets ``AZURE_OPENAI_SYNTHESIS_DEPLOYMENT``, falling back to the
    lightweight deployment and then to the main chat deployment, so existing
    single-knob deployments keep working and leaving every override unset
    runs one deployment everywhere. Set it only to make prose cheaper than
    the tool-decision path — not the other way round.
    """
    key = (temperature, max_tokens, request_timeout, use_responses_api)
    cached = _SYNTHESIS_LLM_CACHE.get(key)
    if cached is not None:
        return cached
    settings = get_settings()
    # Synthesis call can be long (full 4096-token completion). Use the main
    # agent timeout, not the lightweight one, unless caller overrides.
    resolved_timeout = (
        request_timeout
        if request_timeout is not None
        else settings.AGENT_LLM_REQUEST_TIMEOUT
    )
    llm = _build_chat_llm(
        _resolve_synthesis_deployment(),
        role_label="Synthesis",
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=resolved_timeout,
        use_responses_api=use_responses_api,
        # Shares AGENT_LIGHTWEIGHT_REASONING_EFFORT ("minimal") with the
        # lightweight tier on purpose. That coupling used to be a defect —
        # it set the effort for tool-calling turns too — but tool decisions
        # now run on the main deployment, so every caller left here is prose
        # or a short classification, and "minimal" is the right setting for
        # them. Add AGENT_SYNTHESIS_REASONING_EFFORT only if synthesis
        # quality measurably regresses; a knob for a value that should not
        # vary is debt.
        reasoning_effort=settings.AGENT_LIGHTWEIGHT_REASONING_EFFORT or None,
    )
    _SYNTHESIS_LLM_CACHE[key] = llm
    return llm


def get_lightweight_model_name() -> str:
    """Return the configured lightweight model/deployment name."""
    return _resolve_lightweight_deployment()


def get_synthesis_model_name() -> str:
    """Return the configured synthesis model/deployment name."""
    return _resolve_synthesis_deployment()


def validate_llm_config() -> bool:
    """True if an Azure/OpenAI chat endpoint AND api key resolve. Used at
    startup to fail readiness rather than crash individual turns."""
    s = get_settings()
    endpoint = s.AZURE_OPENAI_CHAT_ENDPOINT or s.AZURE_OPENAI_ENDPOINT or ""
    api_key = s.AZURE_OPENAI_CHAT_API_KEY or s.AZURE_OPENAI_API_KEY or ""
    return bool(endpoint and api_key)


# ---------------------------------------------------------------------------
# Main chat LLM construction (moved from graph.py)
# ---------------------------------------------------------------------------

_LLM_CACHE: dict[tuple[str, str], BaseChatModel] = {}


def _build_llm(model_override: str | None = None):
    """Build a LangChain chat model from the existing Azure/OpenAI config.

    ``model_override`` lets a per-request deployment name win over the configured
    default — used to make the agent honor ``request.model`` from the API.

    Clients are cached by ``(endpoint_type, deployment)`` to avoid rebuilding
    the HTTP client on every ``llm_node`` invocation (~30-50 ms each).
    """
    settings = get_settings()

    endpoint = (
        settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT or ""
    )
    api_key = settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY or ""
    api_version = (
        settings.AZURE_OPENAI_CHAT_API_VERSION or settings.AZURE_OPENAI_API_VERSION
    )
    deployment = (
        model_override
        or settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
        or settings.AZURE_OPENAI_DEPLOYMENT_NAME
    )

    if not endpoint or not api_key:
        raise RuntimeError(
            "Azure/OpenAI chat endpoint and API key must be configured. "
            "Set AZURE_OPENAI_CHAT_ENDPOINT + AZURE_OPENAI_CHAT_API_KEY "
            "(or the non-CHAT variants)."
        )

    if not deployment:
        raise RuntimeError(
            "Chat deployment name must be configured. Set "
            "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME (or AZURE_OPENAI_DEPLOYMENT_NAME)."
        )

    endpoint_type = classify_openai_endpoint(endpoint)
    cache_key = (endpoint_type, deployment)
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]

    # All gpt-5 family deployments (gpt-5, gpt-5-mini, gpt-5-nano, etc.)
    # reject custom temperature — Azure returns 400. Drop it for the whole
    # family rather than per-deployment allowlist.
    temperature = None if deployment.startswith("gpt-5") else 0.7

    # gpt-5 family supports reasoning_effort to trade reasoning depth for
    # latency. Defaults to "low" for fast agent loops; raise via settings
    # for harder reasoning tasks. Non-gpt-5 deployments ignore this kwarg.
    reasoning_effort = settings.AGENT_MAIN_REASONING_EFFORT
    is_gpt5_family = deployment.startswith("gpt-5") if deployment else False

    # Force Chat Completions API. langchain-openai auto-routes gpt-5 family
    # with reasoning_effort to the Azure Responses API, which currently rejects
    # the agent's tool_call message history with "Unsupported data type". The
    # Chat Completions path handles tool_calls reliably and supports
    # reasoning_effort on gpt-5 deployments via api-version 2024-10-21+.
    # Bound LLM call wall-clock + cap retries. Prevents the model-router hang
    # observed in LangSmith (traces with end_time=null blocking root 70s+).
    request_timeout = settings.AGENT_LLM_REQUEST_TIMEOUT
    max_retries = settings.AGENT_LLM_MAX_RETRIES

    if endpoint_type == "openai_compatible":
        from langchain_openai import ChatOpenAI

        kwargs: dict = dict(
            model=deployment,
            api_key=api_key,
            base_url=endpoint,
            max_tokens=4096,
            use_responses_api=False,
            request_timeout=request_timeout,
            max_retries=max_retries,
        )
        if temperature is not None:
            kwargs["temperature"] = temperature
        if is_gpt5_family and reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        llm = ChatOpenAI(**kwargs)
    else:
        from langchain_openai import AzureChatOpenAI

        kwargs = dict(
            azure_deployment=deployment,
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            max_tokens=4096,
            use_responses_api=False,
            request_timeout=request_timeout,
            max_retries=max_retries,
        )
        if temperature is not None:
            kwargs["temperature"] = temperature
        if is_gpt5_family and reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        llm = AzureChatOpenAI(**kwargs)

    _LLM_CACHE[cache_key] = llm
    return llm
