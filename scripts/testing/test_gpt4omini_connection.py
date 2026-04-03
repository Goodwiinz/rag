#!/usr/bin/env python3
"""
Test GPT-4o-mini connection to Azure OpenAI
"""

import sys
import os
from openai import AzureOpenAI

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from src.core.config import settings

def test_gpt4o_mini():
    """Test connection to GPT-4o-mini deployment"""
    print("="*80)
    print("GPT-4o-mini CONNECTION TEST")
    print("="*80)
    print("\nTesting Azure OpenAI connection with GPT-4o-mini...")

    try:
        # Initialize client
        # Use the specific API key for the goodwiinzapi endpoint
        client = AzureOpenAI(
            api_key=os.environ.get("AZURE_OPENAI_API_KEY", "your_azure_openai_key_here"),
            azure_endpoint="https://goodwiinzapi.cognitiveservices.azure.com/",
            api_version="2025-01-01-preview"
        )

        # Test API call
        print("\nSending test request...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France? Keep it brief."}
            ],
            temperature=0.7,
            max_tokens=100
        )

        # Display result
        answer = response.choices[0].message.content
        print(f"\n✅ SUCCESS! GPT-4o-mini responded:")
        print(f"   {answer}")

        # Test entity extraction capability
        print("\n" + "="*40)
        print("TESTING ENTITY EXTRACTION CAPABILITY")
        print("="*40)

        entity_test_prompt = """Extract entities from this text:

        "Dr. Sarah Johnson from MIT published a paper on quantum computing at NeurIPS 2023.
         Contact her at sarah@mit.edu. The research was funded by a $1M grant from NSF."

        Return JSON with entities and their types."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an entity extraction expert. Always return valid JSON."},
                {"role": "user", "content": entity_test_prompt}
            ],
            temperature=0.1,
            max_tokens=300
        )

        result = response.choices[0].message.content
        print(f"\nEntity extraction result:")
        print(f"   {result}")

        print("\n" + "="*80)
        print("✅ GPT-4o-mini is ready for RAG and entity extraction!")
        print("="*80)
        print("\nConfiguration details:")
        print(f"  Endpoint: https://goodwiinzapi.cognitiveservices.azure.com/")
        print(f"  Deployment: gpt-4o-mini")
        print(f"  API Version: 2025-01-01-preview")
        print(f"  Model ID: gpt-4o-mini (2024-07)")

        print("\nBenefits for your RAG system:")
        print("  • Fast response times (≈2-3x faster than GPT-4)")
        print("  • 128K context window")
        print("  • 10x cheaper than GPT-4")
        print("  • Excellent at understanding technical content")
        print("  • Strong multilingual capabilities")

    except Exception as e:
        print(f"\n❌ ERROR: Failed to connect to GPT-4o-mini")
        print(f"   {str(e)}")
        print("\nPlease check:")
        print("  1. API key is correct")
        print("  2. Deployment name is exactly 'gpt-4o-mini'")
        print("  3. Region is correct (likely East US 2)")
        print("  4. API version is supported")

if __name__ == "__main__":
    test_gpt4o_mini()