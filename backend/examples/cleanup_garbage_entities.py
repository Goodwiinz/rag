"""
Script to clean up garbage entities and relationships from the knowledge graph.
Removes low-quality entities that shouldn't have been extracted (OCR errors, fragments, etc.)

Usage:
    # Dry run - see what would be deleted
    python cleanup_garbage_entities.py --dry-run

    # Delete garbage entities and their relationships
    python cleanup_garbage_entities.py

    # Be more aggressive (remove more entities)
    python cleanup_garbage_entities.py --aggressive

    # Only show statistics
    python cleanup_garbage_entities.py --stats-only
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import argparse
import re
from typing import List, Dict, Any
from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def is_garbage_entity(name: str, entity_type: str, aggressive: bool = False) -> bool:
    """Determine if an entity is garbage and should be removed"""

    # Whitelist of legitimate short names (universities, companies, acronyms)
    legitimate_short_names = {
        # Universities
        'MIT', 'UCLA', 'USC', 'NYU', 'UCL', 'ETH', 'EPFL', 'CMU', 'RIT',
        'Yale', 'Duke', 'Rice', 'Case', 'Drew',
        'GTech', 'GaTech', 'Caltech', 'Pitt',
        # Tech companies
        'IBM', 'SAP', 'AMD', 'ARM', 'AWS', 'GCP', 'API',
        'Meta', 'Uber', 'Lyft', 'Snap', 'Zoom',
        # Research/Standards
        'IEEE', 'ACM', 'ISO', 'NIST', 'DARPA', 'NASA', 'ESA',
        'WHO', 'FDA', 'CDC', 'NIH', 'NSF',
        # Common abbreviations
        'USA', 'UK', 'EU', 'UN', 'NATO', 'ASEAN',
        'CEO', 'CTO', 'CFO', 'COO', 'VP', 'SVP', 'EVP',
        'AI', 'ML', 'NLP', 'CV', 'IoT', 'API', 'GPU', 'CPU',
        'PhD', 'MSc', 'BSc', 'MBA', 'MD',
        # Cities with short names
        'LA', 'NY', 'SF', 'DC', 'LA',
    }

    # Check if it's a known legitimate short name (case-insensitive)
    if name.upper() in legitimate_short_names:
        return False

    # Check if it looks like a university abbreviation (all uppercase, 2-5 chars)
    if entity_type == 'ORGANIZATION' and 2 <= len(name) <= 5:
        if name.isupper() and name.isalpha():
            # Likely a legitimate abbreviation
            return False

    # Very short entities (almost always garbage)
    if len(name) < 2:
        return True

    # Single characters
    if len(name) == 1:
        return True

    # Standalone small numbers
    if name.isdigit() and len(name) <= 3:
        return True

    # Just punctuation or symbols
    if re.match(r'^[\W_]+$', name):
        return True

    # OCR errors like "l20", "l4", "I20"
    if re.match(r'^[lI][0-9]+$', name):
        return True

    # Numbers with punctuation only
    if re.match(r'^[\d\W]+$', name):
        return True

    # Very short ORG entities - BUT check for legitimate patterns first
    if entity_type == 'ORGANIZATION' and len(name) <= 3:
        # Allow if it's all uppercase letters (likely acronym)
        if name.isupper() and name.isalpha():
            return False
        # Otherwise it's probably garbage
        return True

    # Single-character "locations" or "concepts"
    if entity_type in ['LOCATION', 'CONCEPT'] and len(name) <= 2:
        return True

    # Meaningless fragments
    meaningless = ['l', 'i', 'ii', 'iii', 'iv', 'v', 'x', 'xi', 'xx', 'xxx']
    if name.lower() in meaningless:
        return True

    # Common OCR mistakes
    ocr_patterns = [
        r'^l+$',  # Just lowercase L's
        r'^I+$',  # Just uppercase i's
        r'^[lI]{1,2}\d$',  # l2, I3, ll4, etc.
        r'^\d+\)$',  # Numbers with closing paren: 2), 3)
        r'^\d+\.$',  # Numbers with period: 2., 3.
    ]

    for pattern in ocr_patterns:
        if re.match(pattern, name):
            return True

    if aggressive:
        # More aggressive filtering - but still respect whitelist

        # Check whitelist first
        if name.upper() in legitimate_short_names:
            return False

        # Short ORG names (likely fragments) - but allow acronyms
        if entity_type == 'ORGANIZATION' and len(name) <= 5:
            if name.isupper() and name.isalpha():
                return False
            return True

        # Very short anything - except whitelisted
        if len(name) <= 3:
            return True

        # Single words that are too short - except whitelisted
        words = name.split()
        if len(words) == 1 and len(name) <= 4:
            if name.upper() in legitimate_short_names:
                return False
            return True

    return False


def get_all_entities() -> List[Dict[str, Any]]:
    """Get all entities from the knowledge graph"""
    query = """
    MATCH (e:Entity)
    RETURN e.id as id, e.name as name, e.type as type,
           e.confidence_score as confidence
    ORDER BY e.name
    """

    with knowledge_graph_service.driver.session() as session:
        result = session.run(query)
        return [dict(record) for record in result]


def get_entity_relationships(entity_id: str) -> int:
    """Count relationships for an entity"""
    query = """
    MATCH (e:Entity {id: $entity_id})
    OPTIONAL MATCH (e)-[r]-()
    RETURN count(r) as rel_count
    """

    with knowledge_graph_service.driver.session() as session:
        result = session.run(query, entity_id=entity_id)
        record = result.single()
        return record["rel_count"] if record else 0


def delete_entity(entity_id: str, dry_run: bool = False) -> int:
    """Delete an entity and all its relationships"""
    if dry_run:
        # Just count relationships
        return get_entity_relationships(entity_id)

    query = """
    MATCH (e:Entity {id: $entity_id})
    OPTIONAL MATCH (e)-[r]-()
    WITH e, count(r) as rel_count
    DETACH DELETE e
    RETURN rel_count
    """

    with knowledge_graph_service.driver.session() as session:
        result = session.run(query, entity_id=entity_id)
        record = result.single()
        return record["rel_count"] if record else 0


def show_statistics():
    """Show statistics about entities in the graph"""
    logger.info("\n" + "="*80)
    logger.info("KNOWLEDGE GRAPH STATISTICS")
    logger.info("="*80)

    # Total entities
    query = "MATCH (e:Entity) RETURN count(e) as total"
    with knowledge_graph_service.driver.session() as session:
        result = session.run(query)
        total = result.single()["total"]
        logger.info(f"Total entities: {total}")

    # Entities by type
    query = """
    MATCH (e:Entity)
    RETURN e.type as type, count(e) as count
    ORDER BY count DESC
    """
    with knowledge_graph_service.driver.session() as session:
        result = session.run(query)
        logger.info("\nEntities by type:")
        for record in result:
            logger.info(f"  {record['type']}: {record['count']}")

    # Total relationships
    query = "MATCH ()-[r]->() RETURN count(r) as total"
    with knowledge_graph_service.driver.session() as session:
        result = session.run(query)
        total = result.single()["total"]
        logger.info(f"\nTotal relationships: {total}")

    # Entities by name length
    query = """
    MATCH (e:Entity)
    WHERE e.name IS NOT NULL
    RETURN size(e.name) as len, count(e) as count
    ORDER BY len
    """
    with knowledge_graph_service.driver.session() as session:
        result = session.run(query)
        logger.info("\nEntities by name length:")
        for record in result:
            if record['len'] <= 10:  # Only show short ones
                logger.info(f"  Length {record['len']}: {record['count']} entities")

    # Sample short entities
    query = """
    MATCH (e:Entity)
    WHERE e.name IS NOT NULL AND size(e.name) <= 3
    RETURN e.name, e.type
    LIMIT 20
    """
    with knowledge_graph_service.driver.session() as session:
        result = session.run(query)
        records = list(result)
        logger.info(f"\nSample short entities (length <= 3): {len(records)} total")
        for record in records:
            # Access by index instead of key
            name = record[0]
            entity_type = record[1] if len(record) > 1 else 'N/A'
            logger.info(f"  '{name}' ({entity_type})")


def main():
    """Main cleanup function"""
    parser = argparse.ArgumentParser(description='Clean up garbage entities from knowledge graph')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    parser.add_argument('--aggressive', action='store_true', help='Be more aggressive in filtering (remove more entities)')
    parser.add_argument('--stats-only', action='store_true', help='Only show statistics, do not delete anything')

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("GARBAGE ENTITY CLEANUP")
    logger.info("="*80)

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    if args.aggressive:
        logger.info("AGGRESSIVE MODE - More entities will be removed")

    # Show initial statistics
    logger.info("\nBEFORE CLEANUP:")
    show_statistics()

    if args.stats_only:
        return

    # Get all entities
    logger.info("\n" + "="*80)
    logger.info("ANALYZING ENTITIES")
    logger.info("="*80)

    entities = get_all_entities()
    logger.info(f"Analyzing {len(entities)} entities...")

    # Identify garbage entities
    garbage_entities = []
    for entity in entities:
        if is_garbage_entity(entity['name'], entity['type'], args.aggressive):
            garbage_entities.append(entity)

    logger.info(f"\nFound {len(garbage_entities)} garbage entities to remove:")

    # Group by type
    by_type = {}
    for entity in garbage_entities:
        entity_type = entity['type']
        if entity_type not in by_type:
            by_type[entity_type] = []
        by_type[entity_type].append(entity['name'])

    for entity_type, names in sorted(by_type.items()):
        logger.info(f"\n{entity_type} ({len(names)}):")
        # Show first 10 of each type
        for name in names[:10]:
            logger.info(f"  - '{name}'")
        if len(names) > 10:
            logger.info(f"  ... and {len(names) - 10} more")

    # Delete entities
    logger.info("\n" + "="*80)
    logger.info("DELETING GARBAGE ENTITIES")
    logger.info("="*80)

    total_relationships_deleted = 0

    for i, entity in enumerate(garbage_entities, 1):
        entity_id = entity['id']
        entity_name = entity['name']
        entity_type = entity['type']

        rel_count = delete_entity(entity_id, dry_run=args.dry_run)
        total_relationships_deleted += rel_count

        if args.dry_run:
            logger.info(f"[DRY RUN] Would delete: '{entity_name}' ({entity_type}) with {rel_count} relationships")
        else:
            logger.info(f"✓ Deleted: '{entity_name}' ({entity_type}) with {rel_count} relationships ({i}/{len(garbage_entities)})")

    # Show final statistics
    logger.info("\n" + "="*80)
    logger.info("CLEANUP COMPLETE")
    logger.info("="*80)

    logger.info(f"Entities removed: {len(garbage_entities)}")
    logger.info(f"Relationships removed: {total_relationships_deleted}")

    if not args.dry_run:
        logger.info("\nAFTER CLEANUP:")
        show_statistics()
    else:
        logger.info("\n⚠️  DRY RUN - No changes were made")
        logger.info("Run without --dry-run to actually delete garbage entities")


if __name__ == "__main__":
    main()
