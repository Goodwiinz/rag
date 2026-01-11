"""
Mock AI Client for Testing

Provides a configurable mock AI client that:
- Records all calls for assertion
- Returns configurable responses
- Supports side effects (exceptions, delays)
- Implements AIClient protocol

Usage:
    mock = MockAIClient()
    mock.set_responses(['{"score": 0.8, "reasoning": "Good", "confidence": 0.9}'])
    
    result = await mock.complete([{"role": "user", "content": "test"}])
    assert mock.call_count == 1
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Union
import numpy as np

from src.core.ai.protocols import CompletionResponse, EmbeddingResponse


@dataclass
class MockCall:
    """Record of a mock call."""
    messages: List[Dict[str, str]]
    model: Optional[str]
    kwargs: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0)


class MockAIClient:
    """
    Mock AI client for testing.
    
    Supports:
    - Configurable response sequences
    - Side effects (exceptions)
    - Call recording and assertion helpers
    - Latency simulation
    """
    
    def __init__(self):
        self.calls: List[MockCall] = []
        self._responses: List[str] = []
        self._response_idx = 0
        self._side_effect: Optional[Callable] = None
        self._default_response = '{"score": 0.8, "reasoning": "Default mock response", "confidence": 0.9}'
        self._latency_ms: float = 0
        self._available: bool = True
    
    def set_responses(self, responses: List[str]) -> "MockAIClient":
        """
        Set sequence of responses to return.
        
        Responses cycle when exhausted.
        
        Args:
            responses: List of response strings.
            
        Returns:
            Self for chaining.
        """
        self._responses = responses
        self._response_idx = 0
        return self
    
    def set_single_response(self, response: str) -> "MockAIClient":
        """
        Set a single response to always return.
        
        Args:
            response: Response string.
            
        Returns:
            Self for chaining.
        """
        self._responses = [response]
        self._response_idx = 0
        return self
    
    def set_side_effect(self, effect: Union[Exception, Callable]) -> "MockAIClient":
        """
        Set a side effect for the next call.
        
        Args:
            effect: Exception to raise or callable to execute.
            
        Returns:
            Self for chaining.
        """
        if isinstance(effect, Exception):
            self._side_effect = lambda: (_ for _ in ()).throw(effect)
        else:
            self._side_effect = effect
        return self
    
    def set_latency(self, latency_ms: float) -> "MockAIClient":
        """
        Set simulated latency for calls.
        
        Args:
            latency_ms: Latency in milliseconds.
            
        Returns:
            Self for chaining.
        """
        self._latency_ms = latency_ms
        return self
    
    def set_available(self, available: bool) -> "MockAIClient":
        """
        Set availability status.
        
        Args:
            available: Whether client is available.
            
        Returns:
            Self for chaining.
        """
        self._available = available
        return self
    
    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 500,
        **kwargs: Any
    ) -> CompletionResponse:
        """
        Generate a mock completion.
        
        Records the call and returns configured response.
        """
        # Record the call
        self.calls.append(MockCall(
            messages=messages,
            model=model,
            kwargs={"temperature": temperature, "max_tokens": max_tokens, **kwargs}
        ))
        
        # Simulate latency
        if self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000)
        
        # Handle side effect
        if self._side_effect:
            effect = self._side_effect
            self._side_effect = None  # Clear after use
            
            if callable(effect):
                try:
                    result = effect()
                    if isinstance(result, CompletionResponse):
                        return result
                except Exception:
                    raise
        
        # Get response
        if self._responses:
            content = self._responses[self._response_idx % len(self._responses)]
            self._response_idx += 1
        else:
            content = self._default_response
        
        return CompletionResponse(
            content=content,
            model=model or "mock-model",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            finish_reason="stop"
        )
    
    def is_available(self) -> bool:
        """Check if mock client is available."""
        return self._available
    
    # ========================================================================
    # Call Recording and Assertions
    # ========================================================================
    
    @property
    def call_count(self) -> int:
        """Number of calls made."""
        return len(self.calls)
    
    def get_last_call(self) -> Optional[MockCall]:
        """Get the most recent call."""
        return self.calls[-1] if self.calls else None
    
    def get_all_prompts(self) -> List[str]:
        """Get all prompts from all calls."""
        prompts = []
        for call in self.calls:
            for message in call.messages:
                if message.get("role") == "user":
                    prompts.append(message.get("content", ""))
        return prompts
    
    def reset(self) -> "MockAIClient":
        """Reset call history and response index."""
        self.calls = []
        self._response_idx = 0
        self._side_effect = None
        return self
    
    def assert_called(self) -> None:
        """Assert that at least one call was made."""
        assert self.call_count > 0, "Expected at least one call, but none were made"
    
    def assert_called_once(self) -> None:
        """Assert that exactly one call was made."""
        assert self.call_count == 1, f"Expected exactly one call, but {self.call_count} were made"
    
    def assert_called_times(self, n: int) -> None:
        """Assert that exactly n calls were made."""
        assert self.call_count == n, f"Expected {n} calls, but {self.call_count} were made"
    
    def assert_prompt_contains(self, substring: str) -> None:
        """Assert that at least one prompt contains the substring."""
        prompts = self.get_all_prompts()
        for prompt in prompts:
            if substring in prompt:
                return
        raise AssertionError(f"No prompt contained '{substring}'.\nPrompts: {prompts}")
    
    def assert_last_prompt_contains(self, substring: str) -> None:
        """Assert that the last prompt contains the substring."""
        last_call = self.get_last_call()
        assert last_call is not None, "No calls were made"
        
        for message in last_call.messages:
            if message.get("role") == "user" and substring in message.get("content", ""):
                return
        
        raise AssertionError(f"Last prompt did not contain '{substring}'")


class MockEmbeddingClient:
    """
    Mock embedding client for testing.
    
    Generates deterministic embeddings based on text hash.
    """
    
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.calls: List[List[str]] = []
        self._available: bool = True
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate deterministic embedding from text."""
        np.random.seed(hash(text) % 2**32)
        return np.random.rand(self.dimension).tolist()
    
    async def embed(self, texts: List[str]) -> EmbeddingResponse:
        """Generate embeddings for texts."""
        self.calls.append(texts)
        embeddings = [self._generate_embedding(text) for text in texts]
        
        return EmbeddingResponse(
            embeddings=embeddings,
            model="mock-embedding-model",
            usage={"prompt_tokens": sum(len(t.split()) for t in texts)},
            dimensions=self.dimension
        )
    
    async def embed_query(self, text: str) -> List[float]:
        """Generate embedding for single query."""
        self.calls.append([text])
        return self._generate_embedding(text)
    
    def is_available(self) -> bool:
        """Check if mock client is available."""
        return self._available
    
    @property
    def call_count(self) -> int:
        """Number of embed calls made."""
        return len(self.calls)
    
    def reset(self) -> "MockEmbeddingClient":
        """Reset call history."""
        self.calls = []
        return self
