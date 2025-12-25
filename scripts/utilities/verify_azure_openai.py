#!/usr/bin/env python3
"""
Verify Azure OpenAI configuration and show how it's integrated
"""

import os
import sys

# Add backend to path
sys.path.insert(0, '/Users/goodwiinz/development/RAG_system/rag/backend')

def verify_azure_config():
    """Verify Azure OpenAI configuration in the environment"""
    print("🔍 Verifying Azure OpenAI Configuration")
    print("=" * 50)

    # Check environment variables
    required_vars = [
        'AZURE_OPENAI_API_KEY',
        'AZURE_OPENAI_ENDPOINT',
        'AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME'
    ]

    config_ok = True
    for var in required_vars:
        value = os.getenv(var)
        if value and value.strip():
            masked_value = value[:8] + "..." if len(value) > 8 else "SET"
            print(f"✅ {var}: {masked_value}")
        else:
            print(f"❌ {var}: Not set or empty")
            config_ok = False

    return config_ok

def test_azure_service_import():
    """Test importing and initializing Azure OpenAI service"""
    print("\n🧪 Testing Azure OpenAI Service Import")
    print("=" * 50)

    try:
        # Load environment from .env file
        env_path = '/Users/goodwiinz/development/RAG_system/rag/.env'
        if os.path.exists(env_path):
            print(f"✅ Found .env file: {env_path}")

            # Load environment variables
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
            print("✅ Environment variables loaded from .env")
        else:
            print(f"❌ .env file not found: {env_path}")
            return False

        # Try to import the service
        from src.services.azure_openai_service import azure_openai_service
        print("✅ Azure OpenAI service imported successfully")

        # Check service availability
        if azure_openai_service.is_available():
            print("✅ Azure OpenAI service is available")

            # Get model info
            model_info = azure_openai_service.get_model_info()
            print(f"✅ Provider: {model_info.get('provider', 'Unknown')}")
            print(f"✅ Endpoint: {model_info.get('endpoint', 'Unknown')}")
            print(f"✅ Embedding Deployment: {model_info.get('embedding_deployment', 'Unknown')}")
            print(f"✅ Chat Deployment: {model_info.get('chat_deployment', 'Unknown')}")

            return True
        else:
            print("❌ Azure OpenAI service is not available")
            print("   Check your credentials and network connection")
            return False

    except ImportError as e:
        print(f"❌ Failed to import Azure OpenAI service: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Error testing Azure OpenAI service: {str(e)}")
        return False

def test_embedding_service():
    """Test embedding service with Azure OpenAI"""
    print("\n🧪 Testing Embedding Service Integration")
    print("=" * 50)

    try:
        from src.services.embedding_service import embedding_service

        print("✅ Embedding service imported successfully")
        print(f"✅ Current provider: {embedding_service.embedding_provider}")
        print(f"✅ Current model: {embedding_service.embedding_dimension}")

        # Test provider switching
        if azure_openai_service.is_available():
            embedding_service.set_provider("azure_openai")
            print("✅ Successfully switched to Azure OpenAI provider")

            # Test generating a simple embedding
            import asyncio

            async def test_embedding():
                from src.models.vector import EmbeddingRequest
                request = EmbeddingRequest(
                    text="Test Azure OpenAI embedding generation",
                    provider="azure_openai"
                )

                try:
                    response = await embedding_service.generate_embedding(request)
                    print("✅ Azure OpenAI embedding generated successfully!")
                    print(f"   Dimension: {response.dimension}")
                    print(f"   Provider: {getattr(response, 'provider', 'Unknown')}")
                    print(f"   Processing time: {response.processing_time:.3f}s")
                    return True
                except Exception as e:
                    print(f"❌ Error generating embedding: {str(e)}")
                    return False

            # Run the async test
            return asyncio.run(test_embedding())
        else:
            print("⚠️  Azure OpenAI not available, skipping embedding test")
            return True

    except ImportError as e:
        print(f"❌ Failed to import embedding service: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Error testing embedding service: {str(e)}")
        return False

def show_api_endpoints():
    """Show which API endpoints use Azure OpenAI"""
    print("\n🌐 API Endpoints Using Azure OpenAI")
    print("=" * 50)

    endpoints = [
        ("POST", "/api/v1/vectors/embeddings", "Single text embedding"),
        ("POST", "/api/v1/vectors/embeddings/batch", "Batch text embeddings"),
        ("GET", "/api/v1/vectors/health", "Vector service health"),
        ("GET", "/api/v1/vectors/collections", "List vector collections"),
        ("POST", "/api/v1/documents/upload", "Document upload with embeddings"),
    ]

    print("📋 These endpoints use Azure OpenAI when available:")
    for method, endpoint, description in endpoints:
        print(f"   {method:8} {endpoint:35} - {description}")

    print(f"\n🔗 Full API Documentation: http://localhost:8000/docs")
    print(f"🏠 Frontend Application: http://localhost:3000")

def main():
    """Run all verification tests"""
    print("🚀 Azure OpenAI Integration Verification")
    print("=" * 60)

    # Test 1: Configuration
    config_ok = verify_azure_config()

    # Test 2: Service Import
    service_ok = test_azure_service_import()

    # Test 3: Embedding Integration
    embedding_ok = test_embedding_service()

    # Show API endpoints
    show_api_endpoints()

    # Summary
    print("\n📊 Summary")
    print("=" * 50)

    if config_ok and service_ok and embedding_ok:
        print("🎉 Azure OpenAI integration is fully functional!")
        print("\n🔧 How to use:")
        print("1. Frontend UI: Upload documents → Uses Azure OpenAI for embeddings")
        print("2. API Calls: Include 'provider': 'azure_openai' in requests")
        print("3. Default: System automatically uses Azure OpenAI when configured")

        print(f"\n🌐 Access Points:")
        print(f"   Frontend: http://localhost:3000")
        print(f"   API Docs: http://localhost:8000/docs")
        print(f"   Backend:  http://localhost:8000")

    else:
        print("⚠️  Some issues detected:")
        if not config_ok:
            print("   - Check your .env file configuration")
        if not service_ok:
            print("   - Check Azure OpenAI credentials and network")
        if not embedding_ok:
            print("   - Check embedding service configuration")

        print(f"\n🔧 Troubleshooting:")
        print(f"   - Check .env file: cat .env | grep AZURE_OPENAI")
        print(f"   - Check service logs: docker-compose logs backend")
        print(f"   - Test connectivity: curl -H 'api-key: YOUR_KEY' https://your-endpoint/")

if __name__ == "__main__":
    main()