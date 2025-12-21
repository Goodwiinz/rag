#!/usr/bin/env python3
"""
Neo4j Data Management Script
For cleaning, updating, and managing Neo4j knowledge graph data
"""

import os
import sys
import argparse
from typing import List, Dict, Any

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from src.services.knowledge_graph_service import KnowledgeGraphService
from src.models.graph import EntityType


def view_stats(kg_service):
    """View current database statistics"""
    print("\n=== Neo4j Database Statistics ===")

    # Get analytics
    analytics = kg_service.get_graph_analytics()
    print(f"Total Entities: {analytics.total_entities}")
    print(f"Total Relationships: {analytics.total_relationships}")

    print("\nEntity Types:")
    for entity_type, count in analytics.entity_type_counts.items():
        print(f"  {entity_type}: {count}")

    print("\nRelationship Types:")
    for rel_type, count in analytics.relationship_type_counts.items():
        print(f"  {rel_type}: {count}")

    print("\nHealth Status:")
    health = kg_service.get_health_status()
    print(f"Status: {health.status}")
    print(f"Response Time: {health.response_time_ms:.2f}ms")


def clear_all_data(kg_service, confirm=False):
    """Delete ALL data from Neo4j"""
    if not confirm:
        response = input("\n⚠️  WARNING: This will delete ALL data in Neo4j. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Operation cancelled.")
            return

    print("\nDeleting all data...")

    try:
        with kg_service.get_session() as session:
            # Delete all nodes and relationships
            result = session.run("MATCH (n) DETACH DELETE n RETURN count(n) as deleted_count")
            deleted = result.single()["deleted_count"]
            print(f"✅ Deleted {deleted} nodes")
    except Exception as e:
        print(f"❌ Error: {e}")


def clear_arxiv_data(kg_service, confirm=False):
    """Delete only ArXiv paper entities"""
    if not confirm:
        response = input("\nDelete all ArXiv paper entities? (yes/no): ")
        if response.lower() != 'yes':
            print("Operation cancelled.")
            return

    print("\nDeleting ArXiv paper entities...")

    try:
        with kg_service.get_session() as session:
            # Delete by name pattern
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.name STARTS WITH 'ArXiv Paper'
                DETACH DELETE e
                RETURN count(e) as deleted_count
            """)
            deleted = result.single()["deleted_count"]
            print(f"✅ Deleted {deleted} ArXiv entities")
    except Exception as e:
        print(f"❌ Error: {e}")


def update_entity_metadata(kg_service, paper_id: str, updates: Dict[str, Any]):
    """Update metadata for a specific entity"""
    print(f"\nUpdating entity for paper: {paper_id}")

    try:
        # Find the entity
        entities = kg_service.search_entities(f"ArXiv Paper: {paper_id}")
        if not entities:
            print(f"❌ No entity found for paper: {paper_id}")
            return

        entity = entities[0]
        print(f"Found entity: {entity.name}")

        # Update the entity
        from src.models.graph import UpdateEntityRequest
        update_request = UpdateEntityRequest(metadata=updates)
        updated_entity = kg_service.update_entity(entity.id, update_request)

        if updated_entity:
            print(f"✅ Updated entity metadata")
        else:
            print("❌ Failed to update entity")

    except Exception as e:
        print(f"❌ Error: {e}")


def list_arxiv_entities(kg_service, limit=20):
    """List all ArXiv paper entities"""
    print(f"\nListing up to {limit} ArXiv paper entities:")

    try:
        entities = kg_service.get_all_entities(limit=limit)
        arxiv_entities = [e for e in entities if "ArXiv Paper" in e.name]

        for entity in arxiv_entities:
            print(f"\n📄 {entity.name}")
            print(f"   ID: {entity.id}")
            print(f"   Type: {entity.entity_type}")
            if entity.metadata:
                paper_id = entity.metadata.get('paper_id', 'N/A')
                topics = entity.metadata.get('topics', [])
                print(f"   Paper ID: {paper_id}")
                if topics:
                    print(f"   Topics: {', '.join(topics)}")

    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Neo4j Data Management")
    parser.add_argument('--action', choices=['stats', 'clear-all', 'clear-arxiv', 'list', 'update'],
                        required=True, help="Action to perform")
    parser.add_argument('--paper-id', help="Paper ID for update action")
    parser.add_argument('--confirm', action='store_true', help="Skip confirmation prompts")

    args = parser.parse_args()

    # Initialize knowledge graph service
    kg_service = KnowledgeGraphService()
    kg_service._connect()

    try:
        if args.action == 'stats':
            view_stats(kg_service)

        elif args.action == 'clear-all':
            clear_all_data(kg_service, args.confirm)

        elif args.action == 'clear-arxiv':
            clear_arxiv_data(kg_service, args.confirm)

        elif args.action == 'list':
            list_arxiv_entities(kg_service)

        elif args.action == 'update':
            if not args.paper_id:
                print("❌ --paper-id required for update action")
                return

            # Example update - you can modify this as needed
            updates = {
                "processed": True,
                "updated_at": "2025-12-18T15:30:00Z"
            }
            update_entity_metadata(kg_service, args.paper_id, updates)

    finally:
        kg_service.close()


if __name__ == "__main__":
    main()