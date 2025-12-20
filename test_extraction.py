#!/usr/bin/env python3
"""Test the arxiv extraction endpoint directly"""

import requests
import json

# API endpoint
url = "http://localhost:8000/api/v1/arxiv/local/extract-local-features"

# Test request payload
payload = {
    "extract_topics": True,
    "extract_keyphrases": True,
    "extract_summaries": True,
    "update_knowledge_graph": True,  # This is critical
    "extract_images": False,
    "extract_tables": False,
    "extract_references": True
}

try:
    print("Sending extraction request...")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    response = requests.post(url, json=payload)

    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200:
        data = response.json()
        print(f"\nProcessed {data.get('processed_count', 0)} files")
        print(f"Total files found: {data.get('total_files_found', 0)}")

    else:
        print(f"Error: {response.status_code}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()