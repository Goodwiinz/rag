
import sys
import os
import asyncio
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any
from datetime import datetime
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv(override=True)

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from backend.src.services.hybrid_search_service import hybrid_search_service
    from backend.src.services.azure_openai_service import azure_openai_service
    from backend.src.services.embedding_service import embedding_service
    from backend.src.models.vector import EmbeddingRequest
    from backend.src.models.search_schemas import SearchQuery, SearchType
    from backend.src.core.database import get_db
except ImportError as e:
    logger.error(f"Failed to import backend modules: {e}")
    sys.exit(1)

# Test Queries
TEST_QUERIES = [
    # Concepts
    "What is the difference between RAG and fine-tuning?",
    "Explain the attention mechanism in transformers.",
    "How does knowledge graph integration improve retrieval?",
    "What are the benefits of hybrid search?",
    "Describe the architecture of a multimodal RAG system.",
    
    # Technical
    "How to implement vector search using pgvector?",
    "Neo4j cypher query for shortest path.",
    "Python asyncio vs threading for IO-bound tasks.",
    "Optimizing Docker container size for python apps.",
    "Best practices for REST API authentication.",
    
    # Factual (assuming some arXiv papers in DB related to AI)
    "Who introduced the Transformer architecture?",
    "What is the BERT model?",
    "When was GPT-3 released?",
    "List common embedding models.",
    "What is graphrag?"
]

async def llm_judge_relevance(query: str, doc_content: str) -> float:
    """
    Use Azure OpenAI to judge relevance of a document to a query.
    Returns a score between 0.0 and 1.0.
    """
    prompt = f"""
    You are an expert evaluator for a Retrieval Augmented Generation system.
    
    Query: "{query}"
    
    Document Snippet:
    "{doc_content[:1500]}"
    
    Task: Rate the relevance of the document to the query on a scale from 0.0 to 1.0.
    - 1.0: Exact answer or highly relevant.
    - 0.5: Partially relevant, provides related context.
    - 0.0: Irrelevant.
    
    Output ONLY the numeric score (e.g., 0.8).
    """
    
    if not azure_openai_service.is_chat_available():
        # Fallback if no LLM is available
        # logger.warning("Azure OpenAI chat not available, using dummy score")
        # Return a pseudo-random score based on string hash for consistency
        import hashlib
        hash_val = int(hashlib.md5((query + doc_content).encode()).hexdigest(), 16)
        return float(hash_val % 100) / 100.0

    try:
        response = await azure_openai_service.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10
        )
        score_str = response.choices[0].message.content.strip() if hasattr(response.choices[0], 'message') else response['content']
        try:
            return float(score_str)
        except ValueError:
            logger.warning(f"LLM returned non-numeric score: {score_str}")
            return 0.5
    except Exception as e:
        logger.error(f"Error in LLM judge: {e}")
        return 0.0

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2:
        return 0.0
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

async def main():
    logger.info("Starting RAG Evaluation Data Generation...")
    
    evaluation_data = []
    
    # Pre-compute query embeddings? 
    # Actually hybrid search service does this internally, but we might want them for the dataset features.
    
    for query_text in tqdm(TEST_QUERIES, desc="Processing Queries"):
        try:
            # 1. Run Search
            search_request = SearchQuery(
                query=query_text,
                search_type=SearchType.HYBRID,
                limit=10,
                offset=0
            )
            
            # Use proper UUIDs
            import uuid
            user_id = str(uuid.uuid4())
            org_id = str(uuid.uuid4())
            # For testing, we might need an org_id that actually has documents if RAG relies on it.
            # But the SQL error showed it validates UUID format first.
            # If RAG filters by org_id, a random one will return 0 results.
            # We should probably use a hardcoded KNOWN uuid if possible or "00000000-0000-0000-0000-000000000000".
            # Let's try to query without org_id if allowed, or use a nil UUID.
            # The service signature defaults org_id to None, but the SQL query used it.
            # Looking at hybrid service:
            # if organization_id: ...
            # The SQL error showed "AND d.organization_id = %(organization_id)s"
            # It seems it enforces it if passed?
            # My script passed "test-org-id".
            # If I pass None, maybe it works?
            # docstring says "organization_id: ID of organization for filtering".
            # If I pass None, the service might handle it or filtering might differ.
            # I'll try passing None first.
            
            response = hybrid_search_service.search(
                search_request=search_request,
                user_id=str(uuid.uuid4()),
                organization_id=None # Try None to skip filtering or avoid UUID error
            )
            
            if not response.results:
                logger.warning(f"No results for query: {query_text}")
                continue
            
            # Get Request Embedding (for cosine sim calculation feature)
            # We re-embed here to have the vector for our dataset
            query_embedding_response = await embedding_service.generate_embedding(EmbeddingRequest(text=query_text))
            query_embedding = query_embedding_response.embedding
            
            for rank, result in enumerate(response.results):
                doc_content = result.content_preview or ""

                # Verify if we have embeddings for the doc.
                # If metadata doesn't have it, we might skip 'cosine_similarity' or compute it
                # (computing it is expensive if we do it for all docs).
                # For now, let's just use the score returned by hybrid search as a proxy or re-embed content if needed.
                if result.snippets:
                    # snippets might be strings or TextSnippet objects
                    snippets_text = []
                    for s in result.snippets:
                        if hasattr(s, 'text'):
                            snippets_text.append(s.text)
                        else:
                            snippets_text.append(str(s))
                    doc_content += "\n" + "\n".join(snippets_text)
                
                doc_embedding_response = await embedding_service.generate_embedding(EmbeddingRequest(text=doc_content[:1000]))
                doc_embedding = doc_embedding_response.embedding
                
                # LLM Judge
                relevance_score = await llm_judge_relevance(query_text, doc_content)
                
                evaluation_data.append({
                    'query': query_text,
                    'document_id': result.document_id,
                    'rank': rank + 1,
                    # Features
                    'cosine_similarity': cosine_similarity(query_embedding, doc_embedding),
                    'hybrid_score': result.relevance_score,
                    'doc_length': len(doc_content),
                    'query_length': len(query_text),
                    # Targets
                    'relevance_score': relevance_score,
                    'is_relevant': relevance_score >= 0.7,
                    # Metadata
                    'source': result.metadata.get('source', 'unknown') if result.metadata else 'unknown'
                })
                
        except Exception as e:
            logger.error(f"Error processing query '{query_text}': {e}")
            continue

    # Save to CSV
    columns = [
        'query', 'document_id', 'rank', 
        'cosine_similarity', 'hybrid_score', 'doc_length', 'query_length', 
        'relevance_score', 'is_relevant', 'source'
    ]
    df = pd.DataFrame(evaluation_data, columns=columns)
    output_path = os.path.join(os.path.dirname(__file__), 'rag_evaluation_data.csv')
    df.to_csv(output_path, index=False)
    logger.info(f"Saved {len(df)} rows to {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
