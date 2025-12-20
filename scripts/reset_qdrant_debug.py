from qdrant_client import QdrantClient
import os

def reset_qdrant_debug():
    url = "https://e0600f6b-7662-45e3-8557-0100fe32bf44.us-east4-0.gcp.cloud.qdrant.io:6333"
    key = "c7p9y7CSIb8z-eHdb-I5D4iH05iE79iR_LbgQs5Cduy6F6dK0U5xrg"
    
    print(f"Connecting to {url}")
    client = QdrantClient(url=url, api_key=key, check_compatibility=False)
    
    try:
        collections = client.get_collections()
        print("Existing collections:")
        for c in collections.collections:
            print(f" - {c.name}")
            
        if any(c.name == "document_chunks" for c in collections.collections):
            print("Deleting document_chunks...")
            client.delete_collection("document_chunks")
            print("Deleted.")
        else:
            print("document_chunks not found.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    reset_qdrant_debug()
