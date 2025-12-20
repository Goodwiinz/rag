
import asyncio
from neo4j import GraphDatabase

# Connection details
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "neo4jpassword")

def analyze_relationships():
    try:
        driver = GraphDatabase.driver(URI, auth=AUTH)
        with driver.session() as session:
            print("--- Existing Relationships involving CONCEPTS ---")
            query = """
            MATCH (n:CONCEPT)-[r]-(m) 
            RETURN labels(n) as source_labels, type(r) as relation_type, labels(m) as target_labels, count(r) as count
            ORDER BY count DESC
            LIMIT 20
            """
            result = session.run(query)
            
            for record in result:
                print(f"{record['source_labels']} --[{record['relation_type']}]--> {record['target_labels']}: {record['count']}")
                
            print("\n--- All Relationship Types in DB ---")
            query_all = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
            result_all = session.run(query_all)
            print([r["relationshipType"] for r in result_all])

        driver.close()
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")

if __name__ == "__main__":
    analyze_relationships()
