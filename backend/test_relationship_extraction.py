
import asyncio
import logging
from typing import Dict, Any, List
# Mock the dependencies to just test the logic, or use real import
from src.services.arxiv_kg_integration import ArXivKnowledgeGraphIntegration
from src.services.azure_openai_service import azure_openai_service

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_relationship_extraction():
    # If azure service is not available, we can't test real LLM call
    if not azure_openai_service.is_chat_available():
        print("Azure OpenAI not available, skipping real test.")
        return

    # Mock service using Duck typing or Real one if possible
    # But ArXivKnowledgeGraphIntegration requires kg_service and vector_service in init
    # We can perform a partial test by instantiating it with mocks
    
    class MockKGService:
        def search_entities(self, query, limit): return []
        def create_entity(self, name, type, metadata): pass
        def create_relationship(self, source, target, relation, props): pass
        
    class MockVectorService:
        pass
        
    integration = ArXivKnowledgeGraphIntegration(config={})
    # Manually inject mocks if needed by internal methods, 
    # though _extract_semantic_relations_with_llm mainly uses global azure_openai_service
    integration.kg_service = MockKGService()
    # integration.vector_service = MockVectorService() # Not used in extraction logic directly
    
    # Paper Data
    paper = {
        'id': '2512.15687v1',
        'title': 'Can LLMs Guide Their Own Exploration? Gradient-Guided Reinforcement Learning for LLM Reasoning',
        'abstract': 'We propose Gradient-Guided Reinforcement Learning (G2RL), a framework that leverages the gradients of the policy. We evaluate G2RL on the MATH500 dataset and compare it with PPO.',
        'authors': ['Zhenwen Liang'],
        'categories': ['cs.LG']
    }
    
    # Pre-extracted entities (simulating what _extract_entities_from_paper would return)
    entities = [
        {'text': 'G2RL', 'type': 'method', 'confidence': 0.9},
        {'text': 'MATH500', 'type': 'dataset', 'confidence': 0.9},
        {'text': 'PPO', 'type': 'method', 'confidence': 0.9},
        {'text': 'Gradient-Guided Reinforcement Learning', 'type': 'method', 'confidence': 0.9}
    ]
    
    print("Testing Semantic Relationship Extraction...")
    try:
        # We call the method directly to test logic
        relationships = await integration._extract_relationships_from_paper(paper, entities)
        
        print(f"\nExtracted {len(relationships)} total relationships.")
        
        semantic_rels = [r for r in relationships if r.get('extraction_source') == 'llm_semantic']
        print(f"Found {len(semantic_rels)} semantic relationships:")
        
        for rel in semantic_rels:
            print(f"  {rel['source']['text']} --[{rel['relation']}]--> {rel['target']['text']}")
            
        if len(semantic_rels) > 0:
            print("\nSUCCESS: Semantic analysis engine is working.")
        else:
            print("\nFAILURE: No semantic relationships found (LLM might have failed or found none).")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_relationship_extraction())
