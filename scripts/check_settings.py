import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

from backend.src.core.config import settings
from backend.src.services.azure_openai_service import azure_openai_service
from backend.src.services.embedding_service import embedding_service

print(f"AZURE_OPENAI_API_KEY: {'*' * 5 if settings.AZURE_OPENAI_API_KEY else 'None'}")
print(f"AZURE_OPENAI_ENDPOINT: {settings.AZURE_OPENAI_ENDPOINT}")
print(f"AZURE_OPENAI_EMBEDDING_ENDPOINT: {settings.AZURE_OPENAI_EMBEDDING_ENDPOINT}")
print(f"AZURE_OPENAI_CHAT_ENDPOINT: {settings.AZURE_OPENAI_CHAT_ENDPOINT}")
print(f"Embedding Provider: {embedding_service.embedding_provider}")
print(f"Is Embedding Available: {azure_openai_service.is_embedding_available()}")
print(f"Is Chat Available: {azure_openai_service.is_chat_available()}")
