from qdrant_client import QdrantClient
import os
import json

# Try localhost first
client = QdrantClient(url="http://localhost:6333")

try:
    collections = client.get_collections()
    print(f"Collections: {[c.name for c in collections.collections]}")
    
    for collection in collections.collections:
        name = collection.name
        print(f"\n--- Inspeting Collection: {name} ---")
        try:
            # Scroll a few points
            points, _ = client.scroll(
                collection_name=name,
                limit=3,
                with_payload=True,
                with_vectors=False
            )
            for p in points:
                print(f"ID: {p.id}")
                print(f"Payload keys: {list(p.payload.keys())}")
                print(f"Payload sample: {json.dumps(p.payload, indent=2, default=str)[:200]}...")
        except Exception as e:
            print(f"Error inspecting {name}: {e}")

except Exception as e:
    print(f"Could not connect to Qdrant: {e}")
