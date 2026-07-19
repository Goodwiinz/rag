from qdrant_client import QdrantClient

client = QdrantClient("http://localhost:6333")
print(f"Client type: {type(client)}")
print(f"Has search: {hasattr(client, 'search')}")
print(f"Dir: {dir(client)}")
