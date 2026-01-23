#!/usr/bin/env python3
"""
Example script demonstrating how to store knowledge graph data in Neo4j.

This script shows various ways to create entities and relationships:
1. Direct API calls via requests
2. Using the KnowledgeGraphService directly
3. Batch operations for efficiency
"""

import sys
import os
import requests
from typing import List, Dict

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service
from src.models.graph import (
    CreateEntityRequest, CreateRelationshipRequest,
    EntityType, RelationshipType, ExtractionMethod
)


# ============================================
# Method 1: Using the API (via HTTP requests)
# ============================================

def store_via_api():
    """
    Store knowledge graph data using the REST API.
    Requires authentication token.
    """
    BASE_URL = "http://localhost:8000"

    # You'll need to authenticate first to get a token
    # For this example, we'll assume you have a valid token
    auth_token = "your-auth-token-here"
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    # Create an entity
    entity_data = {
        "name": "John Doe",
        "entity_type": "PERSON",
        "confidence_score": 0.95,
        "extraction_method": "manual",
        "metadata": {
            "title": "Software Engineer",
            "company": "Tech Corp"
        }
    }

    response = requests.post(
        f"{BASE_URL}/knowledge-graph/entities",
        json=entity_data,
        headers=headers
    )

    if response.status_code == 200:
        entity = response.json()
        print(f"Created entity: {entity['id']} - {entity['name']}")
        return entity
    else:
        print(f"Error creating entity: {response.text}")
        return None


# ============================================
# Method 2: Using KnowledgeGraphService directly
# ============================================

def store_via_service():
    """
    Store knowledge graph data directly using the KnowledgeGraphService.
    This is useful for backend scripts and internal operations.
    """

    print("\n=== Storing Knowledge Graph Data ===\n")

    # Create entities
    entities = []

    # Entity 1: Person
    person_entity = CreateEntityRequest(
        name="Alice Johnson",
        entity_type=EntityType.PERSON,
        confidence_score=0.95,
        extraction_method=ExtractionMethod.MANUAL,
        metadata={
            "title": "Data Scientist",
            "email": "alice@example.com"
        }
    )
    person = knowledge_graph_service.create_entity(person_entity)
    entities.append(person)
    print(f"✓ Created person entity: {person.id} - {person.name}")

    # Entity 2: Organization
    org_entity = CreateEntityRequest(
        name="AI Research Lab",
        entity_type=EntityType.ORGANIZATION,
        confidence_score=0.98,
        extraction_method=ExtractionMethod.MANUAL,
        metadata={
            "industry": "Technology",
            "location": "San Francisco"
        }
    )
    org = knowledge_graph_service.create_entity(org_entity)
    entities.append(org)
    print(f"✓ Created organization entity: {org.id} - {org.name}")

    # Entity 3: Concept
    concept_entity = CreateEntityRequest(
        name="Machine Learning",
        entity_type=EntityType.CONCEPT,
        confidence_score=0.90,
        extraction_method=ExtractionMethod.MANUAL,
        metadata={
            "category": "Artificial Intelligence",
            "complexity": "Advanced"
        }
    )
    concept = knowledge_graph_service.create_entity(concept_entity)
    entities.append(concept)
    print(f"✓ Created concept entity: {concept.id} - {concept.name}")

    # Entity 4: Location
    location_entity = CreateEntityRequest(
        name="San Francisco",
        entity_type=EntityType.LOCATION,
        confidence_score=0.99,
        extraction_method=ExtractionMethod.MANUAL,
        metadata={
            "country": "USA",
            "state": "California"
        }
    )
    location = knowledge_graph_service.create_entity(location_entity)
    entities.append(location)
    print(f"✓ Created location entity: {location.id} - {location.name}")

    print(f"\n✓ Created {len(entities)} entities\n")

    # Create relationships
    relationships = []

    # Relationship 1: Person works for Organization
    works_for = CreateRelationshipRequest(
        source_entity_id=person.id,
        target_entity_id=org.id,
        relationship_type=RelationshipType.WORKS_FOR,
        strength=1.0,
        confidence_score=0.95,
        context="Alice Johnson works at AI Research Lab",
        evidence=["Employment record", "LinkedIn profile"],
        metadata={"start_date": "2020-01-15"}
    )
    rel1 = knowledge_graph_service.create_relationship(works_for)
    relationships.append(rel1)
    print(f"✓ Created relationship: {person.name} WORKS_FOR {org.name}")

    # Relationship 2: Organization located in Location
    located_in = CreateRelationshipRequest(
        source_entity_id=org.id,
        target_entity_id=location.id,
        relationship_type=RelationshipType.LOCATED_IN,
        strength=1.0,
        confidence_score=0.99,
        context="AI Research Lab is located in San Francisco",
        evidence=["Company website", "Business registration"],
        metadata={"verified": True}
    )
    rel2 = knowledge_graph_service.create_relationship(located_in)
    relationships.append(rel2)
    print(f"✓ Created relationship: {org.name} LOCATED_IN {location.name}")

    # Relationship 3: Person related to Concept
    related_to = CreateRelationshipRequest(
        source_entity_id=person.id,
        target_entity_id=concept.id,
        relationship_type=RelationshipType.RELATED_TO,
        strength=0.85,
        confidence_score=0.90,
        context="Alice Johnson specializes in Machine Learning",
        evidence=["Job title", "Published papers"],
        metadata={"expertise_level": "Expert"}
    )
    rel3 = knowledge_graph_service.create_relationship(related_to)
    relationships.append(rel3)
    print(f"✓ Created relationship: {person.name} RELATED_TO {concept.name}")

    print(f"\n✓ Created {len(relationships)} relationships\n")

    return entities, relationships


# ============================================
# Method 3: Batch Operations
# ============================================

def store_batch_data():
    """
    Store multiple entities and relationships efficiently using batch operations.
    """

    print("\n=== Batch Storing Knowledge Graph Data ===\n")

    # Prepare batch of entities
    entities_data = [
        {
            "name": "Bob Smith",
            "entity_type": "PERSON",
            "confidence_score": 0.92,
            "extraction_method": "spacy_ner",
            "metadata": {"role": "Manager"}
        },
        {
            "name": "TechStart Inc",
            "entity_type": "ORGANIZATION",
            "confidence_score": 0.94,
            "extraction_method": "spacy_ner",
            "metadata": {"industry": "SaaS"}
        },
        {
            "name": "Cloud Computing",
            "entity_type": "CONCEPT",
            "confidence_score": 0.88,
            "extraction_method": "llm_extraction",
            "metadata": {"domain": "Technology"}
        }
    ]

    # Create entities
    created_entities = []
    for entity_data in entities_data:
        entity_request = CreateEntityRequest(**entity_data)
        entity = knowledge_graph_service.create_entity(entity_request)
        created_entities.append(entity)
        print(f"✓ Created: {entity.name} ({entity.entity_type})")

    print(f"\n✓ Batch created {len(created_entities)} entities\n")

    return created_entities


# ============================================
# Method 4: From Document Processing
# ============================================

def extract_and_store_from_text():
    """
    Extract entities and relationships from text and store them.
    This simulates automatic extraction during document processing.
    """

    print("\n=== Extracting and Storing from Text ===\n")

    # Sample text
    text = """
    Sarah Williams is the CEO of InnovateTech Solutions, a company based in New York.
    She has extensive experience in Artificial Intelligence and leads a team of 50 engineers.
    The company recently partnered with MIT to research deep learning applications.
    """

    # In a real scenario, you would use NER or LLM to extract entities
    # For this example, we'll create them manually

    entities_to_create = [
        ("Sarah Williams", EntityType.PERSON),
        ("InnovateTech Solutions", EntityType.ORGANIZATION),
        ("New York", EntityType.LOCATION),
        ("Artificial Intelligence", EntityType.CONCEPT),
        ("MIT", EntityType.ORGANIZATION),
        ("deep learning", EntityType.CONCEPT),
    ]

    created_entities = {}
    for name, entity_type in entities_to_create:
        entity_request = CreateEntityRequest(
            name=name,
            entity_type=entity_type,
            confidence_score=0.85,
            extraction_method=ExtractionMethod.SPACY_NER,
            context=text,
            metadata={"source": "document_processing"}
        )
        entity = knowledge_graph_service.create_entity(entity_request)
        created_entities[name] = entity
        print(f"✓ Extracted: {name} ({entity_type})")

    # Create relationships based on text analysis
    relationships_to_create = [
        ("Sarah Williams", "InnovateTech Solutions", RelationshipType.WORKS_FOR),
        ("InnovateTech Solutions", "New York", RelationshipType.LOCATED_IN),
        ("Sarah Williams", "Artificial Intelligence", RelationshipType.RELATED_TO),
        ("InnovateTech Solutions", "MIT", RelationshipType.COLLABORATES_WITH),
    ]

    print()
    for source_name, target_name, rel_type in relationships_to_create:
        rel_request = CreateRelationshipRequest(
            source_entity_id=created_entities[source_name].id,
            target_entity_id=created_entities[target_name].id,
            relationship_type=rel_type,
            strength=0.8,
            confidence_score=0.85,
            context=text,
            metadata={"extracted_from": "text_analysis"}
        )
        rel = knowledge_graph_service.create_relationship(rel_request)
        print(f"✓ Linked: {source_name} → {rel_type} → {target_name}")

    print(f"\n✓ Extracted and stored knowledge graph from text\n")


# ============================================
# Querying the Knowledge Graph
# ============================================

def query_knowledge_graph():
    """
    Examples of querying the stored knowledge graph data.
    """

    print("\n=== Querying Knowledge Graph ===\n")

    # Get all entities
    with knowledge_graph_service.get_session() as session:
        result = session.run("MATCH (e:Entity) RETURN e.name as name, e.type as type")
        entities = list(result)

        print(f"Total entities in graph: {len(entities)}")
        for i, entity in enumerate(entities[:5], 1):
            print(f"  {i}. {entity['name']} ({entity['type']})")

        if len(entities) > 5:
            print(f"  ... and {len(entities) - 5} more")

    # Get all relationships
    with knowledge_graph_service.get_session() as session:
        result = session.run("""
            MATCH (a:Entity)-[r]->(b:Entity)
            RETURN a.name as source, type(r) as relationship, b.name as target
            LIMIT 10
        """)
        relationships = list(result)

        print(f"\nSample relationships:")
        for i, rel in enumerate(relationships, 1):
            print(f"  {i}. {rel['source']} → {rel['relationship']} → {rel['target']}")

    # Find entities by type
    print(f"\nFinding PERSON entities:")
    with knowledge_graph_service.get_session() as session:
        result = session.run("""
            MATCH (e:Entity)
            WHERE e.type = 'PERSON'
            RETURN e.name as name
        """)
        people = list(result)
        for person in people:
            print(f"  • {person['name']}")

    # Find connected entities
    print(f"\nFinding connections for first entity:")
    with knowledge_graph_service.get_session() as session:
        result = session.run("""
            MATCH (a:Entity)-[r]-(b:Entity)
            RETURN a.name as entity
            LIMIT 1
        """)
        first = result.single()
        if first:
            entity_name = first['entity']
            result = session.run("""
                MATCH (a:Entity {name: $name})-[r]-(b:Entity)
                RETURN b.name as connected, type(r) as via
            """, name=entity_name)
            connections = list(result)
            print(f"  {entity_name} is connected to:")
            for conn in connections:
                print(f"    • {conn['connected']} (via {conn['via']})")


# ============================================
# Main execution
# ============================================

def main():
    """Run all examples"""

    print("\n" + "="*60)
    print("Knowledge Graph Data Storage Examples")
    print("="*60)

    try:
        # Method 2: Using service directly (most common for backend)
        entities, relationships = store_via_service()

        # Method 3: Batch operations
        batch_entities = store_batch_data()

        # Method 4: From text extraction
        extract_and_store_from_text()

        # Query examples
        query_knowledge_graph()

        print("\n" + "="*60)
        print("✓ All examples completed successfully!")
        print("="*60 + "\n")

        print("Next steps:")
        print("1. Access Neo4j Browser at http://localhost:7474")
        print("2. Run Cypher queries to visualize your graph:")
        print("   MATCH (n) RETURN n LIMIT 25")
        print("3. Use the API endpoints to integrate with your application")
        print("4. Build search and recommendation features on top of the graph")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()