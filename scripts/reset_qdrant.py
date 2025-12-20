from qdrant_client import QdrantClient
import os

def reset_qdrant():
    url = os.getenv("QDRANT_URL", "https://e0600f6b-7662-45e3-8557-0100fe32bf44.us-east4-0.gcp.cloud.qdrant.io:6333")
    key = os.getenv("QDRANT_API_KEY", "c7p9y7CSIb8z-eHdb-I5D4iH05iE79iR_LbgQs5Cduy6F6dK0U5xrg")
    
    client = QdrantClient(url=url, api_key=key)
    
    collection_name = "document_chunks"
    try:
        client.delete_collection(collection_name)
        print(f"Deleted collection: {collection_name}")
    except Exception as e:
        print(f"Error deleting collection {collection_name}: {e}")

if __name__ == "__main__":
    reset_qdrant()
