"""
AI Client Protocols

Defines Protocol classes for AI services, enabling dependency injection
and testability through duck typing.

Usage:
    class MyAIClient:
        async def complete(self, messages, **kwargs) -> CompletionResponse:
            # Implementation
            pass
        
        def is_available(self) -> bool:
            return True

    # The class automatically satisfies AIClient protocol
    client: AIClient = MyAIClient()
"""

from dataclasses import dataclass, field
from typing import Protocol, List, Optional, Dict, Any, runtime_checkable


@dataclass
class CompletionResponse:
    """Response from an AI completion request."""
    
    content: str
    """The generated text content."""
    
    model: str
    """The model used for generation."""
    
    usage: Dict[str, int] = field(default_factory=dict)
    """Token usage statistics (prompt_tokens, completion_tokens, total_tokens)."""
    
    finish_reason: str = "stop"
    """Reason the generation stopped (stop, length, content_filter, etc.)."""
    
    raw_response: Optional[Any] = None
    """The raw response object from the API (for debugging)."""
    
    def __post_init__(self):
        """Validate response data."""
        if not self.content:
            self.content = ""
        if not self.usage:
            self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


@dataclass
class EmbeddingResponse:
    """Response from an embedding request."""
    
    embeddings: List[List[float]]
    """List of embedding vectors."""
    
    model: str
    """The model used for embedding generation."""
    
    usage: Dict[str, int] = field(default_factory=dict)
    """Token usage statistics."""
    
    dimensions: int = 0
    """Embedding dimension size."""
    
    def __post_init__(self):
        """Validate and set dimensions."""
        if self.embeddings and len(self.embeddings) > 0:
            self.dimensions = len(self.embeddings[0])


@runtime_checkable
class AIClient(Protocol):
    """
    Protocol for AI completion clients.
    
    Implementations should provide async completion generation
    and availability checking.
    """
    
    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 500,
        **kwargs: Any
    ) -> CompletionResponse:
        """
        Generate a completion from messages.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys.
            model: Optional model override.
            temperature: Sampling temperature (0.0 = deterministic).
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional provider-specific parameters.
            
        Returns:
            CompletionResponse with generated content.
            
        Raises:
            Exception: On API errors or unavailability.
        """
        ...
    
    def is_available(self) -> bool:
        """
        Check if the client is properly configured and available.
        
        Returns:
            True if the client can make requests, False otherwise.
        """
        ...


@runtime_checkable
class EmbeddingClient(Protocol):
    """
    Protocol for embedding generation clients.
    
    Implementations should provide async embedding generation.
    """
    
    async def embed(self, texts: List[str]) -> EmbeddingResponse:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed.
            
        Returns:
            EmbeddingResponse with embedding vectors.
        """
        ...
    
    async def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query text.
        
        This is optimized for single queries (e.g., search queries).
        
        Args:
            text: Text to embed.
            
        Returns:
            Single embedding vector as a list of floats.
        """
        ...
    
    def is_available(self) -> bool:
        """
        Check if the client is properly configured and available.
        
        Returns:
            True if the client can make requests, False otherwise.
        """
        ...


@runtime_checkable
class StreamingAIClient(Protocol):
    """
    Protocol for AI clients that support streaming responses.
    
    Extends AIClient with streaming capability.
    """
    
    async def complete_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 500,
        **kwargs: Any
    ):
        """
        Generate a streaming completion from messages.
        
        Args:
            messages: List of message dictionaries.
            model: Optional model override.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional parameters.
            
        Yields:
            String chunks as they are generated.
        """
        ...
    
    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 500,
        **kwargs: Any
    ) -> CompletionResponse:
        """Non-streaming completion (required for AIClient compatibility)."""
        ...
    
    def is_available(self) -> bool:
        """Check if the client is available."""
        ...
