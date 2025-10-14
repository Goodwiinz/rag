#!/usr/bin/env python3
"""
Test Neo4j connectivity and basic functionality
"""

import os
from neo4j import GraphDatabase
from src.core.config import settings

def test_neo4j_connection():
    """Test basic Neo4j connectivity"""
    print("\n=== Testing Neo4j Connection ===")

    try:
        # Parse connection details from settings
        uri = settings.NEO4J_URI
        user = settings.NEO4J_USER
        password = settings.NEO4J_PASSWORD

        print(f"Connecting to Neo4j at: {uri}")
        print(f"User: {user}")

        # Create driver
        driver = GraphDatabase.driver(uri, auth=(user, password))

        # Test connection
        with driver.session() as session:
            result = session.run("RETURN 'Hello Neo4j!' AS message")
            record = result.single()
            print(f"✅ Connected to Neo4j successfully!")
            print(f"Message: {record['message']}")

            # Get Neo4j version
            result = session.run("CALL dbms.components() YIELD name, versions RETURN name, versions")
            record = result.single()
            print(f"✅ Neo4j version: {record['versions'][0]}")

        driver.close()
        return True

    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
        return False

def test_basic_operations():
    """Test basic Neo4j operations"""
    print("\n=== Testing Basic Neo4j Operations ===")

    try:
        uri = settings.NEO4J_URI
        user = settings.NEO4J_USER
        password = settings.NEO4J_PASSWORD

        driver = GraphDatabase.driver(uri, auth=(user, password))

        with driver.session() as session:
            # Clean up any existing test data
            session.run("MATCH (n:TestEntity) DETACH DELETE n")
            print("✅ Cleaned up existing test data")

            # Create test entities
            session.run("""
                CREATE (p1:Person:TestEntity {name: 'Alice', type: 'PERSON', source: 'test'})
                CREATE (p2:Person:TestEntity {name: 'Bob', type: 'PERSON', source: 'test'})
                CREATE (c:Company:TestEntity {name: 'Acme Corp', type: 'ORGANIZATION', source: 'test'})
                CREATE (p1)-[:WORKS_FOR {strength: 0.9, context: 'employee'}]->(c)
                CREATE (p2)-[:WORKS_FOR {strength: 0.7, context: 'contractor'}]->(c)
                CREATE (p1)-[:KNOWS {strength: 0.8, context: 'colleague'}]->(p2)
            """)
            print("✅ Created test entities and relationships")

            # Test entity query
            result = session.run("""
                MATCH (e:TestEntity)
                RETURN e.name AS name, e.type AS type, labels(e) AS labels
                ORDER BY e.name
            """)

            entities = []
            for record in result:
                entities.append({
                    'name': record['name'],
                    'type': record['type'],
                    'labels': record['labels']
                })

            print(f"✅ Found {len(entities)} test entities:")
            for entity in entities:
                print(f"  - {entity['name']} ({entity['type']}) {entity['labels']}")

            # Test relationship query
            result = session.run("""
                MATCH (e1:TestEntity)-[r]->(e2:TestEntity)
                RETURN e1.name AS from, type(r) AS relationship, e2.name AS to, r.strength AS strength
                ORDER BY e1.name, e2.name
            """)

            relationships = []
            for record in result:
                relationships.append({
                    'from': record['from'],
                    'relationship': record['relationship'],
                    'to': record['to'],
                    'strength': record['strength']
                })

            print(f"✅ Found {len(relationships)} test relationships:")
            for rel in relationships:
                print(f"  - {rel['from']} --[{rel['relationship']} (strength: {rel['strength']})]--> {rel['to']}")

            # Test multi-hop query
            result = session.run("""
                MATCH path = (e1:TestEntity {name: 'Alice'})-[:KNOWS]-(friend)-[:WORKS_FOR]-(company)
                RETURN friend.name AS friend_name, company.name AS company_name
            """)

            paths = []
            for record in result:
                paths.append({
                    'friend': record['friend_name'],
                    'company': record['company_name']
                })

            print(f"✅ Found {len(paths)} multi-hop paths:")
            for path in paths:
                print(f"  - Alice knows {path['friend']} who works at {path['company']}")

        driver.close()
        return True

    except Exception as e:
        print(f"❌ Failed to perform Neo4j operations: {e}")
        return False

def test_schema_constraints():
    """Test creating schema constraints"""
    print("\n=== Testing Schema Constraints ===")

    try:
        uri = settings.NEO4J_URI
        user = settings.NEO4J_USER
        password = settings.NEO4J_PASSWORD

        driver = GraphDatabase.driver(uri, auth=(user, password))

        with driver.session() as session:
            # Create uniqueness constraints
            constraints = [
                "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
                "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
                "CREATE CONSTRAINT entity_name_type_unique IF NOT EXISTS FOR (e:Entity) REQUIRE (e.name, e.type) IS UNIQUE"
            ]

            for constraint in constraints:
                try:
                    session.run(constraint)
                    print(f"✅ Created constraint: {constraint.split('FOR')[1].split('REQUIRE')[0].strip()}")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"ℹ️ Constraint already exists: {constraint.split('FOR')[1].split('REQUIRE')[0].strip()}")
                    else:
                        print(f"⚠️ Warning creating constraint: {e}")

            # Create indexes
            indexes = [
                "CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON (e.name)",
                "CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type)",
                "CREATE INDEX document_title_index IF NOT EXISTS FOR (d:Document) ON (d.title)",
                "CREATE INDEX relationship_strength_index IF NOT EXISTS FOR ()-[r:RELATED_TO]-() ON (r.strength)"
            ]

            for index in indexes:
                try:
                    session.run(index)
                    print(f"✅ Created index: {index.split('FOR')[1].split('ON')[0].strip()}")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"ℹ️ Index already exists: {index.split('FOR')[1].split('ON')[0].strip()}")
                    else:
                        print(f"⚠️ Warning creating index: {e}")

        driver.close()
        return True

    except Exception as e:
        print(f"❌ Failed to create schema constraints: {e}")
        return False

def main():
    """Run all Neo4j tests"""
    print("🚀 Starting Neo4j Connectivity Tests")

    tests = [
        test_neo4j_connection,
        test_schema_constraints,
        test_basic_operations
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1

    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("🎉 All Neo4j tests passed! Knowledge graph infrastructure is ready.")
        return True
    else:
        print("⚠️  Some tests failed. Check the logs above.")
        return False

if __name__ == "__main__":
    main()