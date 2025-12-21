#!/usr/bin/env python3
"""
Update document node properties with extraction method information
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any, List
from neo4j import GraphDatabase, Driver, Session

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from src.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DocumentExtractionUpdater:
    """Update document nodes with extraction method information"""

    def __init__(self):
        self.driver: Driver = None
        self.uri = settings.NEO4J_URI
        self.user = settings.NEO4J_USER
        self.password = settings.NEO4J_PASSWORD
        self._connect()

    def _connect(self):
        """Establish connection to Neo4j database"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50
            )

            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info(f"Connected to Neo4j at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def get_session(self) -> Session:
        """Get a Neo4j session"""
        return self.driver.session()

    def update_document_extraction_info(self) -> Dict[str, Any]:
        """Update document nodes with extraction method statistics"""
        stats = {
            "documents_updated": 0,
            "extraction_methods_found": set(),
            "processing_time": 0,
            "errors": []
        }

        start_time = datetime.now()

        try:
            with self.get_session() as session:
                # First, let's check the current extraction methods in entities
                logger.info("Checking current extraction methods...")
                extraction_methods_query = """
                MATCH (e:Entity)
                WHERE e.extraction_method IS NOT NULL
                RETURN DISTINCT e.extraction_method as extraction_method
                """
                result = session.run(extraction_methods_query)
                extraction_methods = [record["extraction_method"] for record in result]
                stats["extraction_methods_found"] = set(extraction_methods)
                logger.info(f"Found extraction methods: {extraction_methods}")

                # Get all documents that have entities
                documents_query = """
                MATCH (d:Document)
                WHERE NOT d:Entity  // Only document nodes
                OPTIONAL MATCH (d)<-[e:EXTRACTED_FROM]-(entity:Entity)
                OPTIONAL MATCH (entity)-[:RELATED_TO]-(related:Entity)
                WITH d,
                     COUNT(DISTINCT entity) as entity_count,
                     COUNT(DISTINCT related) as related_count,
                     collect(DISTINCT entity.extraction_method) as extraction_methods
                WHERE entity_count > 0
                RETURN d.id as document_id,
                       d.title as title,
                       d.created_at as created_at,
                       entity_count,
                       related_count,
                       extraction_methods
                """
                result = session.run(documents_query)

                documents = []
                for record in result:
                    doc_data = {
                        "document_id": record["document_id"],
                        "title": record.get("title", "Untitled"),
                        "created_at": record.get("created_at"),
                        "entity_count": record["entity_count"],
                        "relationship_count": record["related_count"],
                        "extraction_methods": [em for em in record["extraction_methods"] if em is not None]
                    }
                    documents.append(doc_data)

                logger.info(f"Found {len(documents)} documents with entities")

                # Update each document with extraction method info
                for doc in documents:
                    try:
                        update_query = """
                        MATCH (d:Document {id: $document_id})
                        SET d.extraction_methods = $extraction_methods,
                            d.entity_count = $entity_count,
                            d.relationship_count = $relationship_count,
                            d.last_extracted_at = datetime(),
                            d.extraction_summary = $extraction_summary
                        RETURN d
                        """

                        # Create extraction summary
                        method_counts = {}
                        for method in doc["extraction_methods"]:
                            method_counts[method] = method_counts.get(method, 0) + 1

                        extraction_summary = {
                            "total_entities": doc["entity_count"],
                            "total_relationships": doc["relationship_count"],
                            "methods": method_counts
                        }

                        session.run(update_query, {
                            "document_id": doc["document_id"],
                            "extraction_methods": doc["extraction_methods"],
                            "entity_count": doc["entity_count"],
                            "relationship_count": doc["relationship_count"],
                            "extraction_summary": str(extraction_summary)
                        })

                        stats["documents_updated"] += 1
                        logger.info(f"Updated document: {doc['document_id']} - "
                                  f"{doc['entity_count']} entities, {doc['relationship_count']} relationships")

                    except Exception as e:
                        error_msg = f"Failed to update document {doc['document_id']}: {str(e)}"
                        logger.error(error_msg)
                        stats["errors"].append(error_msg)

                # Create materialized view for document analytics
                logger.info("Creating document analytics view...")
                create_view_query = """
                CREATE OR REPLACE VIEW document_extraction_stats AS
                MATCH (d:Document)
                WHERE d.extraction_methods IS NOT NULL
                RETURN d.id as document_id,
                       d.title,
                       d.entity_count,
                       d.relationship_count,
                       d.extraction_methods,
                       d.last_extracted_at,
                       d.extraction_summary
                """

                # Note: This might not work in all Neo4j versions
                try:
                    session.run(create_view_query)
                    logger.info("Created document extraction stats view")
                except Exception as e:
                    logger.warning(f"Could not create view (may not be supported): {e}")

                # Create index for better query performance
                index_queries = [
                    "CREATE INDEX document_extraction_methods IF NOT EXISTS FOR (d:Document) ON (d.extraction_methods)",
                    "CREATE INDEX document_entity_count IF NOT EXISTS FOR (d:Document) ON (d.entity_count)",
                    "CREATE INDEX document_last_extracted IF NOT EXISTS FOR (d:Document) ON (d.last_extracted_at)"
                ]

                for query in index_queries:
                    try:
                        session.run(query)
                        logger.debug(f"Applied index: {query}")
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            logger.warning(f"Failed to apply index: {e}")

        except Exception as e:
            error_msg = f"Error updating documents: {str(e)}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)

        stats["processing_time"] = (datetime.now() - start_time).total_seconds()
        return stats

    def get_extraction_summary(self) -> Dict[str, Any]:
        """Get a summary of extraction methods across all documents"""
        try:
            with self.get_session() as session:
                # Overall statistics
                stats_query = """
                MATCH (d:Document)
                WHERE d.extraction_methods IS NOT NULL
                RETURN COUNT(d) as total_documents,
                       SUM(d.entity_count) as total_entities,
                       SUM(d.relationship_count) as total_relationships
                """

                result = session.run(stats_query).single()
                overall_stats = {
                    "total_documents": result["total_documents"],
                    "total_entities": result["total_entities"] or 0,
                    "total_relationships": result["total_relationships"] or 0
                }

                # Method distribution
                method_query = """
                UNWIND range(0, size(d.extraction_methods)-1) as idx
                MATCH (d:Document)
                WHERE d.extraction_methods IS NOT NULL
                WITH d.extraction_methods[idx] as method
                RETURN method, count(*) as count
                ORDER BY count DESC
                """

                method_result = session.run(method_query)
                method_distribution = {record["method"]: record["count"] for record in method_result}

                # Recent extractions
                recent_query = """
                MATCH (d:Document)
                WHERE d.last_extracted_at IS NOT NULL
                RETURN d.id, d.title, d.last_extracted_at, d.entity_count
                ORDER BY d.last_extracted_at DESC
                LIMIT 10
                """

                recent_result = session.run(recent_query)
                recent_extractions = [
                    {
                        "document_id": record["id"],
                        "title": record.get("title"),
                        "last_extracted_at": record["last_extracted_at"],
                        "entity_count": record["entity_count"]
                    }
                    for record in recent_result
                ]

                return {
                    "overall_stats": overall_stats,
                    "method_distribution": method_distribution,
                    "recent_extractions": recent_extractions
                }

        except Exception as e:
            logger.error(f"Error getting extraction summary: {e}")
            return {}

    def close(self):
        """Close the Neo4j driver"""
        if self.driver:
            self.driver.close()
            logger.info("Closed Neo4j connection")


def main():
    """Main function to update document extraction information"""
    updater = None
    try:
        logger.info("="*80)
        logger.info("DOCUMENT EXTRACTION INFO UPDATER")
        logger.info("="*80)

        updater = DocumentExtractionUpdater()

        # Update documents with extraction method information
        logger.info("\nUpdating document nodes with extraction method information...")
        stats = updater.update_document_extraction_info()

        # Print results
        logger.info("\n" + "="*80)
        logger.info("UPDATE RESULTS")
        logger.info("="*80)
        logger.info(f"Documents updated: {stats['documents_updated']}")
        logger.info(f"Processing time: {stats['processing_time']:.2f} seconds")
        logger.info(f"Extraction methods found: {stats['extraction_methods_found']}")

        if stats["errors"]:
            logger.warning(f"\nErrors encountered: {len(stats['errors'])}")
            for error in stats["errors"]:
                logger.warning(f"  - {error}")

        # Get summary
        logger.info("\n" + "="*80)
        logger.info("EXTRACTION SUMMARY")
        logger.info("="*80)
        summary = updater.get_extraction_summary()

        if "overall_stats" in summary:
            overall = summary["overall_stats"]
            logger.info(f"Total documents with extractions: {overall['total_documents']}")
            logger.info(f"Total entities extracted: {overall['total_entities']}")
            logger.info(f"Total relationships: {overall['total_relationships']}")

            if "method_distribution" in summary:
                logger.info("\nExtraction method distribution:")
                for method, count in summary["method_distribution"].items():
                    logger.info(f"  {method}: {count} documents")

        logger.info("\n✓ Document extraction information updated successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Query updated documents in Neo4j Browser:")
        logger.info("   MATCH (d:Document) WHERE d.extraction_methods IS NOT NULL RETURN d")
        logger.info("2. Check extraction statistics:")
        logger.info("   MATCH (d:Document) RETURN d.extraction_methods, d.entity_count")

    except Exception as e:
        logger.error(f"Update failed: {str(e)}", exc_info=True)
    finally:
        if updater:
            updater.close()


if __name__ == "__main__":
    main()