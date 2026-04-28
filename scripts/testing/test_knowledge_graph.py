#!/usr/bin/env python3
"""
Simple script to populate Neo4j knowledge graph with sample data
"""

import os
from neo4j import GraphDatabase

def create_sample_knowledge_graph():
    """Create sample entities and relationships in Neo4j"""

    # Neo4j connection (credentials sourced from environment — see issue #379)
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("NEO4J_PASSWORD environment variable is required.")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))

        with driver.session() as session:
            # Clear existing data
            session.run("MATCH (n) DETACH DELETE n")

            # Create sample entities
            entities = [
                {"name": "Knowledge Graph", "type": "Concept", "description": "A structured representation of knowledge"},
                {"name": "Neo4j", "type": "Technology", "description": "Graph database management system"},
                {"name": "Entity Extraction", "type": "Process", "description": "Process of identifying entities in text"},
                {"name": "Natural Language Processing", "type": "Field", "description": "Field of AI focused on language understanding"},
                {"name": "Vector Database", "type": "Technology", "description": "Database optimized for vector similarity search"},
                {"name": "Qdrant", "type": "Technology", "description": "Vector similarity search engine"},
                {"name": "Multimodal RAG", "type": "System", "description": "Retrieval-augmented generation system supporting multiple data types"},
            ]

            # Create entity nodes
            for entity in entities:
                session.run(
                    """
                    CREATE (e:Entity {
                        name: $name,
                        type: $type,
                        description: $description,
                        created_at: datetime(),
                        source: 'sample_data'
                    })
                    """,
                    **entity
                )

            # Create relationships
            relationships = [
                ("Knowledge Graph", "USES", "Neo4j"),
                ("Knowledge Graph", "REQUIRES", "Entity Extraction"),
                ("Entity Extraction", "PART_OF", "Natural Language Processing"),
                ("Multimodal RAG", "USES", "Knowledge Graph"),
                ("Multimodal RAG", "USES", "Vector Database"),
                ("Vector Database", "IMPLEMENTED_BY", "Qdrant"),
                ("Natural Language Processing", "ENABLES", "Entity Extraction"),
            ]

            for source, rel_type, target in relationships:
                session.run(
                    """
                    MATCH (source:Entity {name: $source_name})
                    MATCH (target:Entity {name: $target_name})
                    CREATE (source)-[r:RELATIONSHIP {
                        type: $rel_type,
                        created_at: datetime(),
                        source: 'sample_data'
                    }]->(target)
                    """,
                    source_name=source,
                    target_name=target,
                    rel_type=rel_type
                )

            # Create some document nodes
            documents = [
                {"title": "Knowledge Graph Architecture", "content": "This document describes the architecture of knowledge graphs..."},
                {"title": "Neo4j Best Practices", "content": "Best practices for using Neo4j graph database..."},
                {"title": "RAG System Design", "content": "Design principles for retrieval-augmented generation systems..."},
            ]

            for doc in documents:
                session.run(
                    """
                    CREATE (d:Document {
                        title: $title,
                        content: $content,
                        created_at: datetime(),
                        source: 'sample_data'
                    })
                    """,
                    **doc
                )

            # Connect documents to entities
            session.run("""
                MATCH (d:Document {title: 'Knowledge Graph Architecture'})
                MATCH (e:Entity {name: 'Knowledge Graph'})
                CREATE (d)-[:MENTIONS]->(e)
            """)

            session.run("""
                MATCH (d:Document {title: 'Neo4j Best Practices'})
                MATCH (e:Entity {name: 'Neo4j'})
                CREATE (d)-[:MENTIONS]->(e)
            """)

            session.run("""
                MATCH (d:Document {title: 'RAG System Design'})
                MATCH (e:Entity {name: 'Multimodal RAG'})
                CREATE (d)-[:MENTIONS]->(e)
            """)

            # Verify data was created
            result = session.run("MATCH (n) RETURN count(n) as node_count")
            node_count = result.single()["node_count"]

            result = session.run("MATCH ()-[r]->() RETURN count(r) as relationship_count")
            rel_count = result.single()["relationship_count"]

            print(f"✅ Successfully created knowledge graph:")
            print(f"   - {node_count} nodes")
            print(f"   - {rel_count} relationships")

            # Show some sample entities
            result = session.run("MATCH (e:Entity) RETURN e.name, e.type LIMIT 5")
            print("\n📊 Sample entities:")
            for record in result:
                print(f"   - {record['e.name']} ({record['e.type']})")

    except Exception as e:
        print(f"❌ Error creating knowledge graph: {e}")
        return False
    finally:
        driver.close()

    return True

if __name__ == "__main__":
    print("🚀 Creating sample knowledge graph...")
    success = create_sample_knowledge_graph()

    if success:
        print("\n✨ Knowledge graph created successfully!")
        print("🔍 You can now explore the graph in Neo4j Browser at http://localhost:7474")
        print("📱 The frontend knowledge graph viewer will also show this data")
    else:
        print("\n❌ Failed to create knowledge graph")