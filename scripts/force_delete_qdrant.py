import sys
import os
import asyncio

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.src.services.vector_service import vector_service

def force_delete():
    print("Deleting document_chunks collection using service...")
    success = vector_service.delete_collection("document_chunks")
    print(f"Delete success: {success}")

if __name__ == "__main__":
    force_delete()
