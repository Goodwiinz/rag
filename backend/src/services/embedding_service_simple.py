#!/usr/bin/env python3
"""
Simple embedding service using deterministic hash functions
Fallback when sentence-transformers is not available
"""

import hashlib
import numpy as np
from typing import List, Optional, Union
import logging

logger = logging.getLogger(__name__)


class SimpleEmbeddingService:
    """
    Simple embedding service using deterministic hash functions
    Provides consistent embeddings without requiring external dependencies
    """

    def __init__(self, embedding_dim: int = 384):
        """
        Initialize the simple embedding service

        Args:
            embedding_dim: Dimension of the embedding vectors
        """
        self.embedding_dim = embedding_dim
        logger.info(f"Initialized SimpleEmbeddingService with {embedding_dim} dimensions")

    def encode(self, texts: Union[str, List[str]], batch_size: Optional[int] = None) -> np.ndarray:
        """
        Generate embeddings for text using deterministic hash functions

        Args:
            texts: Single text or list of texts to encode
            batch_size: Batch size for processing (ignored in simple implementation)

        Returns:
            numpy array of embeddings
        """
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return np.array([])

        embeddings = []
        for text in texts:
            embedding = self._text_to_embedding(text)
            embeddings.append(embedding)

        return np.array(embeddings)

    def _text_to_embedding(self, text: str) -> List[float]:
        """
        Convert text to a deterministic embedding vector using hash functions

        Args:
            text: Input text

        Returns:
            List of float values representing the embedding
        """
        # Use SHA256 hash for deterministic but pseudo-random embeddings
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()

        # Convert hash to numerical values
        hash_bytes = bytes.fromhex(text_hash)

        # Generate embedding values
        embedding = []
        for i in range(self.embedding_dim):
            # Use different parts of the hash for different dimensions
            byte_index = (i * 3) % len(hash_bytes)
            next_byte_index = (byte_index + 1) % len(hash_bytes)

            # Combine bytes to create a value between 0 and 1
            combined = (hash_bytes[byte_index] << 8) | hash_bytes[next_byte_index]
            normalized_value = combined / 65535.0  # Normalize to [0, 1]

            # Scale to [-1, 1] range
            scaled_value = (normalized_value * 2) - 1
            embedding.append(scaled_value)

        return embedding

    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score
        """
        # Ensure vectors are numpy arrays
        embedding1 = np.array(embedding1)
        embedding2 = np.array(embedding2)

        # Calculate cosine similarity
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def normalize_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Normalize embeddings to unit length

        Args:
            embeddings: Array of embeddings to normalize

        Returns:
            Normalized embeddings
        """
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        return embeddings / norms

    def get_device(self) -> str:
        """
        Get the device being used (always 'cpu' for simple implementation)

        Returns:
            Device string
        """
        return "cpu"

    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of the embedding vectors

        Returns:
            Embedding dimension
        """
        return self.embedding_dim


# Global instance
simple_embedding_service = SimpleEmbeddingService()