#!/usr/bin/env python3
"""Test EntityType.DOCUMENT enum value and knowledge graph creation"""

import sys
import os
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from src.models.graph import EntityType, CreateEntityRequest, ExtractionMethod
from src.services.knowledge_graph_service import KnowledgeGraphService

# Test enum value
print(f"EntityType.DOCUMENT value: '{EntityType.DOCUMENT.value}'")
print(f"EntityType.CONCEPT value: '{EntityType.CONCEPT.value}'")

# Test knowledge graph creation
try:
    kg_service = KnowledgeGraphService()

    # Create a test document entity
    test_request = CreateEntityRequest(
        entity_type=EntityType.DOCUMENT,
        name="Test Document Entity",
        confidence_score=0.9,
        extraction_method=ExtractionMethod.SPACY_NER,
        metadata={
            "test": True,
            "source": "test_script",
            "paper_id": "test_paper_123"
        }
    )

    print(f"\nCreating test document entity...")
    entity = kg_service.create_entity(test_request)

    if entity:
        print(f"✅ Successfully created document entity: {entity.id}")
        print(f"   Type: {entity.entity_type}")
        print(f"   Name: {entity.name}")

        # Now create a concept and relationship
        concept_request = CreateEntityRequest(
            entity_type=EntityType.CONCEPT,
            name="Test Concept",
            confidence_score=0.8,
            extraction_method=ExtractionMethod.SPACY_NER,
            metadata={
                "test": True
            }
        )

        concept = kg_service.create_entity(concept_request)

        if concept:
            print(f"✅ Successfully created concept entity: {concept.id}")

            # Create relationship
            from src.models.graph import CreateRelationshipRequest, RelationshipType

            rel_request = CreateRelationshipRequest(
                source_entity_id=entity.id,
                target_entity_id=concept.id,
                relationship_type=RelationshipType.RELATED_TO,
                strength=0.8,
                confidence_score=0.8
            )

            relationship = kg_service.create_relationship(rel_request)

            if relationship:
                print(f"✅ Successfully created relationship: {relationship.id}")
            else:
                print("❌ Failed to create relationship")

    else:
        print("❌ Failed to create document entity")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()