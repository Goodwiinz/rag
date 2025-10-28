#!/usr/bin/env python3
"""
Test script for Azure OpenAI text-embedding-ada-002 endpoint
"""

import os
import requests
import json

def test_embedding_endpoint():
    """Test text embedding generation with Azure OpenAI"""

    # Azure OpenAI configuration
    api_key = os.getenv('AZURE_OPENAI_API_KEY')
    base_endpoint = os.getenv('AZURE_OPENAI_EMBEDDING_ENDPOINT')
    api_version = os.getenv('AZURE_OPENAI_EMBEDDING_API_VERSION', '2023-05-15')
    deployment = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', 'text-embedding-ada-002')

    print('🔤 Testing Azure OpenAI Text Embedding!')
    print(f'   Base Endpoint: {base_endpoint}')
    print(f'   Deployment: {deployment}')
    print(f'   API Version: {api_version}')

    if not base_endpoint:
        print('❌ AZURE_OPENAI_EMBEDDING_ENDPOINT not set')
        return False

    # The user provided the exact URL format earlier
    # "https://goodwiinzapi.cognitiveservices.azure.com/openai/deployments/text-embedding-ada-002/embeddings?api-version=2023-05-15"
    url = f"{base_endpoint.rstrip('/')}/openai/deployments/{deployment}/embeddings?api-version={api_version}"
    print(f'   Full URL: {url}')

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'api-key': api_key
    }

    # Request body
    data = {
        'input': 'This is a test document for Azure OpenAI embedding generation.'
    }

    try:
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            result = response.json()
            print('🎉 SUCCESS! Text embedding generation is working!')
            print(f'   Embedding Dimension: {len(result["data"][0]["embedding"])}')
            print(f'   Model: {result.get("model", "text-embedding-ada-002")}')
            print(f'   Usage: {result.get("usage", {})}')
            print(f'   First 5 values: {result["data"][0]["embedding"][:5]}')
            return True
        else:
            print(f'❌ HTTP Error {response.status_code}: {response.text}')
            return False

    except Exception as e:
        print(f'❌ Error: {str(e)}')
        return False

if __name__ == "__main__":
    # Load environment variables from .env
    env_path = '/Users/goodwiinz/development/RAG_system/rag/.env'
    if os.path.exists(env_path):
        print(f'✅ Loading environment from: {env_path}')
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    result = test_embedding_endpoint()
    print(f'\n🎯 Text Embedding Status: {"WORKING" if result else "NOT WORKING"}')