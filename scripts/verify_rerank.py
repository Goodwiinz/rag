
import requests
import json
import sys

def verify_reranking():
    url = "http://localhost:8000/api/v1/search/public/hybrid"
    payload = {
        "query": "machine learning models",
        "top_n": 3,
        "include_rerank": True
    }
    
    print(f"Sending request to {url}...")
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            return

        data = response.json()
        results = data.get("results", [])
        
        if not results:
            print("⚠️  No results found. Cannot verify reranking.")
            return

        print(f"Found {len(results)} results.")
        
        # Check first result for cohere_score
        first_result = results[0]
        metadata = first_result.get("metadata", {})
        
        if "cohere_score" in metadata:
            print("✅ SUCCESS: 'cohere_score' found in metadata.")
            print(f"   Score: {metadata['cohere_score']}")
            print("   Reranking IS working.")
        else:
            print("❌ FAILURE: 'cohere_score' NOT found in metadata.")
            print("   Reranking might be disabled or failing.")
            print(f"   Metadata keys: {list(metadata.keys())}")

    except Exception as e:
        print(f"❌ Error connecting to backend: {e}")

if __name__ == "__main__":
    verify_reranking()
