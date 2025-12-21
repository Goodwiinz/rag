env_content = """# Application
APP_NAME="Multimodal Enterprise RAG System"
VERSION="1.0.0"
ENVIRONMENT="development"
DEBUG=True
SECRET_KEY="dev_secret_key_must_be_very_long_to_pass_validation_32_chars"

# Database
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/multimodal_rag"
REDIS_URL="redis://localhost:6379"

# Neo4j Configuration
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="password"

# Qdrant Configuration (LOCAL)
QDRANT_URL="http://localhost:6333"
QDRANT_API_KEY=""

# Azure OpenAI Configuration (Embeddings)
AZURE_OPENAI_API_KEY="7awsW9wUrULKH9CLPkeh1oeaeeGmKvIotw8HSYjVtjMcIgj0NqyLJQQJ99BIACYeBjFXJ3w3AAABACOG5UHM"
AZURE_OPENAI_ENDPOINT="https://goodwiinzapi.cognitiveservices.azure.com/"
AZURE_OPENAI_EMBEDDING_ENDPOINT="https://goodwiinzapi.cognitiveservices.azure.com/openai/deployments/text-embedding-3-small/embeddings?api-version=2023-05-15"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME="text-embedding-3-small"
AZURE_OPENAI_API_VERSION="2023-05-15"

# Azure OpenAI Configuration (Chat - for LLM Extraction)
AZURE_OPENAI_CHAT_API_KEY="Fy2YKNsjf9evt81MSkLHoFKuFKF95PfadS93Io19jmBqrmgFZoXcJQQJ99BJACHYHv6XJ3w3AAAAACOGmjzy"
AZURE_OPENAI_CHAT_ENDPOINT="https://abdo9-mh9qxzwu-eastus2.cognitiveservices.azure.com/"
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME="gpt-5-nano"
AZURE_OPENAI_CHAT_API_VERSION="2024-06-01"

# Embedding Provider
EMBEDDING_PROVIDER="azure_openai"
EMBEDDING_MODEL="text-embedding-3-small"
"""

with open(".env", "w") as f:
    f.write(env_content)

print("Successfully rewrote .env with clean configuration.")
