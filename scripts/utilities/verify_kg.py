import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

print(f"Connecting to {URI} as {USER}...")

try:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        # Check node count
        result = session.run("MATCH (n) RETURN count(n) as count")
        count = result.single()["count"]
        print(f"Total nodes in graph: {count}")
        
        if count > 0:
            # Check for Documents
            print("\nRecent Document nodes:")
            result = session.run("MATCH (n:Document) RETURN n.paper_id, n.title ORDER BY n.extracted_at DESC LIMIT 5")
            documents = list(result)
            if documents:
                for record in documents:
                    print(f" - [{record['n.paper_id']}] {record['n.title']}")
            else:
                print(" - No Document nodes found.")

            # Check for Concepts (Topics)
            print("\nSample Concept nodes:")
            result = session.run("MATCH (n:Concept) RETURN n.name LIMIT 5")
            concepts = list(result)
            if concepts:
                for record in concepts:
                    print(f" - {record['n.name']}")
            else:
                print(" - No Concept nodes found.")
        else:
            print("Graph is empty.")
            
    driver.close()
    print("\nVerification complete.")

except Exception as e:
    print(f"Error connecting to Neo4j: {e}")
