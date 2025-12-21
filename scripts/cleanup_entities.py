import sys
import os
import logging
from neo4j import GraphDatabase

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_manual_entities():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    query = """
    MATCH (e:Entity)
    WHERE e.extraction_method = 'manual'
    DETACH DELETE e
    RETURN count(e) as deleted_count
    """
    
    try:
        with driver.session() as session:
            result = session.run(query)
            count = result.single()["deleted_count"]
            logger.info(f"Successfully deleted {count} entities with extraction_method='manual'")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    cleanup_manual_entities()
