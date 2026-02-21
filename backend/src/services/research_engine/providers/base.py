"""Base classes and data structures for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""

    provider_type: str
    model_id: str
    model_version: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMRequest:
    """Request payload for LLM completion."""

    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.0
    seed: Optional[int] = 42
    max_tokens: int = 2048
    response_format: Optional[Dict[str, Any]] = None


@dataclass
class LLMResponse:
    """Response from an LLM completion."""

    content: str
    model_id: str
    model_version: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    temperature: float = 0.0
    seed: Optional[int] = None

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.input_tokens + self.output_tokens


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to the LLM."""
        ...

    @abstractmethod
    async def is_model_available(self) -> bool:
        """Check if the configured model is available."""
        ...
