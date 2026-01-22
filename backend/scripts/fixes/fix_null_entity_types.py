"""
Fix NULL entity types in Neo4j knowledge graph.
Sets all entities with NULL type to 'OTHER'.

Usage:
    python scripts/fix_null_entity_types.py
"""

import logging
import sys
import os

# Add the parent directory to sys.path to allow imports from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fix_null_entity_types():
    """Fix all entities with NULL type by setting them to 'OTHER'"""

    driver = GraphDatabase.driver(
        settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )

    try:
        with driver.session() as session:
            # First, count how many entities have NULL type
            count_result = session.run("""
                MATCH (e:Entity) 
                WHERE e.type IS NULL OR e.entity_type IS NULL
                RETURN count(e) as count
            """)
            count = count_result.single()["count"]
            logger.info(f"Found {count} entities with NULL type")

            if count == 0:
                logger.info("No entities need fixing. Exiting.")
                return

            # Fix entities with NULL type property
            result1 = session.run("""
                MATCH (e:Entity) 
                WHERE e.type IS NULL
                SET e.type = 'OTHER'
                RETURN count(e) as updated
            """)
            updated1 = result1.single()["updated"]
            logger.info(f"Updated {updated1} entities with NULL 'type' property")

            # Fix entities with NULL entity_type property (alternate field name)
            result2 = session.run("""
                MATCH (e:Entity) 
                WHERE e.entity_type IS NULL
                SET e.entity_type = 'OTHER'
                RETURN count(e) as updated
            """)
            updated2 = result2.single()["updated"]
            logger.info(f"Updated {updated2} entities with NULL 'entity_type' property")

            # Verify fix
            verify_result = session.run("""
                MATCH (e:Entity) 
                WHERE e.type IS NULL OR e.entity_type IS NULL
                RETURN count(e) as remaining
            """)
            remaining = verify_result.single()["remaining"]

            if remaining == 0:
                logger.info("SUCCESS: All NULL entity types have been fixed!")
            else:
                logger.warning(f"WARNING: {remaining} entities still have NULL type")

            # Show type distribution after fix
            dist_result = session.run("""
                MATCH (e:Entity)
                RETURN e.type as type, count(e) as count
                ORDER BY count DESC
                LIMIT 20
            """)

            logger.info("\nEntity type distribution after fix:")
            for record in dist_result:
                logger.info(f"  {record['type']}: {record['count']}")

    finally:
        driver.close()
        logger.info("Neo4j connection closed")


if __name__ == "__main__":
    logger.info("Starting NULL entity type fix...")
    fix_null_entity_types()
    logger.info("Done!")
