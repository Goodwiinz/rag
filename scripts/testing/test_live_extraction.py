#!/usr/bin/env python3
"""Test the live extraction endpoint with proper authentication"""

import requests
import json
import time

# First, let's try to login
login_url = "http://localhost:8000/api/v1/auth/login"
login_data = {
    "email": "demo@multimodal-rag.com",
    "password": "demo123"
}

print("Attempting to login...")
try:
    login_response = requests.post(login_url, json=login_data)

    if login_response.status_code == 200:
        login_result = login_response.json()
        token = login_result.get("access_token")
        print(f"✅ Login successful! Token: {token[:20]}...")

        # Now call the extraction endpoint
        extract_url = "http://localhost:8000/api/v1/arxiv/local/extract-local-features"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "paper_ids": None,
            "extract_entities": True,
            "extract_topics": True,
            "extract_citations": False,
            "extract_keyphrases": True,
            "extract_summaries": True,
            "process_full_content": False,  # Set to False to avoid full processing
            "update_knowledge_graph": True,
            "extract_images": False,
            "extract_tables": False,
            "extract_references": True
        }

        print("\nSending extraction request...")
        response = requests.post(extract_url, json=payload, headers=headers)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Extraction started!")
            print(f"   Files found: {result.get('total_files_found', 0)}")
            print(f"   Processed: {result.get('processed_count', 0)}")

            # Wait and check results
            print("\nWaiting 10 seconds for background processing...")
            time.sleep(10)

            # Check knowledge graph
            print("\nChecking knowledge graph updates...")
            import sys
            sys.path.append('/Users/goodwiinz/development/RAG_system/backend')
            from src.services.knowledge_graph_service import KnowledgeGraphService

            kg = KnowledgeGraphService()
            docs = kg.search_entities("ArXiv Paper", limit=20)

            print(f"Found {len(docs)} document entities")
            for doc in docs[-5:]:  # Show last 5
                print(f"   - {doc.name[:60]}...")

        else:
            print(f"❌ Extraction failed: {response.text}")
    else:
        print(f"❌ Login failed: {login_response.text}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()