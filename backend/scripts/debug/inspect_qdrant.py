import requests
import json

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "document_chunks"  # Based on VectorCollectionType.DOCUMENT_CHUNKS


def inspect_collection():
    # Get collection info
    resp = requests.get(f"{QDRANT_URL}/collections/{COLLECTION_NAME}")
    if resp.status_code != 200:
        print(f"Error getting collection info: {resp.text}")
        return

    print("Collection Info:")
    print(json.dumps(resp.json(), indent=2))

    # Scroll points to see payload
    resp = requests.post(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
        json={"limit": 1, "with_payload": True, "with_vector": False},
    )

    if resp.status_code != 200:
        print(f"Error scrolling points: {resp.text}")
        return

    print("\nSample Point:")
    print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
    inspect_collection()
