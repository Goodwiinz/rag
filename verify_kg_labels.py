import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

try:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        # Check node count
        result = session.run("MATCH (n) RETURN count(n) as count")
        count = result.single()["count"]
        print(f"Total nodes: {count}")
        
        if count > 0:
            print("Labels present:")
            result = session.run("MATCH (n) RETURN distinct labels(n) as labels")
            for record in result:
                print(f" - {record['labels']}")
        else:
            print("Graph is effectively empty.")
            
    driver.close()
except Exception as e:
    print(f"Error: {e}")
