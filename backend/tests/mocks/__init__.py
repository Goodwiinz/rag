"""
Test Mocks Package

Provides mock implementations for external services and AI clients.
"""

from tests.mocks.ai_client import MockAIClient, MockEmbeddingClient

__all__ = [
    "MockAIClient",
    "MockEmbeddingClient",
]
