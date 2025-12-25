#!/usr/bin/env python3
"""
Comprehensive test for both Azure OpenAI services working together
"""

import os
import requests
import json

def test_gpt5_nano():
    """Test GPT-5 Nano chat completion"""
    print("💬 Testing GPT-5 Nano Chat Completion")
    print("-" * 40)

    api_key = os.getenv('AZURE_OPENAI_CHAT_API_KEY') or os.getenv('AZURE_OPENAI_API_KEY')
    endpoint = os.getenv('AZURE_OPENAI_CHAT_ENDPOINT')
    deployment = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME', 'gpt-5-nano')
    api_version = os.getenv('AZURE_OPENAI_CHAT_API_VERSION', '2024-06-01')

    url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    headers = {
        'Content-Type': 'application/json',
        'api-key': api_key
    }

    data = {
        'messages': [
            {'role': 'system', 'content': 'You are a helpful AI assistant.'},
            {'role': 'user', 'content': 'Explain what multimodal RAG systems do in one sentence.'}
        ],
        'max_completion_tokens': 50,
        'temperature': 1.0
    }

    try:
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            result = response.json()
            print('✅ GPT-5 Nano Chat SUCCESS!')
            print(f'   Response: {result["choices"][0]["message"]["content"]}')
            print(f'   Model: {result.get("model", deployment)}')
            print(f'   Usage: {result.get("usage", {})}')
            return True
        else:
            print(f'❌ GPT-5 Nano Chat FAILED: {response.status_code}')
            print(f'   Error: {response.text}')
            return False
    except Exception as e:
        print(f'❌ GPT-5 Nano Chat ERROR: {str(e)}')
        return False

def test_text_embedding():
    """Test text-embedding-ada-002 embedding generation"""
    print("\n🔤 Testing Text Embedding Generation")
    print("-" * 40)

    api_key = os.getenv('AZURE_OPENAI_EMBEDDING_API_KEY') or os.getenv('AZURE_OPENAI_API_KEY')
    base_endpoint = os.getenv('AZURE_OPENAI_EMBEDDING_ENDPOINT')
    deployment = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', 'text-embedding-ada-002')
    api_version = os.getenv('AZURE_OPENAI_EMBEDDING_API_VERSION', '2023-05-15')

    url = f"{base_endpoint.rstrip('/')}/openai/deployments/{deployment}/embeddings?api-version={api_version}"

    headers = {
        'Content-Type': 'application/json',
        'api-key': api_key
    }

    data = {
        'input': 'Multimodal RAG systems process text, images, audio, and video to provide comprehensive answers.'
    }

    try:
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            result = response.json()
            print('✅ Text Embedding SUCCESS!')
            print(f'   Model: {result.get("model", deployment)}')
            print(f'   Dimension: {len(result["data"][0]["embedding"])}')
            print(f'   Usage: {result.get("usage", {})}')
            print(f'   First 3 values: {result["data"][0]["embedding"][:3]}')
            return True
        else:
            print(f'❌ Text Embedding FAILED: {response.status_code}')
            print(f'   Error: {response.text}')
            return False
    except Exception as e:
        print(f'❌ Text Embedding ERROR: {str(e)}')
        return False

def test_rag_workflow():
    """Test a complete RAG workflow using both services"""
    print("\n🔄 Testing Complete RAG Workflow")
    print("-" * 40)

    # Sample document text
    document_text = """
    Azure OpenAI provides powerful language models and embedding services.
    GPT-5 Nano is optimized for conversational AI tasks, while text-embedding-ada-002
    creates high-quality vector representations for semantic search and retrieval.
    """

    # Step 1: Generate embedding for the document
    print("Step 1: Generating document embedding...")
    api_key = os.getenv('AZURE_OPENAI_EMBEDDING_API_KEY') or os.getenv('AZURE_OPENAI_API_KEY')
    base_endpoint = os.getenv('AZURE_OPENAI_EMBEDDING_ENDPOINT')
    deployment = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', 'text-embedding-ada-002')
    api_version = os.getenv('AZURE_OPENAI_EMBEDDING_API_VERSION', '2023-05-15')

    url = f"{base_endpoint.rstrip('/')}/openai/deployments/{deployment}/embeddings?api-version={api_version}"

    headers = {
        'Content-Type': 'application/json',
        'api-key': api_key
    }

    data = {'input': document_text.strip()}

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            print(f'❌ Document embedding failed: {response.text}')
            return False

        doc_embedding = response.json()['data'][0]['embedding']
        print(f'✅ Document embedding generated (dimension: {len(doc_embedding)})')

    except Exception as e:
        print(f'❌ Document embedding error: {str(e)}')
        return False

    # Step 2: Generate a question and get chat completion
    print("\nStep 2: Processing user query with GPT-5 Nano...")
    question = "What services does Azure OpenAI provide for RAG systems?"

    chat_endpoint = os.getenv('AZURE_OPENAI_CHAT_ENDPOINT')
    chat_deployment = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME', 'gpt-5-nano')
    chat_api_version = os.getenv('AZURE_OPENAI_CHAT_API_VERSION', '2024-06-01')
    chat_api_key = os.getenv('AZURE_OPENAI_CHAT_API_KEY') or os.getenv('AZURE_OPENAI_API_KEY')

    chat_url = f"{chat_endpoint.rstrip('/')}/openai/deployments/{chat_deployment}/chat/completions?api-version={chat_api_version}"

    chat_data = {
        'messages': [
            {'role': 'system', 'content': 'You are a helpful AI assistant specializing in RAG systems. Use the provided document to answer questions accurately.'},
            {'role': 'user', 'content': f'Document: {document_text.strip()}\n\nQuestion: {question}\n\nAnswer:'}
        ],
        'max_completion_tokens': 100,
        'temperature': 1.0
    }

    chat_headers = {
        'Content-Type': 'application/json',
        'api-key': chat_api_key
    }

    try:
        response = requests.post(chat_url, headers=chat_headers, json=chat_data)
        if response.status_code != 200:
            print(f'❌ Chat completion failed: {response.text}')
            return False

        chat_result = response.json()
        answer = chat_result["choices"][0]["message"]["content"]
        print(f'✅ Chat completion successful!')
        print(f'   Question: {question}')
        print(f'   Answer: {answer}')
        print(f'   Tokens used: {chat_result.get("usage", {})}')

    except Exception as e:
        print(f'❌ Chat completion error: {str(e)}')
        return False

    print('\n🎉 Complete RAG workflow successful!')
    return True

def main():
    """Run all tests"""
    print("🚀 Azure OpenAI Multi-Service Integration Test")
    print("=" * 60)

    # Load environment variables
    env_path = '/Users/goodwiinz/development/RAG_system/rag/.env'
    if os.path.exists(env_path):
        print(f'✅ Loading environment from: {env_path}')
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    else:
        print(f'❌ .env file not found: {env_path}')
        return False

    print("\n📋 Configuration Summary:")
    print(f"   Chat Endpoint: {os.getenv('AZURE_OPENAI_CHAT_ENDPOINT', 'Not set')}")
    print(f"   Chat Deployment: {os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME', 'Not set')}")
    print(f"   Embedding Endpoint: {os.getenv('AZURE_OPENAI_EMBEDDING_ENDPOINT', 'Not set')}")
    print(f"   Embedding Deployment: {os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', 'Not set')}")
    print(f"   Chat API Key: {os.getenv('AZURE_OPENAI_CHAT_API_KEY', 'Not set')[:20]}...")
    print(f"   Embedding API Key: {os.getenv('AZURE_OPENAI_EMBEDDING_API_KEY', 'Not set')[:20]}...")

    # Run tests
    chat_success = test_gpt5_nano()
    embedding_success = test_text_embedding()

    if chat_success and embedding_success:
        workflow_success = test_rag_workflow()
    else:
        workflow_success = False

    # Final summary
    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULTS")
    print("=" * 60)
    print(f"   GPT-5 Nano Chat:        {'✅ WORKING' if chat_success else '❌ FAILED'}")
    print(f"   Text Embeddings:        {'✅ WORKING' if embedding_success else '❌ FAILED'}")
    print(f"   RAG Workflow:           {'✅ WORKING' if workflow_success else '❌ FAILED'}")

    if chat_success and embedding_success:
        print(f"\n🎉 SUCCESS! Azure OpenAI multi-service integration is fully functional!")
        print(f"   Your system is ready for multimodal RAG operations.")
        print(f"\n🌐 Next Steps:")
        print(f"   1. Start Docker: docker-compose -f docker-compose.development.yml up -d")
        print(f"   2. Access Frontend: http://localhost:3000")
        print(f"   3. Upload documents for automatic embedding generation")
        print(f"   4. Use chat interface with GPT-5 Nano")
    else:
        print(f"\n❌ Some services need attention. Check the error messages above.")

    return chat_success and embedding_success

if __name__ == "__main__":
    main()