
import asyncio
import os
from neo4j import GraphDatabase

# Using the settings we saw earlier in config.py
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "neo4jpassword") # Default dev credentials

def cleanup_bad_concepts():
    try:
        driver = GraphDatabase.driver(URI, auth=AUTH)
        with driver.session() as session:
            # 1. Count nodes to be deleted
            count_query = """
            MATCH (n:CONCEPT)
            WHERE n.extraction_method = 'pattern_matching' 
            AND n.metadata CONTAINS 'source' 
            AND n.metadata CONTAINS 'text_pattern'
            RETURN count(n) as count
            """
            result = session.run(count_query)
            count = result.single()["count"]
            print(f"Found {count} bad CONCEPT nodes to delete.")

            if count > 0:
                # 2. Delete them
                delete_query = """
                MATCH (n:CONCEPT)
                WHERE n.extraction_method = 'pattern_matching'
                AND n.metadata CONTAINS 'source'
                AND n.metadata CONTAINS 'text_pattern'
                DETACH DELETE n
                """
                session.run(delete_query)
                print(f"Successfully deleted {count} nodes.")
            else:
                print("No nodes matched the criteria.")

        driver.close()
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")

if __name__ == "__main__":
    cleanup_bad_concepts()
