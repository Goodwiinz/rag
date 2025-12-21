import os
import requests
# from dotenv import load_dotenv

# Load environment variables
# load_dotenv()

def reset_qdrant_properly():
    # Hardcoded fallback as .env loading failed
    url = os.getenv("QDRANT_URL", "https://e0600f6b-7662-45e3-8557-0100fe32bf44.us-east4-0.gcp.cloud.qdrant.io")
    key = os.getenv("QDRANT_API_KEY", "c7p9y7CSIb8z-eHdb-I5D4iH05iE79iR_LbgQs5Cduy6F6dK0U5xrg")
    
    if not url or not key:
        print("Error: Missing QDRANT_URL or QDRANT_API_KEY")
        return

    print(f"Targeting Qdrant at: {url}")
    
    # Ensure URL doesn't end with slash
    url = url.rstrip('/')
    
    # Collection name
    collection_name = "document_chunks"
    
    # Construct DELETE URL
    delete_url = f"{url}/collections/{collection_name}"
    
    headers = {
        "api-key": key,
        "Content-Type": "application/json"
    }
    
    print(f"Sending DELETE to {delete_url}")
    try:
        response = requests.delete(delete_url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("Collection deleted successfully.")
        elif response.status_code == 404:
            print("Collection not found (already deleted?).")
        else:
            print("Failed to delete collection.")
            
    except Exception as e:
        print(f"Exception during request: {e}")

if __name__ == "__main__":
    reset_qdrant_properly()
