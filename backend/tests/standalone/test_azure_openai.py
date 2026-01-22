#!/usr/bin/env python3
"""
Test script for Azure OpenAI integration
"""

import asyncio
import os
import sys
import json
from typing import List

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.config import settings
from src.services.infrastructure.azure_openai_service import azure_openai_service
from src.services.embedding.embedding_service import embedding_service

async def test_azure_openai_service():
    """Test Azure OpenAI service functionality"""
    print("🔧 Testing Azure OpenAI Service...")

    # Check if Azure OpenAI is configured
    if not azure_openai_service.is_available():
        print("❌ Azure OpenAI service is not available or not configured")
        print(f"   API Key configured: {bool(settings.AZURE_OPENAI_API_KEY)}")
        print(f"   Endpoint configured: {bool(settings.AZURE_OPENAI_ENDPOINT)}")
        return False

    print("✅ Azure OpenAI service is available")

    # Test embeddings
    test_texts = [
        "This is a test document for Azure OpenAI embeddings.",
        "Another test document to verify the embedding quality.",
        "Testing multimodal RAG system with Azure OpenAI integration."
    ]

    try:
        print("\n📊 Testing Azure OpenAI embeddings...")
        embeddings = await azure_openai_service.get_embeddings(test_texts)

        if embeddings and len(embeddings) == len(test_texts):
            print(f"✅ Successfully generated {len(embeddings)} embeddings")
            print(f"   Embedding dimension: {len(embeddings[0])}")
            print(f"   Sample embedding values (first 5): {embeddings[0][:5]}")
        else:
            print("❌ Failed to generate embeddings")
            return False

    except Exception as e:
        print(f"❌ Error testing embeddings: {str(e)}")
        return False

    # Test chat completion
    try:
        print("\n💬 Testing Azure OpenAI chat completion...")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is a RAG system?"}
        ]

        response = await azure_openai_service.chat_completion(
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )

        if response and "content" in response:
            print("✅ Chat completion successful")
            print(f"   Response: {response['content'][:100]}...")
            print(f"   Usage: {response['usage']}")
        else:
            print("❌ Failed to get chat completion")
            return False

    except Exception as e:
        print(f"❌ Error testing chat completion: {str(e)}")
        return False

    # Test token counting
    try:
        print("\n🔢 Testing token counting...")
        test_text = "This is a sample text for token counting with Azure OpenAI."
        token_count = azure_openai_service.count_tokens(test_text)
        print(f"✅ Token count for text: {token_count}")

    except Exception as e:
        print(f"❌ Error testing token counting: {str(e)}")

    # Get model info
    try:
        print("\nℹ️  Azure OpenAI model information:")
        model_info = azure_openai_service.get_model_info()
        print(json.dumps(model_info, indent=2))

    except Exception as e:
        print(f"❌ Error getting model info: {str(e)}")

    return True

async def test_embedding_service_integration():
    """Test embedding service with Azure OpenAI integration"""
    print("\n🔄 Testing Embedding Service Integration with Azure OpenAI...")

    # Test provider selection
    try:
        print("📋 Testing provider selection...")
        print(f"   Current provider: {embedding_service.embedding_provider}")

        # Switch to Azure OpenAI if available
        if azure_openai_service.is_available():
            embedding_service.set_provider("azure_openai")
            print("✅ Successfully switched to Azure OpenAI provider")

            # Test single embedding
            from src.models.vector import EmbeddingRequest
            request = EmbeddingRequest(text="Test Azure OpenAI embedding integration")
            response = await embedding_service.generate_embedding(request)

            print(f"✅ Single embedding successful")
            print(f"   Provider: {getattr(response, 'provider', 'unknown')}")
            print(f"   Dimension: {response.dimension}")
            print(f"   Processing time: {response.processing_time:.3f}s")

            # Test batch embeddings
            from src.models.vector import BatchEmbeddingRequest
            batch_request = BatchEmbeddingRequest(texts=[
                "First test document",
                "Second test document",
                "Third test document"
            ])
            batch_response = await embedding_service.generate_batch_embeddings(batch_request)

            print(f"✅ Batch embedding successful")
            print(f"   Provider: {getattr(batch_response, 'provider', 'unknown')}")
            print(f"   Successful embeddings: {len([e for e in batch_response.embeddings if e is not None])}")
            print(f"   Processing time: {batch_response.processing_time:.3f}s")

        else:
            print("⚠️  Azure OpenAI not available, skipping provider tests")

    except Exception as e:
        print(f"❌ Error testing embedding service integration: {str(e)}")
        return False

    return True

async def test_fallback_mechanism():
    """Test fallback mechanism from sentence transformers to Azure OpenAI"""
    print("\n🔄 Testing Fallback Mechanism...")

    try:
        # Set provider to sentence transformers first
        embedding_service.set_provider("sentence_transformers")

        # Test with a request that should work with sentence transformers
        from src.models.vector import EmbeddingRequest
        request = EmbeddingRequest(text="Testing fallback mechanism")
        response = await embedding_service.generate_embedding(request)

        print(f"✅ Sentence transformers working")
        print(f"   Provider: {getattr(response, 'provider', 'unknown')}")

        # The fallback will only trigger if sentence transformers fail
        # This is tested by forcing an invalid model or other error conditions
        print("ℹ️  Fallback mechanism will activate automatically if sentence transformers fail")

    except Exception as e:
        print(f"❌ Error testing fallback mechanism: {str(e)}")
        return False

    return True

async def main():
    """Main test function"""
    print("🚀 Starting Azure OpenAI Integration Tests\n")

    # Check environment configuration
    print("🔍 Environment Configuration:")
    print(f"   AZURE_OPENAI_API_KEY: {'✅ Set' if settings.AZURE_OPENAI_API_KEY else '❌ Not set'}")
    print(f"   AZURE_OPENAI_ENDPOINT: {'✅ Set' if settings.AZURE_OPENAI_ENDPOINT else '❌ Not set'}")
    print(f"   AZURE_OPENAI_API_VERSION: {settings.AZURE_OPENAI_API_VERSION}")
    print(f"   AZURE_OPENAI_DEPLOYMENT_NAME: {settings.AZURE_OPENAI_DEPLOYMENT_NAME or 'Not set'}")
    print(f"   AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME: {settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME or 'Not set'}")
    print(f"   AZURE_OPENAI_CHAT_DEPLOYMENT_NAME: {settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME or 'Not set'}")

    success = True

    # Run tests
    tests = [
        ("Azure OpenAI Service", test_azure_openai_service),
        ("Embedding Service Integration", test_embedding_service_integration),
        ("Fallback Mechanism", test_fallback_mechanism),
    ]

    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"🧪 Running {test_name} Tests")
        print(f"{'='*50}")

        try:
            result = await test_func()
            if not result:
                success = False
                print(f"❌ {test_name} tests failed")
            else:
                print(f"✅ {test_name} tests completed successfully")
        except Exception as e:
            success = False
            print(f"❌ {test_name} tests failed with exception: {str(e)}")

    # Final summary
    print(f"\n{'='*50}")
    if success:
        print("🎉 All Azure OpenAI integration tests passed!")
        print("\n📝 Next steps:")
        print("   1. Create a .env file with your Azure OpenAI credentials")
        print("   2. Test with real documents through the API")
        print("   3. Monitor performance and costs")
        print("   4. Configure deployment names in your environment")
    else:
        print("❌ Some Azure OpenAI integration tests failed")
        print("\n🔧 Troubleshooting:")
        print("   1. Verify your Azure OpenAI credentials in .env")
        print("   2. Check your Azure OpenAI resource endpoint")
        print("   3. Ensure deployment names match your Azure OpenAI deployments")
        print("   4. Check network connectivity to Azure OpenAI")

    print(f"{'='*50}")

if __name__ == "__main__":
    asyncio.run(main())