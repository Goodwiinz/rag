"""
Text embedding generation service
"""

import time
import logging
from typing import List, Dict, Any, Optional, Union
import numpy as np

# Try to import sentence transformers, fall back gracefully if not available
try:
    from sentence_transformers import SentenceTransformer
    import torch
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None
    torch = None

from ..core.config import settings
from ..models.vector import (
    EmbeddingRequest,
    EmbeddingResponse,
    BatchEmbeddingRequest,
    BatchEmbeddingResponse
)

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using sentence transformers"""

    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL
        self.model = None
        self.device = "cuda" if (torch and torch.cuda.is_available()) else "cpu"
        self.embedding_dimension = None
        self._load_model()

    def _load_model(self):
        """Load the embedding model"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("Sentence transformers not available. Loading simple fallback.")
            self._load_simple_model()
            return

        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            self.embedding_dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded successfully. Dimension: {self.embedding_dimension}")
        except Exception as e:
            logger.error(f"Failed to load embedding model {self.model_name}: {e}")
            # Fallback to a smaller model
            try:
                fallback_model = "sentence-transformers/all-MiniLM-L6-v2"
                logger.info(f"Trying fallback model: {fallback_model}")
                self.model = SentenceTransformer(fallback_model, device=self.device)
                self.model_name = fallback_model
                self.embedding_dimension = self.model.get_sentence_embedding_dimension()
                logger.info(f"Fallback model loaded. Dimension: {self.embedding_dimension}")
            except Exception as fallback_error:
                logger.error(f"Failed to load fallback model: {fallback_error}")
                self._load_simple_model()

    def _load_simple_model(self):
        """Load simple fallback model"""
        try:
            from .embedding_service_simple import SimpleEmbeddingService
            self.simple_service = SimpleEmbeddingService()
            self.embedding_dimension = self.simple_service.get_embedding_dimension()
            self.use_simple_fallback = True
            logger.info(f"Simple embedding service loaded. Dimension: {self.embedding_dimension}")
        except Exception as e:
            logger.error(f"Failed to load simple embedding service: {e}")
            raise

    def generate_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embedding for a single text"""
        start_time = time.time()

        try:
            # Use provided model or default model
            model_to_use = request.model if request.model else self.model_name

            # Check if we should use simple fallback
            if hasattr(self, 'use_simple_fallback') and self.use_simple_fallback:
                # Use simple fallback service
                embedding = self.simple_service.encode([request.text])[0]
                embedding_dimension = self.embedding_dimension
                embedding_list = embedding.tolist()
            else:
                # If different model requested, load it
                if model_to_use != self.model_name:
                    logger.info(f"Loading different model: {model_to_use}")
                    temp_model = SentenceTransformer(model_to_use, device=self.device)
                    embedding = temp_model.encode(request.text, convert_to_tensor=True)
                    embedding_dimension = temp_model.get_sentence_embedding_dimension()
                else:
                    embedding = self.model.encode(request.text, convert_to_tensor=True)
                    embedding_dimension = self.embedding_dimension

                # Convert to list for JSON serialization
                embedding_list = embedding.cpu().numpy().tolist()

            processing_time = time.time() - start_time

            return EmbeddingResponse(
                embedding=embedding_list,
                model=model_to_use,
                dimension=embedding_dimension,
                processing_time=processing_time
            )

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def generate_batch_embeddings(self, request: BatchEmbeddingRequest) -> BatchEmbeddingResponse:
        """Generate embeddings for multiple texts"""
        start_time = time.time()

        try:
            # Use provided model or default model
            model_to_use = request.model if request.model else self.model_name

            # Filter out empty or None texts
            valid_texts = []
            valid_indices = []
            errors = []

            for i, text in enumerate(request.texts):
                if text and text.strip():
                    valid_texts.append(text.strip())
                    valid_indices.append(i)
                else:
                    errors.append({
                        "index": i,
                        "text": text,
                        "error": "Empty or invalid text"
                    })

            if not valid_texts:
                return BatchEmbeddingResponse(
                    embeddings=[],
                    model=model_to_use,
                    dimension=self.embedding_dimension or 384,
                    processing_time=time.time() - start_time,
                    failed_count=len(request.texts),
                    errors=errors
                )

            # If different model requested, load it
            if model_to_use != self.model_name:
                logger.info(f"Loading different model for batch: {model_to_use}")
                temp_model = SentenceTransformer(model_to_use, device=self.device)
                embeddings = temp_model.encode(valid_texts, convert_to_tensor=True)
                embedding_dimension = temp_model.get_sentence_embedding_dimension()
            else:
                embeddings = self.model.encode(valid_texts, convert_to_tensor=True)
                embedding_dimension = self.embedding_dimension

            # Convert to list and restore original order
            embedding_lists = embeddings.cpu().numpy().tolist()
            all_embeddings = [None] * len(request.texts)

            for i, original_index in enumerate(valid_indices):
                all_embeddings[original_index] = embedding_lists[i]

            processing_time = time.time() - start_time

            return BatchEmbeddingResponse(
                embeddings=all_embeddings,
                model=model_to_use,
                dimension=embedding_dimension,
                processing_time=processing_time,
                failed_count=len(errors),
                errors=errors
            )

        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            # Return error response
            return BatchEmbeddingResponse(
                embeddings=[],
                model=request.model or self.model_name,
                dimension=self.embedding_dimension or 384,
                processing_time=time.time() - start_time,
                failed_count=len(request.texts),
                errors=[{"index": i, "error": str(e)} for i in range(len(request.texts))]
            )

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            "model_name": self.model_name,
            "dimension": self.embedding_dimension,
            "device": self.device,
            "max_sequence_length": getattr(self.model, 'max_seq_length', 512),
            "available": self.model is not None
        }

    def test_embedding_quality(self, test_texts: List[str]) -> Dict[str, Any]:
        """Test embedding quality with sample texts"""
        try:
            # Generate embeddings for test texts
            request = BatchEmbeddingRequest(texts=test_texts)
            response = self.generate_batch_embeddings(request)

            if response.failed_count > 0:
                return {
                    "success": False,
                    "error": f"Failed to embed {response.failed_count} texts",
                    "errors": response.errors
                }

            # Calculate basic quality metrics
            embeddings = np.array([emb for emb in response.embeddings if emb is not None])

            # Calculate pairwise similarities
            from sklearn.metrics.pairwise import cosine_similarity
            similarities = cosine_similarity(embeddings)

            # Average similarity (excluding self-similarity)
            avg_similarity = np.mean(similarities[np.triu_indices_from(similarities, k=1)])

            # Embedding statistics
            embedding_mean = np.mean(embeddings)
            embedding_std = np.std(embeddings)
            embedding_norm = np.linalg.norm(embeddings, axis=1).mean()

            return {
                "success": True,
                "model": response.model,
                "dimension": response.dimension,
                "processing_time": response.processing_time,
                "texts_count": len(test_texts),
                "avg_pairwise_similarity": float(avg_similarity),
                "embedding_stats": {
                    "mean": float(embedding_mean),
                    "std": float(embedding_std),
                    "avg_norm": float(embedding_norm)
                },
                "quality_score": min(1.0, max(0.0, 1.0 - avg_similarity))  # Lower similarity is better for diversity
            }

        except Exception as e:
            logger.error(f"Error testing embedding quality: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into chunks for embedding"""
        if not text or not text.strip():
            return []

        # Simple word-based chunking
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk.strip())

        return chunks

    def generate_document_embeddings(
        self,
        document_id: str,
        text: str,
        metadata: Dict[str, Any],
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[Dict[str, Any]]:
        """Generate embeddings for a full document by chunking"""
        try:
            # Chunk the text
            chunks = self.chunk_text(text, chunk_size, overlap)

            if not chunks:
                return []

            # Generate embeddings for all chunks
            chunk_texts = [chunk for chunk in chunks]
            request = BatchEmbeddingRequest(texts=chunk_texts)
            response = self.generate_batch_embeddings(request)

            # Combine embeddings with metadata
            document_embeddings = []
            for i, (chunk, embedding) in enumerate(zip(chunks, response.embeddings)):
                if embedding is not None:
                    chunk_metadata = metadata.copy()
                    chunk_metadata.update({
                        "document_id": document_id,
                        "chunk_index": i,
                        "chunk_text": chunk,
                        "total_chunks": len(chunks)
                    })

                    document_embeddings.append({
                        "id": f"{document_id}_chunk_{i}",
                        "embedding": embedding,
                        "text": chunk,
                        "metadata": chunk_metadata
                    })

            return document_embeddings

        except Exception as e:
            logger.error(f"Error generating document embeddings: {e}")
            return []


# Singleton instance
embedding_service = EmbeddingService()