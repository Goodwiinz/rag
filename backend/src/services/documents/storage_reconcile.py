"""Report-only Spaces ⇄ Postgres storage reconciler (audit finding D6).

Lists the objects an organization owns in DO Spaces and diffs them against the
keys still referenced by *live* (non-deleted) rows in Postgres, then LOGS the
orphans. It never deletes anything — deletion is the delete path's job
(``FileService.delete_physical_file``); this is the safety net that surfaces
objects left behind by a delete whose best-effort storage cleanup failed, or by
documents deleted before the delete path enumerated every object class.

Three object classes accumulate under an org's prefixes:

* originals   — ``{documents,images,audio,video}/{org}/{doc}/…`` (``storage_path``)
* KB text     — ``documents/{org}/{doc}.txt`` (canonical DO-KB text mirror)
* figure PNGs — ``figures/{org}/{doc}/…`` (``MultimodalContent`` storage keys)

An object is an orphan when it lives under an org prefix but no live row of that
org references it. Every referenced key is derived from live rows, so a live
document's objects can never be reported (let alone deleted). All queries are
organization-scoped.

Scheduled entry point is a plain async function so a Celery-beat task can call
it later (beat wiring intentionally out of scope for this PR); a manual CLI
lives at ``backend/scripts/reconcile_storage.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.document_processing import MultimodalContent
from src.services.documents.object_keys import FIGURES_KEY_PREFIX, canonical_text_key

logger = structlog.get_logger(__name__)

# Top-level Spaces prefixes an org's objects live under. Originals are keyed by
# document *type* (``FileService.TYPE_TO_BUCKET`` → documents/images/audio/video),
# the canonical KB text mirror under ``documents/``, and figure crops under
# ``figures/``. Scanning all five per org covers every object class.
OBJECT_CLASS_PREFIXES = ("documents", "images", "audio", "video", FIGURES_KEY_PREFIX)

# Cap on how many orphan keys are logged inline (the full list is on the report).
_LOG_SAMPLE = 100


@dataclass(frozen=True)
class StorageReconcileReport:
    """Result of reconciling one organization's Spaces objects with Postgres."""

    organization_id: str
    listed_count: int
    referenced_count: int
    orphan_keys: List[str] = field(default_factory=list)

    @property
    def orphan_count(self) -> int:
        return len(self.orphan_keys)


def _classify_key(key: str) -> str:
    """Best-effort object-class label for logs (does not affect the diff)."""
    if key.startswith(f"{FIGURES_KEY_PREFIX}/"):
        return "figure"
    if key.endswith(".txt"):
        return "kb_text"
    return "original"


async def _referenced_keys(session: AsyncSession, org_id: str) -> Set[str]:
    """Every Spaces key referenced by an org's *live* rows.

    Derived strictly from non-deleted rows so a live document's objects are
    never flagged as orphans:

    * original upload key (``storage_path``) + canonical ``.txt`` mirror key, per
      non-deleted ``Document``;
    * figure PNG keys from each non-deleted document's ``MultimodalContent``
      rows (``content_metadata['storage_key']``).
    """
    referenced: Set[str] = set()

    doc_result = await session.execute(
        select(Document).where(
            Document.organization_id == org_id,
            Document.is_deleted.is_(False),
        )
    )
    for doc in doc_result.scalars().all():
        if doc.storage_path:
            referenced.add(doc.storage_path)
        # Canonical KB text mirror is a *referenced* key even when it was never
        # uploaded (DO_KB off / no content_text): a non-existent key simply
        # won't appear in the listing, and including it protects a live doc's
        # .txt from a false-orphan flag.
        referenced.add(canonical_text_key(doc))

    fig_result = await session.execute(
        select(MultimodalContent.content_metadata)
        .join(Document, Document.id == MultimodalContent.document_id)
        .where(
            MultimodalContent.organization_id == org_id,
            Document.organization_id == org_id,
            Document.is_deleted.is_(False),
        )
    )
    for metadata in fig_result.scalars().all():
        if isinstance(metadata, dict):
            storage_key = metadata.get("storage_key")
            if storage_key:
                referenced.add(storage_key)

    return referenced


def _listed_keys(s3_helper, org_id: str) -> Set[str]:
    """Every object key under the org's Spaces prefixes."""
    listed: Set[str] = set()
    for prefix in OBJECT_CLASS_PREFIXES:
        listed.update(s3_helper.list_objects(f"{prefix}/{org_id}/"))
    return listed


async def reconcile_org_storage(
    session: AsyncSession,
    org_id: str,
    *,
    s3_helper=None,
) -> StorageReconcileReport:
    """Reconcile one organization's Spaces objects against Postgres and LOG the
    orphans. Report-only — never deletes.

    ``s3_helper`` is injectable for tests; by default an ``S3StorageHelper`` is
    constructed (raising if S3/Spaces is unconfigured — reconciliation only
    makes sense against the s3 backend).
    """
    if s3_helper is None:
        from src.core.s3_client import S3StorageHelper

        s3_helper = S3StorageHelper()

    org_id = str(org_id)
    referenced = await _referenced_keys(session, org_id)
    listed = _listed_keys(s3_helper, org_id)
    orphan_keys = sorted(listed - referenced)

    report = StorageReconcileReport(
        organization_id=org_id,
        listed_count=len(listed),
        referenced_count=len(referenced),
        orphan_keys=orphan_keys,
    )

    if orphan_keys:
        logger.warning(
            "storage_reconcile_orphans_found",
            organization_id=org_id,
            listed=report.listed_count,
            referenced=report.referenced_count,
            orphan_count=report.orphan_count,
        )
        for key in orphan_keys[:_LOG_SAMPLE]:
            logger.warning(
                "storage_reconcile_orphan",
                organization_id=org_id,
                key=key,
                object_class=_classify_key(key),
            )
        if report.orphan_count > _LOG_SAMPLE:
            logger.warning(
                "storage_reconcile_orphan_log_truncated",
                organization_id=org_id,
                logged=_LOG_SAMPLE,
                total=report.orphan_count,
            )
    else:
        logger.info(
            "storage_reconcile_clean",
            organization_id=org_id,
            listed=report.listed_count,
            referenced=report.referenced_count,
        )

    return report


async def reconcile_all_orgs_storage(
    session: AsyncSession,
    *,
    s3_helper=None,
) -> List[StorageReconcileReport]:
    """Reconcile every active organization (scheduled/whole-fleet entry point).

    Constructs the S3 helper once and reuses it across orgs. Failure-isolated
    per org: one org's error is logged and the sweep continues.
    """
    if s3_helper is None:
        from src.core.s3_client import S3StorageHelper

        s3_helper = S3StorageHelper()

    from src.models.organization import Organization

    org_result = await session.execute(
        select(Organization.id).where(Organization.is_active.is_(True))
    )
    org_ids = [str(oid) for oid in org_result.scalars().all()]

    reports: List[StorageReconcileReport] = []
    for org_id in org_ids:
        try:
            reports.append(
                await reconcile_org_storage(session, org_id, s3_helper=s3_helper)
            )
        except Exception:  # noqa: BLE001 - one bad org must not abort the sweep
            logger.warning(
                "storage_reconcile_org_failed",
                organization_id=org_id,
                exc_info=True,
            )
    return reports
