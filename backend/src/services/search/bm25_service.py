"""
BM25 Sparse Vector Service

Generates BM25-based sparse vectors for hybrid search in Qdrant.
Combines with dense vectors from Azure OpenAI embeddings for improved retrieval.
"""

import hashlib
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SparseVector:
    """Sparse vector representation for BM25"""

    indices: List[int]
    values: List[float]

    def to_dict(self) -> Dict:
        """Convert to dict for Qdrant API"""
        return {"indices": self.indices, "values": self.values}


class BM25Service:
    """
    BM25-based sparse vector generator for hybrid search.

    Uses sub-word tokenization and hashing to create sparse vectors
    that can be stored alongside dense vectors in Qdrant.
    """

    # BM25 hyperparameters
    K1 = 1.5  # Term frequency saturation
    B = 0.75  # Document length normalization

    # Vocabulary size (hash space for sparse vectors)
    VOCAB_SIZE = 30000

    # Stopwords to filter out
    STOPWORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "he",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "were",
        "will",
        "with",
        "this",
        "but",
        "they",
        "have",
        "had",
        "what",
        "when",
        "where",
        "who",
        "which",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "can",
        "just",
        "should",
        "now",
        "would",
        "could",
        "may",
        "might",
        "must",
        "shall",
        "need",
        "do",
        "does",
        "did",
    }

    def __init__(self):
        self.avg_doc_length = 200.0  # Will be updated during indexing
        self.doc_count = 0
        self.idf_cache: Dict[int, float] = {}  # term_hash -> idf
        self.doc_freqs: Dict[int, int] = {}  # term_hash -> doc_frequency

        logger.info("BM25 service initialized")

    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into terms.
        Uses lowercase, removes punctuation, filters stopwords.
        """
        # Lowercase and extract words
        text = text.lower()
        # Keep alphanumeric and spaces
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        # Split on whitespace
        tokens = text.split()
        # Filter stopwords and short tokens
        tokens = [t for t in tokens if t not in self.STOPWORDS and len(t) > 1]
        return tokens

    def _hash_token(self, token: str) -> int:
        """Hash token to vocabulary index"""
        return int(hashlib.md5(token.encode(), usedforsecurity=False).hexdigest(), 16) % self.VOCAB_SIZE

    def _compute_tf(self, term_count: int, doc_length: int) -> float:
        """Compute BM25 term frequency component"""
        numerator = term_count * (self.K1 + 1)
        denominator = term_count + self.K1 * (
            1 - self.B + self.B * doc_length / self.avg_doc_length
        )
        return numerator / max(denominator, 1e-6)

    def _compute_idf(self, doc_freq: int) -> float:
        """Compute IDF (Inverse Document Frequency)"""
        if self.doc_count == 0:
            return 1.0
        return math.log((self.doc_count - doc_freq + 0.5) / (doc_freq + 0.5) + 1)

    def update_statistics(self, documents: List[str]):
        """
        Update corpus statistics for IDF calculation.
        Call this during indexing to build proper IDF values.
        """
        total_length = 0

        for doc in documents:
            tokens = self.tokenize(doc)
            total_length += len(tokens)
            self.doc_count += 1

            # Count unique terms per document
            unique_terms = set(self._hash_token(t) for t in tokens)
            for term_hash in unique_terms:
                self.doc_freqs[term_hash] = self.doc_freqs.get(term_hash, 0) + 1

        # Update average document length
        if self.doc_count > 0:
            self.avg_doc_length = total_length / self.doc_count

        # Update IDF cache
        for term_hash, doc_freq in self.doc_freqs.items():
            self.idf_cache[term_hash] = self._compute_idf(doc_freq)

        logger.info(
            f"Updated BM25 stats: {self.doc_count} docs, avg_len={self.avg_doc_length:.1f}"
        )

    def encode(self, text: str, is_query: bool = False) -> SparseVector:
        """
        Encode text to sparse BM25 vector.

        Args:
            text: Input text to encode
            is_query: If True, uses query-specific weighting (no length normalization)

        Returns:
            SparseVector with indices and values
        """
        tokens = self.tokenize(text)
        if not tokens:
            return SparseVector(indices=[], values=[])

        # Count term frequencies
        term_counts = Counter(self._hash_token(t) for t in tokens)
        doc_length = len(tokens)

        indices = []
        values = []

        for term_hash, count in sorted(term_counts.items()):
            # Get IDF (use default if term not in corpus)
            idf = self.idf_cache.get(term_hash, 1.0)

            if is_query:
                # For queries, just use term frequency * IDF
                weight = count * idf
            else:
                # For documents, use full BM25 formula
                tf = self._compute_tf(count, doc_length)
                weight = tf * idf

            if weight > 0:
                indices.append(term_hash)
                values.append(weight)

        return SparseVector(indices=indices, values=values)

    def encode_batch(
        self, texts: List[str], is_query: bool = False
    ) -> List[SparseVector]:
        """Encode multiple texts to sparse vectors"""
        return [self.encode(text, is_query) for text in texts]

    def get_hybrid_weight_recommendation(self) -> Dict[str, float]:
        """
        Returns recommended weights for hybrid search.
        Based on typical RAG system performance.
        """
        return {
            "dense_weight": 0.7,  # Semantic similarity (embeddings)
            "sparse_weight": 0.3,  # Keyword matching (BM25)
        }


# Global service instance
bm25_service = BM25Service()
