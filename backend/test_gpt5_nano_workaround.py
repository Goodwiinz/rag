#!/usr/bin/env python3
"""
Test GPT-5 Nano with direct API call to work around client limitations
"""

import os
import requests
import json

def test_gpt5_nano_direct():
    """Test GPT-5 Nano with direct HTTP API call"""

    # Azure OpenAI configuration
    api_key = os.getenv('AZURE_OPENAI_API_KEY')
    endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    deployment = 'gpt-5-nano'
    api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-06-01')

    print('🚀 Testing GPT-5 Nano with Direct API Call!')
    print(f'   Endpoint: {endpoint}')
    print(f'   Deployment: {deployment}')

    # Build the URL
    url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'api-key': api_key
    }

    # Request body
    data = {
        'messages': [
            {'role': 'system', 'content': 'You are a helpful AI assistant.'},
            {'role': 'user', 'content': 'Hello! Introduce yourself briefly.'}
        ],
        'max_completion_tokens': 50,
        'temperature': 1.0
    }

    try:
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            result = response.json()
            print('🎉 SUCCESS! GPT-5 Nano is working with direct API call!')
            print(f'   Response: {result["choices"][0]["message"]["content"]}')
            print(f'   Usage: {result.get("usage", {})}')
            print(f'   Model: {result.get("model", deployment)}')
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
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    result = test_gpt5_nano_direct()
    print(f'\n🎯 GPT-5 Nano Status: {"WORKING" if result else "NOT WORKING"}')