"""
AI Client Abstraction Layer

This module provides protocol definitions and implementations for AI services,
enabling dependency injection and testability.

Usage:
    from src.core.ai import AIClient, EmbeddingClient, CompletionResponse
"""

from src.core.ai.protocols import AIClient, EmbeddingClient, CompletionResponse

__all__ = [
    "AIClient",
    "EmbeddingClient", 
    "CompletionResponse",
]
