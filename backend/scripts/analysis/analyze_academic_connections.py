import asyncio
import ast
import logging
from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def analyze_academic_connections():
    logger.info("Connecting to Neo4j...")
    if not knowledge_graph_service.driver:
        knowledge_graph_service._connect()
        
    query = """
    MATCH (n:Entity)
    RETURN n.type as type, n.name as name, n.metadata as metadata
    """
    
    topics = []
    institutions = []
    
    with knowledge_graph_service.get_session() as session:
        result = session.run(query)
        for record in result:
            node_type = record['type']
            name = record['name']
            metadata_str = record['metadata']
            
            meta = {}
            if metadata_str:
                try:
                    meta = ast.literal_eval(metadata_str)
                except:
                    pass
            
            original_type = meta.get('entity_type_original')
            
            if node_type == 'ORGANIZATION' or original_type == 'institution':
                institutions.append(name)
            elif original_type == 'topic':
                topics.append(name)
                
    logger.info(f"--- Institutions Found: {len(institutions)} ---")
    for i in institutions[:10]:
        logger.info(f" - {i}")
        
    logger.info(f"--- Topics Found: {len(topics)} ---")
    for t in topics[:10]:
        logger.info(f" - {t}")

if __name__ == "__main__":
    asyncio.run(analyze_academic_connections())
