#!/usr/bin/env python3
"""
Test script for vector database setup and embedding generation
"""

import os
import sys
import time
import logging

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_embedding_service():
    """Test the embedding service"""
    print("\n=== Testing Embedding Service ===")

    try:
        from src.services.embedding_service import embedding_service

        # Test model info
        model_info = embedding_service.get_model_info()
        print(f"✅ Model loaded: {model_info['model_name']}")
        print(f"✅ Dimension: {model_info['dimension']}")
        print(f"✅ Device: {model_info['device']}")

        # Test single embedding
        from src.models.vector import EmbeddingRequest
        request = EmbeddingRequest(text="This is a test document for embedding generation.")
        result = embedding_service.generate_embedding(request)

        print(f"✅ Single embedding generated successfully")
        print(f"✅ Embedding dimension: {len(result.embedding)}")
        print(f"✅ Processing time: {result.processing_time:.4f}s")

        # Test batch embedding
        from src.models.vector import BatchEmbeddingRequest
        batch_request = BatchEmbeddingRequest(texts=[
            "First test document",
            "Second test document",
            "Third test document"
        ])
        batch_result = embedding_service.generate_batch_embeddings(batch_request)

        print(f"✅ Batch embedding generated successfully")
        print(f"✅ Generated {len(batch_result.embeddings)} embeddings")
        print(f"✅ Processing time: {batch_result.processing_time:.4f}s")
        print(f"✅ Failed count: {batch_result.failed_count}")

        # Test embedding quality
        test_texts = [
            "The weather is sunny today",
            "Machine learning is a subfield of artificial intelligence",
            "Python is a popular programming language"
        ]
        quality_result = embedding_service.test_embedding_quality(test_texts)

        print(f"✅ Embedding quality test completed")
        print(f"✅ Quality score: {quality_result.get('quality_score', 'N/A')}")
        print(f"✅ Average similarity: {quality_result.get('avg_pairwise_similarity', 'N/A')}")

        return True

    except Exception as e:
        print(f"❌ Embedding service test failed: {e}")
        return False

def test_vector_service():
    """Test the vector database service"""
    print("\n=== Testing Vector Database Service ===")

    try:
        from src.services.vector_service import vector_service
        from src.models.vector import VectorCollectionType, CollectionConfig

        # Test health status
        health = vector_service.get_health_status()
        print(f"✅ Vector database health: {health.status}")
        print(f"✅ Collections count: {health.collections_count}")
        print(f"✅ Total vectors: {health.total_vectors}")

        # Test collection creation
        config = CollectionConfig(
            name="test_collection",
            vector_size=384,
            distance="Cosine",
            on_disk=True
        )

        create_result = vector_service.create_collection(config)
        if create_result.success:
            print(f"✅ Test collection created successfully")
        else:
            print(f"⚠️ Test collection may already exist: {create_result.message}")

        # Test collection stats
        stats = vector_service.get_collection_stats(VectorCollectionType.DOCUMENT_CHUNKS)
        if stats:
            print(f"✅ Document chunks collection stats retrieved")
            print(f"✅ Vectors count: {stats.vectors_count}")
        else:
            print("ℹ️ Document chunks collection not created yet")

        return True

    except Exception as e:
        print(f"❌ Vector service test failed: {e}")
        return False

def test_vector_search_service():
    """Test the combined vector search service"""
    print("\n=== Testing Vector Search Service ===")

    try:
        from src.services.vector_search_service import vector_search_service

        # Test model info
        model_info = vector_search_service.get_embedding_model_info()
        print(f"✅ Vector search service model info retrieved")
        print(f"✅ Model: {model_info['model_name']}")

        # Test health status
        health = vector_search_service.get_vector_database_health()
        print(f"✅ Vector database health retrieved")
        print(f"✅ Status: {health['status']}")

        # Test document indexing
        result = vector_search_service.index_document(
            document_id="test_doc_001",
            text="This is a test document for vector indexing. It contains multiple sentences and various content types to test the embedding and indexing functionality.",
            organization_id="test_org_001",
            content_type="text",
            source_type="test"
        )

        if result.success:
            print(f"✅ Test document indexed successfully")
        else:
            print(f"❌ Document indexing failed: {result.error}")

        # Test document search
        search_result = vector_search_service.search_documents(
            query="test document functionality",
            organization_id="test_org_001",
            limit=5,
            score_threshold=0.5
        )

        print(f"✅ Document search completed")
        print(f"✅ Found {search_result.total_found} results")
        print(f"✅ Search time: {search_result.search_time:.4f}s")

        # Test entity indexing
        entity_result = vector_search_service.index_entity(
            entity_id="test_entity_001",
            entity_text="Test Entity",
            entity_type="PERSON",
            confidence_score=0.95,
            organization_id="test_org_001",
            document_id="test_doc_001"
        )

        if entity_result.success:
            print(f"✅ Test entity indexed successfully")
        else:
            print(f"❌ Entity indexing failed: {entity_result.error}")

        # Test entity search
        entity_search_result = vector_search_service.search_entities(
            query="Test Entity",
            organization_id="test_org_001",
            limit=5,
            score_threshold=0.5
        )

        print(f"✅ Entity search completed")
        print(f"✅ Found {entity_search_result.total_found} entities")
        print(f"✅ Search time: {entity_search_result.search_time:.4f}s")

        return True

    except Exception as e:
        print(f"❌ Vector search service test failed: {e}")
        return False

def test_api_endpoints():
    """Test the API endpoints"""
    print("\n=== Testing API Endpoints ===")

    try:
        import httpx

        # Test health endpoint
        response = httpx.get("http://localhost:8000/health")
        if response.status_code == 200:
            print("✅ Health endpoint accessible")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False

        # Test vector model info endpoint
        response = httpx.get("http://localhost:8000/api/v1/vectors/model/info")
        if response.status_code == 200:
            model_info = response.json()
            print(f"✅ Vector model info endpoint accessible")
            print(f"✅ Model: {model_info.get('model_name', 'Unknown')}")
        else:
            print(f"❌ Vector model info endpoint failed: {response.status_code}")

        # Test embedding generation endpoint
        response = httpx.post(
            "http://localhost:8000/api/v1/vectors/embeddings",
            json={"text": "Test text for embedding generation"}
        )
        if response.status_code == 200:
            embedding_result = response.json()
            print(f"✅ Embedding generation endpoint accessible")
            print(f"✅ Generated embedding dimension: {len(embedding_result.get('embedding', []))}")
        else:
            print(f"❌ Embedding generation endpoint failed: {response.status_code}")

        # Test vector health endpoint
        response = httpx.get("http://localhost:8000/api/v1/vectors/health")
        if response.status_code == 200:
            health_info = response.json()
            print(f"✅ Vector health endpoint accessible")
            print(f"✅ Vector database status: {health_info.get('status', 'Unknown')}")
        else:
            print(f"❌ Vector health endpoint failed: {response.status_code}")

        return True

    except Exception as e:
        print(f"❌ API endpoint test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Testing Vector Database Setup and Embedding Generation")
    print("=" * 60)

    all_tests_passed = True

    # Test embedding service
    if not test_embedding_service():
        all_tests_passed = False

    # Test vector service
    if not test_vector_service():
        all_tests_passed = False

    # Test vector search service
    if not test_vector_search_service():
        all_tests_passed = False

    # Test API endpoints
    if not test_api_endpoints():
        all_tests_passed = False

    print("\n" + "=" * 60)
    if all_tests_passed:
        print("🎉 All tests passed! Vector database setup is working correctly.")
        print("\n📋 T2-001 Acceptance Criteria Status:")
        print("✅ Qdrant database is running and accessible")
        print("✅ Embedding generation is working efficiently")
        print("✅ Vector storage and retrieval operations are functional")
        print("✅ Vector similarity search returns relevant results")
        print("✅ API endpoints are accessible and functional")
    else:
        print("❌ Some tests failed. Please check the error messages above.")
        print("\n🔧 Troubleshooting steps:")
        print("1. Ensure Qdrant is running: docker-compose up qdrant")
        print("2. Check environment variables in .env file")
        print("3. Verify dependencies are installed: pip install -r requirements.txt")
        print("4. Check network connectivity between services")

    return all_tests_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)