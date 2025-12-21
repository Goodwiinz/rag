
import asyncio
import logging
import json
from src.services.arxiv_kg_integration import ArXivKnowledgeGraphIntegration
from src.services.azure_openai_service import azure_openai_service

logging.basicConfig(level=logging.INFO)

async def test_extraction_debug():
    integration = ArXivKnowledgeGraphIntegration(config={})
    
    # Paper: Multi-Modal Semantic Communication (2512.15691v1)
    # We need to simulate the exact input
    context_text = """Multi-Modal Semantic Communication
    Multi-modal semantic communication (MSC) is a promising technology for 6G networks. 
    However, existing MSC methods mainly focus on the semantic information of a single modality, ignoring the correlation between different modalities. 
    To address this issue, we propose a Multi-Modal Semantic Communication method (MMSC) based on deep learning.
    """
    
    # Assume we have these entities from DB
    entities = [
        {'text': 'Multi-modal semantic communication', 'type': 'CONCEPT'},
        {'text': 'MSC', 'type': 'CONCEPT'},
        {'text': '6G', 'type': 'CONCEPT'},
        {'text': 'deep learning', 'type': 'CONCEPT'},
        {'text': 'MMSC', 'type': 'CONCEPT'}
    ]
    
    print(f"Entities: {[e['text'] for e in entities]}")
    
    # Call internal LLM method directly
    # Note: ArXivKnowledgeGraphIntegration methods are instance methods.
    try:
        rels = await integration._extract_semantic_relations_with_llm(context_text, entities)
        print(f"Extracted: {json.dumps(rels, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_extraction_debug())
