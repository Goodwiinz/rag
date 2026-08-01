"""
ArXiv Change Tracking Service

This service tracks changes to arXiv papers and updates the database
when new papers are added or existing papers are modified.
"""

import asyncio
import copy
import hashlib
import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_session, get_db
from src.models.document import Document, DocumentType, ProcessingStatus
from src.services.arxiv.arxiv_kg_integration import ArXivKnowledgeGraphIntegration
from src.services.arxiv.arxiv_service import ArXivIngestionService
from src.services.knowledge_graph import KnowledgeGraphService

logger = logging.getLogger(__name__)

# Serializes concurrent writes to the on-disk state file. Multiple category
# scans can run at once (API + cron); a naive open("w") interleaves their
# writes and corrupts the JSON.
_STATE_LOCK = threading.Lock()


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
    - Tracks papers missing from search results with consecutive miss counting
    - Only marks papers as deleted after DELETION_MISS_THRESHOLD consecutive misses
    - Maintains audit trail of all changes
    - Automatically updates database and knowledge graph
    """

    # Papers must be absent from search results for this many consecutive
    # tracking runs before being marked as deleted. ArXiv search results are
    # paginated and time-windowed, so a paper falling out of the top results
    # does not mean it was removed from ArXiv.
    DELETION_MISS_THRESHOLD = 3

    def __init__(self):
        self.state_file = Path("data/arxiv_change_state.json")
        self.state_file.parent.mkdir(exist_ok=True)
        # Tracking state is partitioned per organization under the "__orgs__"
        # key: self.state["__orgs__"][str(org_id)] = {paper_id: {...}}. A single
        # global dict leaked one tenant's papers into another's history/stats.
        self.state: Dict[str, Any] = {}
        self.load_state()

    def _org_state(self, organization_id: Any) -> Dict[str, Dict]:
        """Return the (mutable) per-organization tracking sub-dict, creating it
        if absent. Every read/write of paper state must go through this so that
        tenants never see each other's papers."""
        return self.state.setdefault("__orgs__", {}).setdefault(
            str(organization_id), {}
        )

    def load_state(self):
        """Load previous tracking state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    loaded = json.load(f)
                # Tolerate empty / legacy (flat, un-partitioned) files without
                # crashing. Legacy per-paper keys are simply ignored — new reads
                # go through the "__orgs__" partition.
                self.state = loaded if isinstance(loaded, dict) else {}
                org_count = len(self.state.get("__orgs__", {}))
                logger.info(f"Loaded tracking state for {org_count} organizations")
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
                self.state = {}
        else:
            logger.info("No previous state found, starting fresh")

    def save_state(self):
        """Save current tracking state to file atomically.

        Writes to a temp file in the same directory then ``os.replace`` (atomic
        on POSIX) under a module-level lock, so concurrent scans can never see a
        half-written / corrupt state file.
        """
        try:
            with _STATE_LOCK:
                self.state_file.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp_path = tempfile.mkstemp(
                    dir=str(self.state_file.parent), suffix=".tmp"
                )
                try:
                    with os.fdopen(fd, "w") as f:
                        json.dump(self.state, f, indent=2, default=str)
                    os.replace(tmp_path, self.state_file)
                except Exception:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    raise
            logger.debug("Saved tracking state")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def compute_paper_hash(self, paper: Dict[str, Any]) -> str:
        """Compute hash of paper metadata to detect changes"""
        # Fields to include in hash (exclude dynamic fields like last_updated)
        fields_to_hash = [
            "title",
            "abstract",
            "authors",
            "categories",
            "primary_category",
            "published",
            "doi",
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

    def detect_changes(
        self,
        papers: List[Dict[str, Any]],
        organization_id: Any,
        tracked_categories: Optional[Set[str]] = None,
        commit: bool = True,
    ) -> List[ChangeRecord]:
        """
        Detect changes between current papers and stored state, scoped to a
        single organization.

        Args:
            papers: Papers returned by the current (partial, per-category,
                date-windowed) arXiv scan.
            organization_id: Tenant whose tracking state to compare against.
            tracked_categories: The set of arXiv categories actually scanned in
                this run. When provided, a stored paper missing from ``papers``
                is only considered a deletion candidate if its stored
                ``primary_category`` is within this set — papers from other
                categories (or outside the date window) are simply not
                observable by this scan and must NOT be treated as deleted.
            commit: When False (dry run), operate on a deep copy of the org
                state and do NOT mutate ``self.state`` / persist anything.

        Returns:
            List of change records
        """
        changes: List[ChangeRecord] = []

        if commit:
            org_state = self._org_state(organization_id)
        else:
            # Dry run: never touch the live state.
            existing = self.state.get("__orgs__", {}).get(str(organization_id), {})
            org_state = copy.deepcopy(existing)

        current_ids = {paper["id"] for paper in papers}
        stored_ids = set(org_state.keys())

        # Find new papers
        new_ids = current_ids - stored_ids
        for paper in papers:
            if paper["id"] in new_ids:
                new_hash = self.compute_paper_hash(paper)
                change = ChangeRecord(
                    paper_id=paper["id"],
                    change_type="new",
                    old_hash=None,
                    new_hash=new_hash,
                    change_date=datetime.now(timezone.utc),
                    fields_changed=["all"],
                    metadata={"title": paper.get("title", "")},
                )
                changes.append(change)

                # Add to state
                org_state[paper["id"]] = {
                    "hash": new_hash,
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                    "paper_metadata": {
                        "title": paper.get("title", ""),
                        "authors": paper.get("authors", [])[
                            :5
                        ],  # Store first 5 authors
                        "primary_category": paper.get("primary_category"),
                    },
                }

        # Find updated papers (also resets miss_count since paper is still visible)
        common_ids = current_ids & stored_ids
        for paper in papers:
            if paper["id"] in common_ids:
                # Paper is still in results — reset miss count
                org_state[paper["id"]]["miss_count"] = 0
                if "deleted" in org_state[paper["id"]]:
                    del org_state[paper["id"]]["deleted"]

                new_hash = self.compute_paper_hash(paper)
                old_hash = org_state[paper["id"]]["hash"]

                # Always update last_seen
                org_state[paper["id"]]["last_seen"] = datetime.now(
                    timezone.utc
                ).isoformat()

                if new_hash != old_hash:
                    # Determine what changed
                    fields_changed = []
                    stored_metadata = org_state[paper["id"]].get("paper_metadata", {})

                    # Compare key fields
                    if paper.get("title", "") != stored_metadata.get("title", ""):
                        fields_changed.append("title")
                    if sorted(paper.get("authors", [])) != sorted(
                        stored_metadata.get("authors", [])
                    ):
                        fields_changed.append("authors")
                    if paper.get("primary_category", "") != stored_metadata.get(
                        "primary_category", ""
                    ):
                        fields_changed.append("category")

                    change = ChangeRecord(
                        paper_id=paper["id"],
                        change_type="updated",
                        old_hash=old_hash,
                        new_hash=new_hash,
                        change_date=datetime.now(timezone.utc),
                        fields_changed=fields_changed,
                        metadata={
                            "title": paper.get("title", ""),
                            "changes_detected": len(fields_changed),
                        },
                    )
                    changes.append(change)

                    # Update state
                    org_state[paper["id"]]["hash"] = new_hash
                    org_state[paper["id"]]["paper_metadata"] = {
                        "title": paper.get("title", ""),
                        "authors": paper.get("authors", [])[:5],
                        "primary_category": paper.get("primary_category"),
                    }

        # Track missing papers — increment miss_count instead of instant deletion.
        # Only mark as deleted after DELETION_MISS_THRESHOLD consecutive misses.
        #
        # The scan is a partial, date-windowed, per-category query, so a stored
        # paper absent from `papers` is NOT necessarily deleted — it may simply
        # belong to a category we didn't scan or fall outside the date window.
        # When `tracked_categories` is given, only papers whose stored
        # primary_category is in that set are observable enough to be deletion
        # candidates.
        missing_ids = stored_ids - current_ids
        for paper_id in missing_ids:
            data = org_state[paper_id]
            if "deleted" in data:
                # Already deleted, skip
                continue

            if tracked_categories is not None:
                stored_category = (data.get("paper_metadata", {}) or {}).get(
                    "primary_category"
                )
                if stored_category not in tracked_categories:
                    # Not covered by this scan — cannot conclude deletion.
                    continue

            miss_count = data.get("miss_count", 0) + 1
            data["miss_count"] = miss_count

            if miss_count >= self.DELETION_MISS_THRESHOLD:
                change = ChangeRecord(
                    paper_id=paper_id,
                    change_type="deleted",
                    old_hash=data["hash"],
                    new_hash="",
                    change_date=datetime.now(timezone.utc),
                    fields_changed=[],
                    metadata=data.get("paper_metadata", {}),
                )
                changes.append(change)

                # Mark as deleted in state (keep record)
                data["deleted"] = datetime.now(timezone.utc).isoformat()
                logger.info(
                    f"Paper {paper_id} marked deleted after {miss_count} consecutive misses"
                )
            else:
                logger.debug(
                    f"Paper {paper_id} missing from results "
                    f"({miss_count}/{self.DELETION_MISS_THRESHOLD} misses)"
                )

        return changes

    async def apply_changes(
        self,
        changes: List[ChangeRecord],
        organization_id: Any,
        user_id: Optional[Any] = None,
        update_kg: bool = True,
    ) -> Dict[str, int]:
        """
        Apply changes to database and knowledge graph, scoped to a tenant.

        Args:
            changes: Detected change records to apply.
            organization_id: Tenant owning every created/updated Document.
            user_id: User to attribute created documents to (uploaded_by).
            update_kg: Whether to sync the knowledge graph.

        Returns:
            Summary of applied changes
        """
        summary = {"new": 0, "updated": 0, "deleted": 0, "errors": 0}

        async with get_async_session() as db:
            for change in changes:
                try:
                    if change.change_type == "new":
                        # Handle new paper
                        paper = await self._fetch_paper_details(change.paper_id)
                        if paper:
                            await self._ingest_new_paper(
                                db, paper, organization_id, user_id, update_kg
                            )
                            summary["new"] += 1
                            logger.info(f"Added new paper: {change.paper_id}")
                        else:
                            summary["errors"] += 1
                            self._revert_change_state(organization_id, change)

                    elif change.change_type == "updated":
                        # Handle updated paper
                        paper = await self._fetch_paper_details(change.paper_id)
                        if paper:
                            await self._update_existing_paper(
                                db, paper, change.fields_changed, organization_id
                            )
                            if update_kg:
                                await self._update_knowledge_graph(paper)
                            summary["updated"] += 1
                            logger.info(
                                f"Updated paper: {change.paper_id}, changed fields: {change.fields_changed}"
                            )
                        else:
                            summary["errors"] += 1
                            self._revert_change_state(organization_id, change)

                    elif change.change_type == "deleted":
                        # Handle deleted paper
                        await self._mark_paper_deleted(
                            db, change.paper_id, organization_id
                        )
                        summary["deleted"] += 1
                        logger.info(f"Marked paper as deleted: {change.paper_id}")

                except Exception as e:
                    summary["errors"] += 1
                    self._revert_change_state(organization_id, change)
                    logger.error(f"Error applying change for {change.paper_id}: {e}")

        # Save updated state
        self.save_state()

        return summary

    def _revert_change_state(self, organization_id: Any, change: ChangeRecord):
        """Undo detect_changes' state write for a change that failed to apply.

        detect_changes stamps the new hash into state BEFORE apply runs, and
        apply_changes ends with save_state() regardless of per-paper failures.
        Without this revert, a transient failure (arXiv 429 was the observed
        case, Sentry JAVASCRIPT-NEXTJS-48/49) persisted the new hash anyway, so
        the next scan saw "no change" and the paper was silently never
        ingested/updated. Reverting makes the next scan re-emit the change.
        """
        org_state = self._org_state(organization_id)
        data = org_state.get(change.paper_id)
        if data is None:
            return
        if change.change_type == "new":
            org_state.pop(change.paper_id, None)
        elif change.change_type == "updated" and change.old_hash:
            data["hash"] = change.old_hash
        elif change.change_type == "deleted":
            # Keep miss_count at threshold so the next scan re-emits deletion.
            data.pop("deleted", None)

    async def _fetch_paper_details(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full paper details from arXiv"""
        try:
            async with ArXivIngestionService() as service:
                results = await service.search_papers(
                    query=f"id:{paper_id}", max_results=1
                )
                return results[0] if results else None
        except Exception as e:
            # arXiv 429s are expected transients (retried on the next scan via
            # _revert_change_state) — warning, not Sentry-error spam.
            log = logger.warning if "429" in str(e) else logger.error
            log(f"Failed to fetch paper {paper_id}: {e}")
            return None

    @staticmethod
    def _paper_metadata(paper: Dict[str, Any]) -> Dict[str, Any]:
        """Build the document_metadata payload for an arXiv paper.

        The arXiv id lives in document_metadata (the Document model has no
        external_id column); dedup/lookup keys on it.
        """
        return {
            "arxiv_id": paper["id"],
            "source": "arxiv",
            "authors": paper.get("authors", []),
            "categories": paper.get("categories", []),
            "primary_category": paper.get("primary_category"),
            "published": paper.get("published"),
            "doi": paper.get("doi"),
            "arxiv_url": paper.get("arxiv_url"),
            "pdf_url": paper.get("pdf_url"),
        }

    @staticmethod
    def _paper_lookup_stmt(paper_id: str, organization_id: Any):
        """Tenant-scoped lookup by the arxiv_id stored in document_metadata."""
        return select(Document).where(
            Document.organization_id == organization_id,
            # .as_string(), NOT .astext — document_metadata is the generic
            # sqlalchemy.JSON type, whose comparator has no astext (that's the
            # postgres-dialect JSONB type). astext raises AttributeError at
            # statement-build time.
            Document.document_metadata["arxiv_id"].as_string() == paper_id,
        )

    async def _ingest_new_paper(
        self,
        db: AsyncSession,
        paper: Dict[str, Any],
        organization_id: Any,
        user_id: Optional[Any],
        update_kg: bool,
    ):
        """Ingest a new paper into the database (tenant-scoped)."""
        # Check if paper already exists for this organization
        result = await db.execute(self._paper_lookup_stmt(paper["id"], organization_id))
        existing = result.scalar_one_or_none()

        if not existing:
            # Create new document record using the real Document columns.
            pdf_url = paper.get("pdf_url") or ""
            doc = Document(
                title=paper.get("title", "") or "",
                filename=f"{paper['id']}.pdf",
                file_path=pdf_url,
                file_size_bytes=0,
                mime_type="application/pdf",
                document_type=DocumentType.PDF,
                content_text=paper.get("abstract", "") or "",
                document_metadata=self._paper_metadata(paper),
                processing_status=ProcessingStatus.COMPLETED,
                organization_id=organization_id,
                uploaded_by_user_id=user_id,
                is_public=False,
            )
            db.add(doc)
            await db.commit()

            # Add to knowledge graph if requested
            if update_kg:
                try:
                    logger.info(f"Adding paper {paper['id']} to knowledge graph...")
                    async with ArXivKnowledgeGraphIntegration() as kg:
                        result = await kg.process_paper_kg_integration(paper)
                        if result:
                            logger.info(
                                f"Successfully added {paper['id']} to KG with {len(result.get('entities', []))} entities"
                            )
                        else:
                            logger.warning(
                                f"No result returned from KG integration for {paper['id']}"
                            )
                except Exception as e:
                    logger.error(
                        f"Failed to add paper {paper['id']} to KG: {e}", exc_info=True
                    )

    async def _update_existing_paper(
        self,
        db: AsyncSession,
        paper: Dict[str, Any],
        changed_fields: List[str],
        organization_id: Any,
    ):
        """Update an existing paper in the database (tenant-scoped)."""
        result = await db.execute(self._paper_lookup_stmt(paper["id"], organization_id))
        doc = result.scalar_one_or_none()

        if doc:
            # Update fields that changed
            if "title" in changed_fields:
                doc.title = paper.get("title", doc.title) or doc.title
            if "abstract" in changed_fields:
                doc.content_text = paper.get("abstract", doc.content_text)

            # Copy-update-reassign so SQLAlchemy detects the JSON mutation.
            md = dict(doc.document_metadata or {})
            md.update(
                {
                    "arxiv_id": paper["id"],
                    "authors": paper.get("authors", []),
                    "categories": paper.get("categories", []),
                    "primary_category": paper.get("primary_category"),
                    "published": paper.get("published"),
                    "doi": paper.get("doi"),
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }
            )
            doc.document_metadata = md

            await db.commit()

    async def _update_knowledge_graph(self, paper: Dict[str, Any]):
        """Update knowledge graph with changed paper"""
        try:
            async with ArXivKnowledgeGraphIntegration() as kg:
                # Extract new entities and relationships
                await kg.process_paper_kg_integration(paper)
        except Exception as e:
            logger.warning(f"Failed to update KG for paper {paper['id']}: {e}")

    async def _mark_paper_deleted(
        self, db: AsyncSession, paper_id: str, organization_id: Any
    ):
        """Soft-mark a paper as deleted in the database (tenant-scoped).

        There is no "deleted" ProcessingStatus — record the soft-delete via a
        metadata flag and leave processing_status untouched.
        """
        result = await db.execute(self._paper_lookup_stmt(paper_id, organization_id))
        doc = result.scalar_one_or_none()

        if doc:
            # Copy-update-reassign so SQLAlchemy detects the JSON mutation.
            md = dict(doc.document_metadata or {})
            md["deleted"] = True
            md["deleted_date"] = datetime.now(timezone.utc).isoformat()
            doc.document_metadata = md
            await db.commit()

    async def track_category_changes(
        self,
        categories: List[str],
        organization_id: Any,
        user_id: Optional[Any] = None,
        days_back: int = 7,
        update_db: bool = True,
    ) -> Dict[str, Any]:
        """
        Track changes for specific categories over a time period, scoped to a
        single organization.

        Args:
            categories: List of arXiv categories to track
            organization_id: Tenant owning tracking state + created documents
            user_id: User to attribute created documents to
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
                    date_from=datetime.now(timezone.utc) - timedelta(days=days_back),
                )
                all_papers.extend(papers)
                logger.info(f"Found {len(papers)} papers in {category}")

        # Remove duplicates
        seen_ids = set()
        unique_papers = []
        for paper in all_papers:
            if paper["id"] not in seen_ids:
                seen_ids.add(paper["id"])
                unique_papers.append(paper)

        logger.info(f"Total unique papers: {len(unique_papers)}")

        # Detect changes — restrict deletion candidates to the scanned
        # categories, and never mutate persisted state on a dry run.
        changes = self.detect_changes(
            unique_papers,
            organization_id=organization_id,
            tracked_categories=set(categories),
            commit=update_db,
        )

        # Group changes by type
        changes_by_type = {}
        for change in changes:
            if change.change_type not in changes_by_type:
                changes_by_type[change.change_type] = []
            changes_by_type[change.change_type].append(change)

        logger.info(
            f"Detected changes: {len(changes_by_type.get('new', []))} new, "
            f"{len(changes_by_type.get('updated', []))} updated, "
            f"{len(changes_by_type.get('deleted', []))} deleted"
        )

        # Apply changes if requested
        if update_db and changes:
            summary = await self.apply_changes(
                changes,
                organization_id=organization_id,
                user_id=user_id,
                update_kg=True,
            )
            logger.info(f"Applied changes: {summary}")
        else:
            summary = {
                "new": len(changes_by_type.get("new", [])),
                "updated": len(changes_by_type.get("updated", [])),
                "deleted": len(changes_by_type.get("deleted", [])),
                "errors": 0,
            }

        return {
            "categories": categories,
            "period_days": days_back,
            "papers_found": len(unique_papers),
            "changes_detected": len(changes),
            "changes_by_type": changes_by_type,
            "applied": update_db,
            "summary": summary,
        }

    async def get_change_history(
        self, organization_id: Any, paper_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get change history for papers within a single organization.

        Args:
            organization_id: Tenant whose tracking state to read
            paper_id: Specific paper ID to get history for, or None for all

        Returns:
            List of change records
        """
        changes = []

        org_state = self.state.get("__orgs__", {}).get(str(organization_id), {})
        for pid, data in org_state.items():
            if paper_id and pid != paper_id:
                continue

            record = {
                "paper_id": pid,
                "current_hash": data.get("hash", ""),
                "last_seen": data.get("last_seen", ""),
                "deleted": bool(data.get("deleted", False)),
                "miss_count": data.get("miss_count", 0),
                "metadata": data.get("paper_metadata", {}),
            }
            changes.append(record)

        return changes

    async def cleanup_old_state(self, organization_id: Any, days: int = 90):
        """Clean up state records for papers not seen in specified days,
        scoped to a single organization."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        org_state = self._org_state(organization_id)
        to_remove = []
        for paper_id, data in org_state.items():
            last_seen = datetime.fromisoformat(data["last_seen"])
            # Convert last_seen to timezone-aware if it's naive
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            if last_seen < cutoff and not data.get("deleted"):
                to_remove.append(paper_id)

        for paper_id in to_remove:
            del org_state[paper_id]
            logger.info(f"Removed stale state for {paper_id}")

        if to_remove:
            self.save_state()

        return len(to_remove)


# Singleton instance
change_tracker = ArXivChangeTracker()


async def track_arxiv_changes(
    organization_id: Any,
    user_id: Optional[Any] = None,
    categories: List[str] = None,
    days_back: int = 1,
):
    """
    Convenience function to track arXiv changes for a single organization.

    Args:
        organization_id: Tenant owning tracking state + created documents
        user_id: User to attribute created documents to
        categories: Categories to track (defaults to popular categories)
        days_back: Days to look back for changes
    """
    if categories is None:
        categories = ["cs.AI", "cs.LG", "cs.CV", "quant-ph", "stat.ML"]

    return await change_tracker.track_category_changes(
        categories,
        organization_id=organization_id,
        user_id=user_id,
        days_back=days_back,
    )
