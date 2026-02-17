"""OpenAI LLM provider."""

from typing import Any, Dict, List

import structlog

from src.services.research_engine.providers.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderConfig,
)

try:
    import openai
except ImportError:
    openai = None  # type: ignore[assignment]

logger = structlog.get_logger(__name__)


class OpenAIProvider(LLMProvider):
    """LLM provider for OpenAI models."""

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        if openai is not None and config.api_key:
            self.client = openai.AsyncOpenAI(api_key=config.api_key)
        else:
            self.client = None  # type: ignore[assignment]

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to the OpenAI API."""
        if self.client is None:
            raise RuntimeError(
                "OpenAI client not initialized. "
                "Ensure the 'openai' package is installed and an API key is set."
            )

        messages: List[Dict[str, Any]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        kwargs: Dict[str, Any] = {
            "model": self.config.model_id,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if request.seed is not None:
            kwargs["seed"] = request.seed

        if request.response_format is not None:
            kwargs["response_format"] = request.response_format

        logger.debug(
            "openai_completion_request",
            model=self.config.model_id,
            temperature=request.temperature,
            seed=request.seed,
        )

        response = await self.client.chat.completions.create(**kwargs)

        return LLMResponse(
            content=response.choices[0].message.content,
            model_id=response.model,
            model_version=self.config.model_version,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            temperature=request.temperature,
            seed=request.seed,
        )

    async def is_model_available(self) -> bool:
        """Check availability by verifying an API key is configured."""
        return self.config.api_key is not None
