"""
Improved Knowledge Graph Service with connection resilience
"""

import logging
import time
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class ResilientKnowledgeGraphService:
    """Knowledge graph service with automatic reconnection"""

    def __init__(self, max_retries=3, retry_delay=1):
        from .knowledge_graph_service import KnowledgeGraphService
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._kg_service = None
        self._get_service()

    def _get_service(self):
        """Get or create the KG service"""
        from .knowledge_graph_service import KnowledgeGraphService
        if self._kg_service is None:
            self._kg_service = KnowledgeGraphService()
        return self._kg_service

    def _execute_with_retry(self, func, *args, **kwargs):
        """Execute function with retry logic"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # Try to execute
                if attempt > 0:
                    logger.info(f"Retrying KG operation (attempt {attempt + 1}/{self.max_retries})")
                    # Recreate service if needed
                    self._kg_service = None
                    self._get_service()

                result = func(self._kg_service, *args, **kwargs)
                return result

            except Exception as e:
                last_error = e
                if "defunct connection" in str(e) or "failed to read" in str(e).lower():
                    logger.warning(f"Neo4j connection issue on attempt {attempt + 1}: {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    # Non-connection error, don't retry
                    break

        raise last_error

    def create_entity(self, request):
        """Create entity with retry"""
        return self._execute_with_retry(
            lambda kg: kg.create_entity(request)
        )

    def create_relationship(self, request):
        """Create relationship with retry"""
        return self._execute_with_retry(
            lambda kg: kg.create_relationship(request)
        )

    def search_entities(self, query="", entity_types=None, limit=100):
        """Search entities with retry"""
        return self._execute_with_retry(
            lambda kg: kg.search_entities(query, entity_types, limit)
        )

# Update the arxiv_local.py to use this improved service
"""
# In src/api/arxiv_local.py, replace:
kg_service = KnowledgeGraphService()

# With:
from .knowledge_graph_service_improved import ResilientKnowledgeGraphService
kg_service = ResilientKnowledgeGraphService()
"""