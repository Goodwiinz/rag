#!/usr/bin/env python3
"""
Fix arXiv Neo4j integration by bypassing config issues
"""

import sys
import asyncio
from pathlib import Path
import os

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent / "backend"))

async def test_direct_neo4j():
    """Test direct Neo4j connection without config"""
    print("=" * 60)
    print("Direct Neo4j Test")
    print("=" * 60)

    try:
        from neo4j import GraphDatabase
        print("✓ Neo4j driver imported")
    except Exception as e:
        print(f"✗ Neo4j import failed: {e}")
        return

    # Connect directly
    try:
        driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "neo4jpassword")
        )

        with driver.session() as session:
            result = session.run("RETURN 'Hello Neo4j' as message")
            message = result.single()['message']
            print(f"✓ Connected to Neo4j: {message}")

            # Count nodes
            result = session.run("MATCH (n) RETURN count(n) as count")
            count = result.single()['count']
            print(f"✓ Total nodes in database: {count}")

            # Create test entities
            print("\nCreating test entities...")

            # Create a concept node
            session.run("""
                CREATE (c:Concept:Entity {
                    id: 'ml-concept-1',
                    name: 'Machine Learning',
                    type: 'CONCEPT',
                    confidence_score: 0.95,
                    created_at: datetime(),
                    metadata: {
                        source: 'arxiv',
                        category: 'cs.LG'
                    }
                })
            """)
            print("✓ Created Machine Learning concept node")

            # Create another concept
            session.run("""
                CREATE (c:Concept:Entity {
                    id: 'ai-concept-1',
                    name: 'Artificial Intelligence',
                    type: 'CONCEPT',
                    confidence_score: 0.95,
                    created_at: datetime(),
                    metadata: {
                        source: 'arxiv',
                        category: 'cs.AI'
                    }
                })
            """)
            print("✓ Created Artificial Intelligence concept node")

            # Create relationship
            session.run("""
                MATCH (ml:Concept {name: 'Machine Learning'}),
                     (ai:Concept {name: 'Artificial Intelligence'})
                CREATE (ml)-[r:RELATED_TO {
                    type: 'RELATED_TO',
                    confidence: 0.9,
                    created_at: datetime(),
                    metadata: {
                        relationship_type: 'is_subfield_of'
                    }
                }]->(ai)
            """)
            print("✓ Created relationship between concepts")

            # Create author nodes
            session.run("""
                CREATE (a:Person:Entity {
                    id: 'author-1',
                    name: 'Geoffrey Hinton',
                    type: 'PERSON',
                    confidence_score: 1.0,
                    created_at: datetime(),
                    metadata: {
                        source: 'arxiv',
                        role: 'author'
                    }
                })
            """)
            print("✓ Created author node")

            # Create paper node
            session.run("""
                CREATE (p:Document:Entity {
                    id: 'arxiv-1234',
                    name: 'Deep Learning Paper',
                    type: 'DOCUMENT',
                    confidence_score: 1.0,
                    created_at: datetime(),
                    metadata: {
                        source: 'arxiv',
                        arxiv_id: '1234.5678',
                        category: 'cs.LG'
                    }
                })
            """)
            print("✓ Created paper node")

            # Create author-paper relationship
            session.run("""
                MATCH (a:Person {name: 'Geoffrey Hinton'}),
                     (p:Document {name: 'Deep Learning Paper'})
                CREATE (a)-[r:AUTHORED {
                    type: 'AUTHORED',
                    confidence: 1.0,
                    created_at: datetime()
                }]->(p)
            """)
            print("✓ Created author-paper relationship")

            print("\n✓ All test data created successfully!")

        driver.close()

    except Exception as e:
        print(f"✗ Neo4j operation failed: {e}")

    # Now query and show the results
    print("\n" + "=" * 60)
    print("Querying created data...")
    print("=" * 60)

    try:
        driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "neo4jpassword")
        )

        with driver.session() as session:
            # Show all entities
            result = session.run("""
                MATCH (e:Entity)
                RETURN e.name as name, labels(e) as labels, e.type as type
                LIMIT 10
            """)

            print("\nEntities in Neo4j:")
            for record in result:
                print(f"  - {record['name']} (labels: {record['labels']}, type: {record['type']})")

            # Show relationships
            result = session.run("""
                MATCH (e1)-[r]->(e2)
                RETURN e1.name as source, type(r) as relationship, e2.name as target
                LIMIT 10
            """)

            print("\nRelationships:")
            for record in result:
                print(f"  - {record['source']} --[{record['relationship']}]--> {record['target']}")

        driver.close()

    except Exception as e:
        print(f"✗ Query failed: {e}")

    print("\n" + "=" * 60)
    print("Instructions")
    print("=" * 60)
    print("\nTo view the data in Neo4j Browser:")
    print("1. Open http://localhost:7474")
    print("2. Login with neo4j/neo4j123")
    print("3. Run queries:")
    print("   - MATCH (n) RETURN n")
    print("   - MATCH (e:Entity) RETURN e")
    print("   - MATCH (e1)-[r]->(e2) RETURN e1, r, e2")
    print("   - MATCH (c:Concept) RETURN c")
    print("   - MATCH (p:Person)-[:AUTHORED]->(d:Document) RETURN p, d")

if __name__ == "__main__":
    asyncio.run(test_direct_neo4j())