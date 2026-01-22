import asyncio
import os
import ast
import logging
from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_author_names():
    """
    Fetch all PERSON entities, parse their metadata to find 'full_name',
    and update the 'name' property to match the full name.
    """
    logger.info("Connecting to Neo4j...")
    driver = knowledge_graph_service.driver
    if not driver:
        # Try to initialize if not already
        knowledge_graph_service._connect()
        driver = knowledge_graph_service.driver
        
    if not driver:
        logger.error("Could not connect to Neo4j.")
        return

    query = """
    MATCH (n:Entity)
    WHERE n.type = 'PERSON' OR n.type = 'author' OR 'PERSON' in labels(n)
    RETURN elementId(n) as id, n.name as current_name, n.metadata as metadata
    """
    
    update_query = """
    MATCH (n:Entity)
    WHERE elementId(n) = $id
    SET n.name = $new_name, n.full_name = $new_name
    RETURN n.name
    """
    
    count_updated = 0
    
    with knowledge_graph_service.get_session() as session:
        # Fetch all candidates
        # Note: session.run is synchronous in standard Neo4j driver unless using AsyncSession
        # knowledge_graph_service.get_session() returns a synchronous session context manager
        
        # We need to collect first because we can't write while reading in same tx sometimes, 
        # or better to batch.
        nodes_to_update = []
        
        # We can use a direct session for reading
        with driver.session() as read_session:
            result = read_session.run(query)
            for record in result:
                node_id = record['id']
                current_name = record['current_name']
                metadata_str = record['metadata']
                
                if not metadata_str:
                    continue
                    
                full_name = None
                try:
                    # Metadata seems to be a string representation of a Python dict
                    # e.g. "{'source': 'paper_authors', ...}"
                    # We use ast.literal_eval for safe parsing
                    meta_dict = ast.literal_eval(metadata_str)
                    full_name = meta_dict.get('full_name')
                except Exception as e:
                    logger.warning(f"Failed to parse metadata for node {node_id}: {e}")
                    continue
                
                if full_name and full_name != current_name:
                    nodes_to_update.append((node_id, full_name))
        
        logger.info(f"Found {len(nodes_to_update)} nodes requiring name update.")
        
        # Apply updates
        with driver.session() as write_session:
            for node_id, new_name in nodes_to_update:
                try:
                    write_session.run(update_query, {'id': node_id, 'new_name': new_name})
                    count_updated += 1
                    if count_updated % 10 == 0:
                        logger.info(f"Updated {count_updated} nodes...")
                except Exception as e:
                    logger.error(f"Failed to update node {node_id} to '{new_name}': {e}")

    logger.info(f"Finished. Total updated: {count_updated}")

if __name__ == "__main__":
    # The service setup might need env vars loaded
    from src.core.config import settings
    # To ensure driver initialization works if not already
    asyncio.run(fix_author_names())
