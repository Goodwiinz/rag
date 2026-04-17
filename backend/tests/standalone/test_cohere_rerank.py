#!/usr/bin/env python3
"""
Test script for Cohere Reranking Service

Tests the Azure AI Cohere rerank API integration.
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variables for testing
os.environ['COHERE_RERANK_ENDPOINT'] = os.environ.get('COHERE_RERANK_ENDPOINT', 'https://goodwiinzapi.services.ai.azure.com/providers/cohere/v2/rerank')
os.environ['COHERE_RERANK_API_KEY'] = os.environ.get('COHERE_RERANK_API_KEY', '')
os.environ['COHERE_RERANK_MODEL'] = os.environ.get('COHERE_RERANK_MODEL', 'Cohere-rerank-v4.0-pro')


async def test_cohere_rerank():
    """Test the Cohere reranking service"""
    from src.services.search.cohere_rerank_service import CohereRerankService
    
    print("=" * 60)
    print("Testing Cohere Reranking Service")
    print("=" * 60)
    
    # Create service instance
    service = CohereRerankService()
    
    print(f"\n✅ Service enabled: {service.is_enabled}")
    print(f"📍 Endpoint: {service.endpoint}")
    print(f"🤖 Model: {service.model}")
    
    if not service.is_enabled:
        print("\n❌ Service is not enabled. Check your environment variables.")
        return False
    
    # Test documents
    query = "What are the applications of machine learning in healthcare?"
    
    documents = [
        {
            "id": "doc1",
            "content": "Machine learning algorithms are revolutionizing healthcare by enabling early disease detection and personalized treatment plans."
        },
        {
            "id": "doc2", 
            "content": "The stock market experienced significant volatility due to changing economic policies and global uncertainty."
        },
        {
            "id": "doc3",
            "content": "Deep learning models have been successfully applied to medical imaging, helping radiologists identify tumors with high accuracy."
        },
        {
            "id": "doc4",
            "content": "Natural language processing is being used to analyze electronic health records and extract valuable patient information."
        },
        {
            "id": "doc5",
            "content": "Quantum computing represents the next frontier in computational power for complex problem solving."
        }
    ]
    
    print(f"\n📝 Query: {query}")
    print(f"📄 Documents: {len(documents)}")
    
    # Test reranking
    print("\n🔄 Calling Cohere rerank API...")
    
    try:
        results = await service.rerank(query, documents, top_n=5)
        
        print("\n📊 Reranking Results:")
        print("-" * 50)
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. Document: {result.document_id}")
            print(f"   Relevance Score: {result.relevance_score:.4f}")
            print(f"   Original Score: {result.original_score:.4f}")
            
            # Find the document content
            doc = next((d for d in documents if d['id'] == result.document_id), None)
            if doc:
                print(f"   Content: {doc['content'][:100]}...")
        
        print("\n" + "=" * 60)
        print("✅ Cohere reranking test PASSED!")
        print("=" * 60)
        
        # Verify expected order (healthcare docs should rank higher)
        expected_high_rank = ['doc1', 'doc3', 'doc4']
        top_3_ids = [r.document_id for r in results[:3]]
        
        matches = sum(1 for doc_id in top_3_ids if doc_id in expected_high_rank)
        print(f"\n🎯 Precision check: {matches}/3 healthcare-related docs in top 3")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during reranking: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_cohere_rerank())
    sys.exit(0 if success else 1)
