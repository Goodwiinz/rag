#!/usr/bin/env python3
"""
Quick test to verify Azure OpenAI integration is working
"""

import requests
import json

def test_embedding_endpoint():
    """Test the embedding endpoint that uses Azure OpenAI"""
    url = "http://localhost:8000/api/v1/vectors/embeddings"

    payload = {
        "text": "This is a test of Azure OpenAI embedding integration",
        "provider": "azure_openai"
    }

    try:
        print("🧪 Testing Azure OpenAI Embedding Endpoint...")
        response = requests.post(url, json=payload)

        if response.status_code == 200:
            result = response.json()
            print("✅ Embedding request successful!")
            print(f"   Provider: {result.get('provider', 'Unknown')}")
            print(f"   Dimension: {result.get('dimension', 'Unknown')}")
            print(f"   Processing time: {result.get('processing_time', 0):.3f}s")
            return True
        else:
            print(f"❌ Embedding request failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error testing embedding: {str(e)}")
        return False

def test_batch_embedding():
    """Test batch embedding endpoint"""
    url = "http://localhost:8000/api/v1/vectors/embeddings/batch"

    payload = {
        "texts": [
            "First test document for Azure OpenAI",
            "Second test document for batch processing",
            "Third test document to verify quality"
        ],
        "provider": "azure_openai"
    }

    try:
        print("\n🧪 Testing Azure OpenAI Batch Embedding Endpoint...")
        response = requests.post(url, json=payload)

        if response.status_code == 200:
            result = response.json()
            print("✅ Batch embedding request successful!")
            print(f"   Provider: {result.get('provider', 'Unknown')}")
            print(f"   Successful embeddings: {len([e for e in result.get('embeddings', []) if e is not None])}")
            print(f"   Processing time: {result.get('processing_time', 0):.3f}s")
            return True
        else:
            print(f"❌ Batch embedding request failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error testing batch embedding: {str(e)}")
        return False

def test_vector_service_health():
    """Test vector service health (includes Azure OpenAI check)"""
    url = "http://localhost:8000/api/v1/vectors/health"

    try:
        print("\n🧪 Testing Vector Service Health...")
        response = requests.get(url)

        if response.status_code == 200:
            result = response.json()
            print("✅ Vector service is healthy!")
            print(f"   Status: {result.get('status', 'Unknown')}")
            print(f"   Provider: {result.get('embedding_provider', 'Unknown')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error testing health: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing Azure OpenAI Integration")
    print("=" * 50)

    # Test health first
    health_ok = test_vector_service_health()

    if health_ok:
        # Test embeddings
        embedding_ok = test_embedding_endpoint()
        batch_ok = test_batch_embedding()

        if embedding_ok and batch_ok:
            print("\n🎉 All Azure OpenAI tests passed!")
            print("\n📝 How to use Azure OpenAI:")
            print("1. Upload documents through the frontend")
            print("2. Use the embedding endpoints directly")
            print("3. Query the system for RAG responses")
            print("\n🌐 Frontend: http://localhost:3000")
            print("🔧 Backend API: http://localhost:8000/docs")
        else:
            print("\n❌ Some tests failed. Check the backend logs:")
            print("   docker-compose logs backend")
    else:
        print("\n❌ Vector service not healthy. Check if services are running:")
        print("   ./start.sh status")

if __name__ == "__main__":
    main()