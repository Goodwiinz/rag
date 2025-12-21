import requests
import os

def reset_qdrant_http():
    url = os.getenv("QDRANT_URL", "https://e0600f6b-7662-45e3-8557-0100fe32bf44.us-east4-0.gcp.cloud.qdrant.io:6333")
    key = os.getenv("QDRANT_API_KEY", "c7p9y7CSIb8z-eHdb-I5D4iH05iE79iR_LbgQs5Cduy6F6dK0U5xrg")
    
    # Remove port if present for REST API sometimes? No, 6333 is usually good.
    # But Qdrant Cloud usually manages ports.
    
    # Try creating connection
    delete_url = f"{url}/collections/document_chunks"
    print(f"Deleting: {delete_url}")
    
    headers = {"api-key": key}
    response = requests.delete(delete_url, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

if __name__ == "__main__":
    reset_qdrant_http()
