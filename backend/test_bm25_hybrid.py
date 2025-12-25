#!/usr/bin/env python3
"""
Test BM25 Hybrid Search

Tests the BM25 service and hybrid search functionality.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.bm25_service import bm25_service, SparseVector


def test_bm25_tokenization():
    """Test BM25 tokenization"""
    print("=" * 60)
    print("Testing BM25 Tokenization")
    print("=" * 60)
    
    text = "Machine learning algorithms are used in healthcare for disease detection"
    tokens = bm25_service.tokenize(text)
    
    print(f"Input: {text}")
    print(f"Tokens: {tokens}")
    print(f"Token count: {len(tokens)}")
    
    assert len(tokens) > 0, "Should have tokens"
    assert "machine" in tokens, "Should contain 'machine'"
    assert "are" not in tokens, "Should filter stopwords"
    print("✅ Tokenization test passed!")


def test_bm25_encoding():
    """Test BM25 sparse vector encoding"""
    print("\n" + "=" * 60)
    print("Testing BM25 Encoding")
    print("=" * 60)
    
    # Test document encoding
    doc = "Deep learning models improve medical imaging diagnosis accuracy"
    sparse = bm25_service.encode(doc)
    
    print(f"Document: {doc}")
    print(f"Sparse vector indices: {sparse.indices[:5]}...")
    print(f"Sparse vector values: {[f'{v:.3f}' for v in sparse.values[:5]]}...")
    print(f"Non-zero entries: {len(sparse.indices)}")
    
    assert len(sparse.indices) > 0, "Should have non-zero entries"
    assert len(sparse.indices) == len(sparse.values), "Indices and values should match"
    print("✅ Encoding test passed!")


def test_bm25_relevance():
    """Test that BM25 correctly scores relevant vs irrelevant documents"""
    print("\n" + "=" * 60)
    print("Testing BM25 Relevance Scoring")
    print("=" * 60)
    
    query = "machine learning healthcare applications"
    
    # Relevant documents
    relevant_docs = [
        "Machine learning algorithms are transforming healthcare by enabling early disease detection",
        "Deep learning in medical imaging helps doctors diagnose diseases more accurately",
        "Healthcare applications of machine learning include drug discovery and patient monitoring"
    ]
    
    # Irrelevant documents
    irrelevant_docs = [
        "The stock market showed significant volatility in the fourth quarter",
        "World Cup soccer tournament attracted millions of viewers",
        "New smartphone models feature improved camera technology"
    ]
    
    # Update corpus statistics
    all_docs = relevant_docs + irrelevant_docs
    bm25_service.update_statistics(all_docs)
    
    # Encode query
    query_sparse = bm25_service.encode(query, is_query=True)
    query_indices = set(query_sparse.indices)
    
    print(f"Query: {query}")
    print(f"Query sparse indices: {len(query_indices)} unique terms")
    
    def compute_bm25_similarity(doc: str) -> float:
        doc_sparse = bm25_service.encode(doc)
        score = 0.0
        for idx, val in zip(doc_sparse.indices, doc_sparse.values):
            if idx in query_indices:
                score += val
        return score
    
    print("\n📊 Relevance Scores:")
    print("-" * 50)
    
    relevant_scores = []
    for doc in relevant_docs:
        score = compute_bm25_similarity(doc)
        relevant_scores.append(score)
        print(f"✅ Relevant: {score:.3f} - {doc[:50]}...")
    
    irrelevant_scores = []
    for doc in irrelevant_docs:
        score = compute_bm25_similarity(doc)
        irrelevant_scores.append(score)
        print(f"❌ Irrelevant: {score:.3f} - {doc[:50]}...")
    
    avg_relevant = sum(relevant_scores) / len(relevant_scores)
    avg_irrelevant = sum(irrelevant_scores) / len(irrelevant_scores)
    
    print(f"\n📈 Average relevant score: {avg_relevant:.3f}")
    print(f"📉 Average irrelevant score: {avg_irrelevant:.3f}")
    
    assert avg_relevant > avg_irrelevant, "Relevant docs should score higher"
    print("\n✅ Relevance test passed! BM25 correctly ranks relevant documents higher.")


def test_bm25_combined_ranking():
    """Test how BM25 improves ranking when combined with dense scores"""
    print("\n" + "=" * 60)
    print("Testing Combined Dense + BM25 Ranking")
    print("=" * 60)
    
    query = "neural networks image classification"
    
    # Simulate dense search results (score, text)
    # Some results might have high dense score but low keyword overlap
    dense_results = [
        (0.85, "Transfer learning approaches for computer vision tasks"),
        (0.82, "Neural networks are powerful tools for image classification tasks"),
        (0.78, "Deep convolutional networks achieve state-of-the-art results"),
        (0.75, "Image recognition using neural network architectures for classification"),
        (0.70, "Machine perception and visual understanding systems")
    ]
    
    # Update statistics
    bm25_service.update_statistics([text for _, text in dense_results])
    
    # Get query sparse vector
    query_sparse = bm25_service.encode(query, is_query=True)
    query_indices = set(query_sparse.indices)
    
    print(f"Query: {query}")
    print("\nRanking with combined scores (70% dense + 30% BM25):")
    print("-" * 60)
    
    combined_results = []
    for dense_score, text in dense_results:
        # Compute BM25 score
        doc_sparse = bm25_service.encode(text)
        bm25_score = 0.0
        for idx, val in zip(doc_sparse.indices, doc_sparse.values):
            if idx in query_indices:
                bm25_score += val
        
        # Normalize
        bm25_norm = min(bm25_score / max(len(query_indices), 1), 1.0)
        
        # Combine
        combined = 0.7 * dense_score + 0.3 * bm25_norm
        combined_results.append((combined, dense_score, bm25_norm, text))
    
    # Sort by combined score
    combined_results.sort(key=lambda x: x[0], reverse=True)
    
    print(f"{'Rank':<5} {'Combined':<10} {'Dense':<10} {'BM25':<10} {'Text'}")
    print("-" * 80)
    for i, (combined, dense, bm25, text) in enumerate(combined_results, 1):
        print(f"{i:<5} {combined:.3f}      {dense:.3f}      {bm25:.3f}      {text[:40]}...")
    
    # The result with "neural networks" and "image classification" should rank high
    top_text = combined_results[0][3]
    assert "neural" in top_text.lower() or "image" in top_text.lower(), \
        "Top result should contain query terms"
    
    print("\n✅ Combined ranking test passed!")


if __name__ == "__main__":
    print("🧪 BM25 Hybrid Search Test Suite\n")
    
    test_bm25_tokenization()
    test_bm25_encoding()
    test_bm25_relevance()
    test_bm25_combined_ranking()
    
    print("\n" + "=" * 60)
    print("🎉 All BM25 tests passed!")
    print("=" * 60)
