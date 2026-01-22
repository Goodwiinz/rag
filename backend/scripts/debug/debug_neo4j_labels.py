
import asyncio
import os
from neo4j import GraphDatabase

# Using the settings we saw earlier in config.py
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "neo4jpassword") # Default dev credentials from config.py

def inspect_graph():
    try:
        driver = GraphDatabase.driver(URI, auth=AUTH)
        with driver.session() as session:
            # 1. Count all nodes
            result = session.run("MATCH (n) RETURN count(n) as total")
            total = result.single()["total"]
            print(f"Total nodes in database: {total}")

            # 2. List all labels and their counts
            print("\n--- Node Label Counts ---")
            result = session.run("""
                CALL db.labels() YIELD label
                CALL {
                    WITH label
                    MATCH (n) WHERE label in labels(n)
                    RETURN count(n) as count
                }
                RETURN label, count ORDER BY count DESC
            """)
            for record in result:
                print(f"Label: {record['label']}, Count: {record['count']}")

            # 3. Check for Entity nodes with type property
            print("\n--- Entity Node Types (if 'Entity' label exists) ---")
            result = session.run("MATCH (n:Entity) RETURN n.type as type, count(n) as count ORDER BY count DESC")
            for record in result:
                print(f"Type: {record['type']}, Count: {record['count']}")

            # 4. Check specifically for 'Document' case variations
            print("\n--- Checking for Document label case variations ---")
            result = session.run("""
                CALL db.labels() YIELD label
                WHERE toLower(label) = 'document'
                RETURN label
            """)
            found_labels = [r['label'] for r in result]
            if found_labels:
                print(f"Found case variations: {found_labels}")
            else:
                print("No label matching 'document' (case-insensitive) found.")

        driver.close()
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")

if __name__ == "__main__":
    inspect_graph()
