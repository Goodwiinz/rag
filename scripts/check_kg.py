import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.src.services.knowledge_graph_service import knowledge_graph_service
from neo4j import GraphDatabase
import os

# Manual connection to verify if service fails
uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(uri, auth=(user, password))

with driver.session() as session:
    result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
    print(f"Relationship Count: {result.single()['count']}")
    
    result = session.run("MATCH (n) RETURN count(n) as count")
    print(f"Node Count: {result.single()['count']}")

driver.close()
