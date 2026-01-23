
import asyncio
from neo4j import GraphDatabase

# Using the settings we saw earlier in config.py
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "neo4jpassword") # Default dev credentials

PAPER_ID = "2512.15687v1"
CORRECT_TITLE = "Can LLMs Guide Their Own Exploration? Gradient-Guided Reinforcement Learning for LLM Reasoning"

def fix_paper_titles():
    try:
        driver = GraphDatabase.driver(URI, auth=AUTH)
        with driver.session() as session:
            # Check how many nodes need fixing
            count_query = """
            MATCH (n)
            WHERE (n.metadata CONTAINS $paper_id OR n.paper_id = $paper_id)
            AND (n.metadata CONTAINS "'paper_title': 'pdf'" OR n.paper_title = 'pdf')
            RETURN count(n) as count
            """
            result = session.run(count_query, paper_id=PAPER_ID)
            count = result.single()["count"]
            print(f"Found {count} nodes with incorrect title 'pdf' for paper {PAPER_ID}.")
            
            if count > 0:
                # Update them
                # Note: metadata is stored as a string JSON in some nodes (based on CSV export), 
                # or as properties. We should handle both if possible, but the CSV showed stringified metadata.
                # The regex replace is tricky in Cypher. 
                # Ideally we just update the node properties if they exist, or rely on string replacement.
                
                # Update Logic 1: If it's a JSON string property named 'metadata'
                update_query_1 = """
                MATCH (n)
                WHERE n.metadata CONTAINS $paper_id AND n.metadata CONTAINS "'paper_title': 'pdf'"
                SET n.metadata = replace(n.metadata, "'paper_title': 'pdf'", "'paper_title': '" + $new_title + "'")
                RETURN count(n) as updated
                """
                
                result = session.run(update_query_1, paper_id=PAPER_ID, new_title=CORRECT_TITLE)
                updated = result.single()["updated"]
                print(f"Updated {updated} nodes (String Metadata Replace).")

            else:
                print("No nodes found requiring update.")

        driver.close()
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")

if __name__ == "__main__":
    fix_paper_titles()
