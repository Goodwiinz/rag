from qdrant_client import QdrantClient
client = QdrantClient(host="localhost", port=6333)
print(f"HTTP Client type: {type(client.http)}")
print(f"Points API type: {type(client.http.points_api)}")
print("Points API methods:")
print(dir(client.http.points_api))
