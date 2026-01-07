"""
ArXiv Change Tracking Service

This service tracks changes to arXiv papers and updates the database
when new papers are added or existing papers are modified.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from ..core.database import get_db, get_async_session
from ..models.document import Document, DocumentType
from ..services.arxiv_service import ArXivIngestionService
from ..services.knowledge_graph_service import KnowledgeGraphService
from ..services.arxiv_kg_integration import ArXivKnowledgeGraphIntegration

logger = logging.getLogger(__name__)


@dataclass
class ChangeRecord:
    """Record of a change to an arXiv paper"""
    paper_id: str
    change_type: str  # 'new', 'updated', 'deleted'
    old_hash: Optional[str]
    new_hash: str
    change_date: datetime
    fields_changed: List[str]
    metadata: Dict[str, Any]


class ArXivChangeTracker:
    """
    Tracks changes to arXiv papers and updates the database accordingly.

    Features:
    - Detects new papers
    - Identifies updated papers based on hash comparison
    - Tracks deleted papers (those no longer found in searches)
    - Maintains audit trail of all changes
    - Automatically updates database and knowledge graph
    """

    def __init__(self):
        self.state_file = Path("data/arxiv_change_state.json")
        self.state_file.parent.mkdir(exist_ok=True)
        self.state: Dict[str, Dict] = {}
        self.load_state()

    def load_state(self):
        """Load previous tracking state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                logger.info(f"Loaded tracking state for {len(self.state)} papers")
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
                self.state = {}
        else:
            logger.info("No previous state found, starting fresh")

    def save_state(self):
        """Save current tracking state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
            logger.debug("Saved tracking state")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def compute_paper_hash(self, paper: Dict[str, Any]) -> str:
        """Compute hash of paper metadata to detect changes"""
        # Fields to include in hash (exclude dynamic fields like last_updated)
        fields_to_hash = [
            'title', 'abstract', 'authors', 'categories',
            'primary_category', 'published', 'doi'
        ]

        hash_data = {}
        for field in fields_to_hash:
            if field in paper:
                # Sort lists to ensure consistent hashing
                if isinstance(paper[field], list):
                    hash_data[field] = sorted(paper[field])
                else:
                    hash_data[field] = paper[field]

        # Convert to JSON and compute hash
        data_str = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def detect_changes(self, papers: List[Dict[str, Any]]) -> List[ChangeRecord]:
        """
        Detect changes between current papers and stored state

        Returns:
            List of change records
        """
        changes = []
        current_ids = {paper['id'] for paper in papers}
        stored_ids = set(self.state.keys())

        # Find new papers
        new_ids = current_ids - stored_ids
        for paper in papers:
            if paper['id'] in new_ids:
                new_hash = self.compute_paper_hash(paper)
                change = ChangeRecord(
                    paper_id=paper['id'],
                    change_type='new',
                    old_hash=None,
                    new_hash=new_hash,
                    change_date=datetime.now(timezone.utc),
                    fields_changed=['all'],
                    metadata={'title': paper.get('title', '')}
                )
                changes.append(change)

                # Add to state
                self.state[paper['id']] = {
                    'hash': new_hash,
                    'last_seen': datetime.now(timezone.utc).isoformat(),
                    'paper_metadata': {
                        'title': paper.get('title', ''),
                        'authors': paper.get('authors', [])[:5],  # Store first 5 authors
                        'primary_category': paper.get('primary_category')
                    }
                }

        # Find updated papers
        common_ids = current_ids & stored_ids
        for paper in papers:
            if paper['id'] in common_ids:
                new_hash = self.compute_paper_hash(paper)
                old_hash = self.state[paper['id']]['hash']

                if new_hash != old_hash:
                    # Determine what changed
                    fields_changed = []
                    stored_metadata = self.state[paper['id']].get('paper_metadata', {})

                    # Compare key fields
                    if paper.get('title', '') != stored_metadata.get('title', ''):
                        fields_changed.append('title')
                    if sorted(paper.get('authors', [])) != sorted(stored_metadata.get('authors', [])):
                        fields_changed.append('authors')
                    if paper.get('primary_category', '') != stored_metadata.get('primary_category', ''):
                        fields_changed.append('category')

                    change = ChangeRecord(
                        paper_id=paper['id'],
                        change_type='updated',
                        old_hash=old_hash,
                        new_hash=new_hash,
                        change_date=datetime.now(timezone.utc),
                        fields_changed=fields_changed,
                        metadata={
                            'title': paper.get('title', ''),
                            'changes_detected': len(fields_changed)
                        }
                    )
                    changes.append(change)

                    # Update state
                    self.state[paper['id']]['hash'] = new_hash
                    self.state[paper['id']]['last_seen'] = datetime.utcnow().isoformat()
                    self.state[paper['id']]['paper_metadata'] = {
                        'title': paper.get('title', ''),
                        'authors': paper.get('authors', [])[:5],
                        'primary_category': paper.get('primary_category')
                    }

        # Find deleted papers (not in current results but in state)
        deleted_ids = stored_ids - current_ids
        for paper_id in deleted_ids:
            if 'deleted' not in self.state[paper_id]:  # Only mark as deleted once
                change = ChangeRecord(
                    paper_id=paper_id,
                    change_type='deleted',
                    old_hash=self.state[paper_id]['hash'],
                    new_hash='',
                    change_date=datetime.now(timezone.utc),
                    fields_changed=[],
                    metadata=self.state[paper_id].get('paper_metadata', {})
                )
                changes.append(change)

                # Mark as deleted in state (keep record)
                self.state[paper_id]['deleted'] = datetime.now(timezone.utc).isoformat()

        return changes

    async def apply_changes(self, changes: List[ChangeRecord], update_kg: bool = True) -> Dict[str, int]:
        """
        Apply changes to database and knowledge graph

        Returns:
            Summary of applied changes
        """
        summary = {
            'new': 0,
            'updated': 0,
            'deleted': 0,
            'errors': 0
        }

        async with get_async_session() as db:
            for change in changes:
                try:
                    if change.change_type == 'new':
                        # Handle new paper
                        paper = await self._fetch_paper_details(change.paper_id)
                        if paper:
                            await self._ingest_new_paper(db, paper, update_kg)
                            summary['new'] += 1
                            logger.info(f"Added new paper: {change.paper_id}")

                    elif change.change_type == 'updated':
                        # Handle updated paper
                        paper = await self._fetch_paper_details(change.paper_id)
                        if paper:
                            await self._update_existing_paper(db, paper, change.fields_changed)
                            if update_kg:
                                await self._update_knowledge_graph(paper)
                            summary['updated'] += 1
                            logger.info(f"Updated paper: {change.paper_id}, changed fields: {change.fields_changed}")

                    elif change.change_type == 'deleted':
                        # Handle deleted paper
                        await self._mark_paper_deleted(db, change.paper_id)
                        summary['deleted'] += 1
                        logger.info(f"Marked paper as deleted: {change.paper_id}")

                except Exception as e:
                    summary['errors'] += 1
                    logger.error(f"Error applying change for {change.paper_id}: {e}")

        # Save updated state
        self.save_state()

        return summary

    async def _fetch_paper_details(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full paper details from arXiv"""
        try:
            async with ArXivIngestionService() as service:
                results = await service.search_papers(
                    query=f"id:{paper_id}",
                    max_results=1
                )
                return results[0] if results else None
        except Exception as e:
            logger.error(f"Failed to fetch paper {paper_id}: {e}")
            return None

    async def _ingest_new_paper(self, db: AsyncSession, paper: Dict[str, Any], update_kg: bool):
        """Ingest a new paper into the database"""
        # TODO: The Document model doesn't have external_id, source, or content fields.
        # ArXiv papers need a dedicated ArXivPaper model or Document model updates.
        # For now, we only add to knowledge graph if requested.
        logger.info(f"Paper {paper['id']} tracked (DB persistence not yet implemented for ArXiv papers)")

        # Add to knowledge graph if requested
        if update_kg:
            try:
                logger.info(f"Adding paper {paper['id']} to knowledge graph...")
                async with ArXivKnowledgeGraphIntegration() as kg:
                    result = await kg.process_paper_kg_integration(paper)
                    if result:
                        logger.info(f"Successfully added {paper['id']} to KG with {len(result.get('entities', []))} entities")
                    else:
                        logger.warning(f"No result returned from KG integration for {paper['id']}")
            except Exception as e:
                logger.error(f"Failed to add paper {paper['id']} to KG: {e}", exc_info=True)

    async def _update_existing_paper(self, db: AsyncSession, paper: Dict[str, Any], changed_fields: List[str]):
        """Update an existing paper in the database"""
        # TODO: The Document model doesn't have external_id field.
        # ArXiv papers need a dedicated ArXivPaper model or Document model updates.
        logger.info(f"Paper {paper['id']} update tracked (DB persistence not yet implemented for ArXiv papers)")

    async def _update_knowledge_graph(self, paper: Dict[str, Any]):
        """Update knowledge graph with changed paper"""
        try:
            async with ArXivKnowledgeGraphIntegration() as kg:
                # Extract new entities and relationships
                await kg.process_paper_kg_integration(paper)
        except Exception as e:
            logger.warning(f"Failed to update KG for paper {paper['id']}: {e}")

    async def _mark_paper_deleted(self, db: AsyncSession, paper_id: str):
        """Mark a paper as deleted in the database"""
        # TODO: The Document model doesn't have external_id field.
        # ArXiv papers need a dedicated ArXivPaper model or Document model updates.
        logger.info(f"Paper {paper_id} deletion tracked (DB persistence not yet implemented for ArXiv papers)")

    async def track_category_changes(
        self,
        categories: List[str],
        days_back: int = 7,
        update_db: bool = True
    ) -> Dict[str, Any]:
        """
        Track changes for specific categories over a time period

        Args:
            categories: List of arXiv categories to track
            days_back: How many days back to look for changes
            update_db: Whether to apply changes to database

        Returns:
            Change tracking summary
        """
        logger.info(f"Tracking changes for categories: {categories}")

        # Search for papers in categories
        all_papers = []
        async with ArXivIngestionService() as service:
            for category in categories:
                papers = await service.search_papers(
                    query=f"cat:{category}",
                    max_results=20,  # Small batch for fast response - increase for production
                    date_from=datetime.now(timezone.utc) - timedelta(days=days_back)
                )
                all_papers.extend(papers)
                logger.info(f"Found {len(papers)} papers in {category}")

        # Remove duplicates
        seen_ids = set()
        unique_papers = []
        for paper in all_papers:
            if paper['id'] not in seen_ids:
                seen_ids.add(paper['id'])
                unique_papers.append(paper)

        logger.info(f"Total unique papers: {len(unique_papers)}")

        # Detect changes
        changes = self.detect_changes(unique_papers)

        # Group changes by type
        changes_by_type = {}
        for change in changes:
            if change.change_type not in changes_by_type:
                changes_by_type[change.change_type] = []
            changes_by_type[change.change_type].append(change)

        logger.info(f"Detected changes: {len(changes_by_type.get('new', []))} new, "
                   f"{len(changes_by_type.get('updated', []))} updated, "
                   f"{len(changes_by_type.get('deleted', []))} deleted")

        # Apply changes if requested
        if update_db and changes:
            summary = await self.apply_changes(changes, update_kg=True)
            logger.info(f"Applied changes: {summary}")
        else:
            summary = {
                'new': len(changes_by_type.get('new', [])),
                'updated': len(changes_by_type.get('updated', [])),
                'deleted': len(changes_by_type.get('deleted', [])),
                'errors': 0
            }

        return {
            'categories': categories,
            'period_days': days_back,
            'papers_found': len(unique_papers),
            'changes_detected': len(changes),
            'changes_by_type': changes_by_type,
            'applied': update_db,
            'summary': summary
        }

    async def get_change_history(self, paper_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get change history for papers

        Args:
            paper_id: Specific paper ID to get history for, or None for all

        Returns:
            List of change records
        """
        changes = []

        for pid, data in self.state.items():
            if paper_id and pid != paper_id:
                continue

            record = {
                'paper_id': pid,
                'current_hash': data['hash'],
                'last_seen': data['last_seen'],
                'deleted': data.get('deleted', False),
                'metadata': data.get('paper_metadata', {})
            }
            changes.append(record)

        return changes

    async def cleanup_old_state(self, days: int = 90):
        """Clean up state records for papers not seen in specified days"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        to_remove = []
        for paper_id, data in self.state.items():
            last_seen = datetime.fromisoformat(data['last_seen'])
            # Convert last_seen to timezone-aware if it's naive
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            if last_seen < cutoff and not data.get('deleted'):
                to_remove.append(paper_id)

        for paper_id in to_remove:
            del self.state[paper_id]
            logger.info(f"Removed stale state for {paper_id}")

        if to_remove:
            self.save_state()

        return len(to_remove)


# Singleton instance
change_tracker = ArXivChangeTracker()


async def track_arxiv_changes(categories: List[str] = None, days_back: int = 1):
    """
    Convenience function to track arXiv changes

    Args:
        categories: Categories to track (defaults to popular categories)
        days_back: Days to look back for changes
    """
    if categories is None:
        categories = ['cs.AI', 'cs.LG', 'cs.CV', 'quant-ph', 'stat.ML']

    return await change_tracker.track_category_changes(categories, days_back)