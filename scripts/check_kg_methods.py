import sys
import os
import logging
from neo4j import GraphDatabase

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_kg_methods():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    query = """
    MATCH (e:Entity)
    RETURN e.extraction_method as method, count(e) as count
    """
    
    try:
        with driver.session() as session:
            result = session.run(query)
            print("Extraction Methods Distribution:")
            for record in result:
                print(f"- {record['method']}: {record['count']}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    check_kg_methods()
