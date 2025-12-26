#!/usr/bin/env python3
"""Test Azure OpenAI embedding configuration"""
import sys
import asyncio
sys.path.insert(0, 'backend')

from src.models.vector import BatchEmbeddingRequest
from src.services.embedding_service import embedding_service
from src.services.azure_openai_service import azure_openai_service

async def test():
    print("=== Testing Embedding Configuration ===")
    print(f"Embedding service provider: {embedding_service.embedding_provider}")
    print(f"Embedding dimension: {embedding_service.embedding_dimension}")
    print(f"Azure embedding available: {azure_openai_service.is_embedding_available()}")
    
    # Test with provider=azure_openai
    request = BatchEmbeddingRequest(texts=['Test text for embedding'], provider='azure_openai')
    print(f"\nRequest provider: {request.provider}")
    
    # Generate embedding
    try:
        response = await embedding_service.generate_batch_embeddings(request)
        print(f"Response dimension: {response.dimension}")
        if response.embeddings and response.embeddings[0]:
            print(f"Actual embedding length: {len(response.embeddings[0])}")
        else:
            print(f"Embeddings: {response.embeddings}")
            print(f"Errors: {getattr(response, 'errors', 'N/A')}")
        print(f"Provider used: {getattr(response, 'provider', 'unknown')}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
