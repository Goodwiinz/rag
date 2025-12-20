#!/usr/bin/env python3
"""Test EntityType.PAPER enum value and knowledge graph creation"""

import sys
import os
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from src.models.graph import EntityType, CreateEntityRequest, ExtractionMethod
from src.services.knowledge_graph_service import KnowledgeGraphService

# Test enum value
print(f"EntityType.PAPER value: '{EntityType.PAPER.value}'")
print(f"EntityType.CONCEPT value: '{EntityType.CONCEPT.value}'")
print(f"EntityType.DOCUMENT value: '{EntityType.DOCUMENT.value}'")

# Test knowledge graph creation
try:
    kg_service = KnowledgeGraphService()

    # Create a test paper entity
    test_request = CreateEntityRequest(
        entity_type=EntityType.PAPER,
        name="Test Paper Entity",
        confidence_score=0.9,
        extraction_method=ExtractionMethod.SPACY_NER,
        metadata={
            "test": True,
            "source": "test_script"
        }
    )

    print(f"\nCreating test paper entity...")
    entity = kg_service.create_entity(test_request)

    if entity:
        print(f"✅ Successfully created paper entity: {entity.id}")
        print(f"   Type: {entity.entity_type}")
        print(f"   Name: {entity.name}")
    else:
        print("❌ Failed to create paper entity")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()