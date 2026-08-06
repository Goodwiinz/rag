from qdrant_client import QdrantClient
import time

client = QdrantClient(host="localhost", port=6333)

def check_collection():
    try:
        count = client.count(collection_name="document_chunks")
        print(f"Count: {count}")
    except Exception as e:
        print(f"Error getting count: {e}")

    # Use raw HTTP to scroll if client fails
    import requests
    response = requests.post("http://localhost:6333/collections/document_chunks/points/scroll", json={"limit": 1, "with_vector": True})
    print(response.text[:500])

check_collection()
