#!/usr/bin/env python3
"""
Quick Embedding Test - Fast validation that Azure OpenAI embeddings are working
"""

import os
import requests
import time
import sys

def quick_embedding_test():
    """Quick test to validate Azure OpenAI embedding service"""
    print("⚡ Quick Azure OpenAI Embedding Test")
    print("-" * 40)

    # Load environment
    env_path = '/Users/goodwiinz/development/RAG_system/rag/.env'
    if not os.path.exists(env_path):
        print("❌ .env file not found")
        return False

    print("✅ Loading environment...")
    with open(env_path, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

    # Configuration
    api_key = os.getenv('AZURE_OPENAI_EMBEDDING_API_KEY') or os.getenv('AZURE_OPENAI_API_KEY')
    base_endpoint = os.getenv('AZURE_OPENAI_EMBEDDING_ENDPOINT')
    deployment = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', 'text-embedding-ada-002')
    api_version = os.getenv('AZURE_OPENAI_EMBEDDING_API_VERSION', '2023-05-15')

    if not api_key or not base_endpoint:
        print("❌ Missing configuration:")
        if not api_key:
            print("   - AZURE_OPENAI_EMBEDDING_API_KEY or AZURE_OPENAI_API_KEY")
        if not base_endpoint:
            print("   - AZURE_OPENAI_EMBEDDING_ENDPOINT")
        return False

    url = f"{base_endpoint.rstrip('/')}/openai/deployments/{deployment}/embeddings?api-version={api_version}"
    headers = {'Content-Type': 'application/json', 'api-key': api_key}

    print(f"   Endpoint: {base_endpoint}")
    print(f"   Deployment: {deployment}")

    # Test single embedding
    test_text = "Azure OpenAI embedding service quick test."
    data = {'input': test_text}

    print(f"\n🧪 Testing: '{test_text}'")
    start_time = time.time()

    try:
        response = requests.post(url, headers=headers, json=data)
        response_time = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            embedding = result['data'][0]['embedding']
            usage = result.get('usage', {})

            print(f"✅ SUCCESS! Embedding generated")
            print(f"   Dimension: {len(embedding)}")
            print(f"   Response time: {response_time:.3f}s")
            print(f"   Tokens used: {usage.get('total_tokens', 'N/A')}")
            print(f"   First 3 values: {embedding[:3]}")

            # Test batch embedding
            print(f"\n🧪 Testing batch embedding...")
            batch_texts = ["First test", "Second test", "Third test"]
            batch_data = {'input': batch_texts}

            start_time = time.time()
            batch_response = requests.post(url, headers=headers, json=batch_data)
            batch_time = time.time() - start_time

            if batch_response.status_code == 200:
                batch_result = batch_response.json()
                batch_embeddings = [item['embedding'] for item in batch_result['data']]
                batch_usage = batch_result.get('usage', {})

                print(f"✅ Batch embedding successful")
                print(f"   Processed: {len(batch_texts)} texts")
                print(f"   Generated: {len(batch_embeddings)} embeddings")
                print(f"   Response time: {batch_time:.3f}s")
                print(f"   Average time per embedding: {batch_time/len(batch_texts):.3f}s")
                print(f"   Tokens used: {batch_usage.get('total_tokens', 'N/A')}")

                print(f"\n🎉 ALL TESTS PASSED!")
                print(f"   Azure OpenAI embedding service is fully functional")
                return True
            else:
                print(f"❌ Batch embedding failed: {batch_response.status_code}")
                print(f"   Error: {batch_response.text}")
                return False

        else:
            print(f"❌ Embedding generation failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def main():
    """Main test runner"""
    success = quick_embedding_test()

    if success:
        print(f"\n🚀 Ready for production!")
        print(f"   Your Azure OpenAI embedding service is working correctly")
        print(f"   You can now use it for:")
        print(f"   • Document processing")
        print(f"   • RAG workflows")
        print(f"   • Semantic search")
        print(f"   • Vector similarity")
    else:
        print(f"\n❌ Service not ready")
        print(f"   Please check your configuration and try again")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)