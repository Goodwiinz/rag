"""Ollama LLM provider (local models via HTTP API)."""

from typing import Any, Dict, List

import httpx
import structlog

from src.services.research_engine.providers.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderConfig,
)

logger = structlog.get_logger(__name__)

_DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(LLMProvider):
    """LLM provider for locally-hosted Ollama models."""

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self.base_url = config.base_url or _DEFAULT_BASE_URL

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to the Ollama HTTP API."""
        messages: List[Dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        options: Dict[str, Any] = {
            "temperature": request.temperature,
            "num_predict": request.max_tokens,
        }
        if request.seed is not None:
            options["seed"] = request.seed

        payload: Dict[str, Any] = {
            "model": self.config.model_id,
            "messages": messages,
            "stream": False,
            "options": options,
        }

        logger.debug(
            "ollama_completion_request",
            model=self.config.model_id,
            base_url=self.base_url,
            temperature=request.temperature,
        )

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()

        return LLMResponse(
            content=data["message"]["content"],
            model_id=data.get("model", self.config.model_id),
            model_version=self.config.model_version,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            temperature=request.temperature,
            seed=request.seed,
        )

    async def is_model_available(self) -> bool:
        """Check if the model is available in the local Ollama instance."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()

            model_names = [m.get("name", "") for m in data.get("models", [])]
            return self.config.model_id in model_names
        except (httpx.HTTPError, Exception):
            logger.warning(
                "ollama_availability_check_failed",
                base_url=self.base_url,
                model_id=self.config.model_id,
            )
            return False
