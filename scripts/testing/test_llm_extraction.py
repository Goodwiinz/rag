#!/usr/bin/env python3
"""
Test LLM-based entity extraction with Azure OpenAI
"""

import sys
import os
import asyncio
from datetime import datetime

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from src.services.services.entity_extraction_service import EntityExtractionService
from src.services.knowledge_graph_service import KnowledgeGraphService

async def test_llm_extraction():
    """Test LLM extraction with sample text"""
    print("="*80)
    print("LLM ENTITY EXTRACTION TEST")
    print("="*80)
    print("\nInitializing services...")

    # Initialize services
    extraction_service = EntityExtractionService()
    kg_service = KnowledgeGraphService()

    # Sample text for testing
    sample_texts = [
        {
            "title": "Sample Research Abstract",
            "text": """
            Dr. Sarah Johnson from MIT Computer Science department published a groundbreaking paper
            on quantum computing in 2023. Her research focuses on developing new algorithms for
            quantum error correction. The paper was presented at the NeurIPS 2023 conference
            in New Orleans, Louisiana. Google and IBM researchers have cited this work extensively.
            Email: sarah.johnson@mit.edu
            """
        },
        {
            "title": "Company Announcement",
            "text": """
            OpenAI announced GPT-5, their latest language model, in San Francisco, California.
            CEO Sam Altman revealed that the model was trained using 10 trillion parameters.
            Microsoft, a key partner, will integrate GPT-5 into Azure AI services. The company
            expects to launch the product in Q2 2024. For more information, visit https://openai.com/gpt5
            """
        },
        {
            "title": "Academic Collaboration",
            "text": """
            Stanford University and Harvard Medical School established a joint research center
            for AI in healthcare. The center, led by Dr. Michael Chen and Dr. Emily Rodriguez,
            will focus on diagnostic AI applications. Initial funding of $50 million was provided
            by the Gates Foundation. The center is located at Stanford's main campus in Palo Alto, California.
            """
        }
    ]

    print(f"\nTesting LLM extraction on {len(sample_texts)} sample texts...")
    print("\nNote: LLM extraction will use Azure OpenAI with deployment:",
          extraction_service.llm_deployment_name if extraction_service.llm_client else "Not configured")

    for i, sample in enumerate(sample_texts, 1):
        print(f"\n" + "="*80)
        print(f"Test {i}: {sample['title']}")
        print("="*80)
        print(f"\nSample text:\n{sample['text'][:300]}...")

        # Extract entities using all methods
        print("\nExtracting entities...")
        entities = await extraction_service.extract_entities(
            text=sample['text'],
            document_id=f"test_doc_{i}",
            methods=['llm', 'spacy_ner', 'pattern_matching', 'rule_based']
        )

        print(f"\nFound {len(entities)} entities:")

        # Group by extraction method
        by_method = {}
        for entity in entities:
            method = entity.get('extraction_method', 'unknown')
            if method not in by_method:
                by_method[method] = []
            by_method[method].append(entity)

        # Display entities by method
        for method, method_entities in by_method.items():
            print(f"\n{method.upper()} Extraction ({len(method_entities)} entities):")
            for entity in method_entities[:5]:  # Show first 5
                print(f"  - {entity['name']} ({entity['entity_type']}) - "
                      f"confidence: {entity['confidence_score']:.2f}")
            if len(method_entities) > 5:
                print(f"  ... and {len(method_entities) - 5} more")

        # Store in knowledge graph if configured
        if kg_service and entities:
            print(f"\nStoring entities in knowledge graph...")
            try:
                document_id = f"llm_test_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                # Create document
                doc_data = {
                    'id': document_id,
                    'title': sample['title'],
                    'source': 'llm_extraction_test',
                    'created_at': datetime.now().isoformat()
                }

                # Store entities and document
                result = kg_service.store_entities(entities, doc_data)

                if result['success']:
                    print(f"  ✓ Stored {result['entities_stored']} entities")
                    print(f"  ✓ Created relationships: {result['relationships_created']}")
                else:
                    print(f"  ✗ Failed to store: {result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"  ✗ Error storing to knowledge graph: {str(e)}")

    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"1. LLM Extraction Status: {'✓ Enabled' if extraction_service.llm_client else '✗ Disabled'}")

    if extraction_service.llm_client:
        print(f"2. Azure OpenAI Deployment: {extraction_service.llm_deployment_name}")
        print("3. LLM extraction is ready to use with your knowledge graph!")
    else:
        print("\n2. LLM extraction is not configured. Please check your Azure OpenAI settings:")
        print("   - AZURE_OPENAI_CHAT_API_KEY")
        print("   - AZURE_OPENAI_CHAT_ENDPOINT")
        print("   - AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
        print("   - AZURE_OPENAI_CHAT_API_VERSION")

    print("\n4. Next steps:")
    print("   - Run document extraction with LLM enabled")
    print("   - Check extraction method distribution in Neo4j:")
    print("     MATCH (e:Entity) RETURN e.extraction_method, count(*)")

async def main():
    """Main function"""
    await test_llm_extraction()

if __name__ == "__main__":
    asyncio.run(main())