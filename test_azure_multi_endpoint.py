#!/usr/bin/env python3
"""
Test script for Azure OpenAI multi-endpoint integration
Tests both GPT-5 Nano chat and text-embedding-ada-002 embeddings
"""

import os
import sys
import asyncio

# Add backend to path
sys.path.insert(0, '/Users/goodwiinz/development/RAG_system/rag/backend')

async def test_azure_openai_multi_endpoint():
    """Test both chat and embedding services with separate endpoints"""

    print("🚀 Testing Azure OpenAI Multi-Endpoint Integration")
    print("=" * 60)

    # Load environment variables from .env
    env_path = '/Users/goodwiinz/development/RAG_system/rag/.env'
    if os.path.exists(env_path):
        print(f"✅ Loading environment from: {env_path}")
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print("✅ Environment variables loaded")
    else:
        print(f"❌ .env file not found: {env_path}")
        return False

    print("\n📋 Configuration Summary:")
    print(f"   Chat Endpoint: {os.getenv('AZURE_OPENAI_CHAT_ENDPOINT', 'Not set')}")
    print(f"   Chat Deployment: {os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME', 'Not set')}")
    print(f"   Embedding Endpoint: {os.getenv('AZURE_OPENAI_EMBEDDING_ENDPOINT', 'Not set')}")
    print(f"   Embedding Deployment: {os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', 'Not set')}")
    print(f"   API Key: {os.getenv('AZURE_OPENAI_API_KEY', 'Not set')[:8]}..." if os.getenv('AZURE_OPENAI_API_KEY') else "Not set")

    try:
        # Import services
        from src.services.azure_openai_service import azure_openai_service
        from src.services.embedding_service import embedding_service

        print("\n🧪 Service 1: Azure OpenAI Multi-Endpoint Test")
        print("-" * 50)

        # Check service availability
        chat_available = azure_openai_service.is_chat_available()
        embedding_available = azure_openai_service.is_embedding_available()

        print(f"✅ Chat Service Available: {chat_available}")
        print(f"✅ Embedding Service Available: {embedding_available}")

        if not chat_available and not embedding_available:
            print("❌ No Azure OpenAI services available. Check configuration.")
            return False

        # Test 1: Chat Completion with GPT-5 Nano
        if chat_available:
            print("\n💬 Testing GPT-5 Nano Chat Completion...")
            try:
                chat_response = await azure_openai_service.chat_completion(
                    messages=[
                        {'role': 'system', 'content': 'You are a helpful AI assistant.'},
                        {'role': 'user', 'content': 'Hello! Introduce yourself briefly in one sentence.'}
                    ],
                    max_tokens=50,
                    temperature=1.0  # GPT-5 Nano requires temperature=1.0
                )

                print("✅ GPT-5 Nano Chat Success!")
                print(f"   Response: {chat_response['content']}")
                print(f"   Model: {chat_response['model']}")
                print(f"   Usage: {chat_response['usage']}")

            except Exception as e:
                print(f"❌ GPT-5 Nano Chat Failed: {str(e)}")
                return False

        # Test 2: Embedding Generation with text-embedding-ada-002
        if embedding_available:
            print("\n🔤 Testing Text Embedding Generation...")
            try:
                embedding_response = await azure_openai_service.get_embeddings([
                    "This is a test document for Azure OpenAI embeddings.",
                    "Multimodal RAG systems process text, images, audio, and video."
                ])

                print("✅ Text Embedding Success!")
                print(f"   Number of embeddings: {len(embedding_response)}")
                print(f"   Dimension: {len(embedding_response[0])}")
                print(f"   First 5 values: {embedding_response[0][:5]}")

            except Exception as e:
                print(f"❌ Text Embedding Failed: {str(e)}")
                return False

        # Test 3: Integration with Embedding Service
        if embedding_available:
            print("\n🔧 Testing Embedding Service Integration...")
            try:
                # Switch to Azure OpenAI provider
                embedding_service.set_provider("azure_openai")
                print(f"   Current provider: {embedding_service.embedding_provider}")

                # Test single embedding
                from src.models.vector import EmbeddingRequest
                request = EmbeddingRequest(
                    text="Test Azure OpenAI embedding through service layer",
                    provider="azure_openai"
                )

                response = await embedding_service.generate_embedding(request)
                print("✅ Service Layer Embedding Success!")
                print(f"   Dimension: {response.dimension}")
                print(f"   Provider: {response.provider}")
                print(f"   Processing Time: {response.processing_time:.3f}s")

            except Exception as e:
                print(f"❌ Service Layer Integration Failed: {str(e)}")
                return False

        print("\n🎉 All tests passed! Azure OpenAI multi-endpoint integration is working.")
        print("\n📊 Summary:")
        print(f"   ✅ GPT-5 Nano Chat: {'Working' if chat_available else 'Not Available'}")
        print(f"   ✅ Text Embeddings: {'Working' if embedding_available else 'Not Available'}")
        print(f"   ✅ Service Integration: {'Working' if embedding_available else 'Not Available'}")

        return True

    except ImportError as e:
        print(f"❌ Import Error: {str(e)}")
        print("   Make sure you're running from the backend directory with all dependencies installed.")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {str(e)}")
        return False

def show_usage_info():
    """Show information about how to use the Azure OpenAI integration"""
    print("\n🔧 Usage Information:")
    print("=" * 50)
    print("1. Frontend UI:")
    print("   - Upload documents → Automatically uses Azure OpenAI for embeddings")
    print("   - Chat interface → Uses GPT-5 Nano for responses")
    print(f"   - Access: http://localhost:3000")

    print("\n2. API Usage:")
    print("   - Include 'provider': 'azure_openai' in embedding requests")
    print("   - Chat automatically uses GPT-5 Nano")
    print(f"   - API Docs: http://localhost:8000/docs")

    print("\n3. Environment Variables:")
    print("   - AZURE_OPENAI_API_KEY: Your Azure OpenAI API key")
    print("   - AZURE_OPENAI_CHAT_ENDPOINT: GPT-5 Nano endpoint")
    print("   - AZURE_OPENAI_EMBEDDING_ENDPOINT: Text embedding endpoint")
    print("   - AZURE_OPENAI_CHAT_DEPLOYMENT_NAME: GPT-5 Nano deployment name")
    print("   - AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME: Text embedding deployment name")

if __name__ == "__main__":
    success = asyncio.run(test_azure_openai_multi_endpoint())

    if success:
        show_usage_info()
        print(f"\n🎯 Status: Azure OpenAI Multi-Endpoint Integration FULLY FUNCTIONAL!")
    else:
        print(f"\n❌ Status: Integration issues detected. Check configuration and logs.")

    print(f"\n🔍 Troubleshooting:")
    print(f"   - Check .env file: cat .env | grep AZURE_OPENAI")
    print(f"   - Check service logs: docker-compose logs backend")
    print(f"   - Test endpoints manually with curl")
    print(f"   - Verify Azure resource deployments")