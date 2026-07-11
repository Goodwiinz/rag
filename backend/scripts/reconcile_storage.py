"""CLI: report-only reconcile of DO Spaces objects against Postgres (audit D6).

Lists every object an organization owns in Spaces and diffs it against the keys
still referenced by live (non-deleted) rows, then LOGS + prints the orphans.
Never deletes anything — it surfaces objects a failed/incomplete delete left
behind (originals, canonical KB ``.txt`` mirrors, figure PNG crops).

Examples:
  python -m scripts.reconcile_storage --org-id 11111111-...
  python -m scripts.reconcile_storage --all
  python -m scripts.reconcile_storage --all --show-keys

Requires the s3/Spaces backend to be configured (S3_ENDPOINT_URL / S3_ACCESS_KEY
/ S3_SECRET_KEY); reconciliation is meaningless without it.

Follow-up (out of scope here): wire ``reconcile_all_orgs_storage`` into
Celery beat as a scheduled sweep (celery_app.py is owned by another in-flight
PR).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import List

from src.core.database import AsyncSessionLocal
from src.services.documents.storage_reconcile import (
    StorageReconcileReport,
    reconcile_all_orgs_storage,
    reconcile_org_storage,
)

logger = logging.getLogger("storage_reconcile")


def _print_report(report: StorageReconcileReport, *, show_keys: bool) -> None:
    print(
        f"[org {report.organization_id}] listed={report.listed_count} "
        f"referenced={report.referenced_count} orphans={report.orphan_count}"
    )
    if report.orphan_count and show_keys:
        for key in report.orphan_keys:
            print(f"    ORPHAN {key}")


async def _run(args: argparse.Namespace) -> int:
    # Construct the helper up front so a misconfigured backend fails fast with a
    # clear message rather than deep inside the sweep.
    try:
        from src.core.s3_client import S3StorageHelper

        s3_helper = S3StorageHelper()
    except Exception as exc:  # noqa: BLE001
        print(
            f"ERROR: S3/Spaces is not configured ({exc}). "
            "Set S3_ENDPOINT_URL / S3_ACCESS_KEY / S3_SECRET_KEY first.",
            file=sys.stderr,
        )
        return 2

    async with AsyncSessionLocal() as session:
        if args.org_id:
            report = await reconcile_org_storage(
                session, args.org_id, s3_helper=s3_helper
            )
            _print_report(report, show_keys=args.show_keys)
            reports: List[StorageReconcileReport] = [report]
        else:
            reports = await reconcile_all_orgs_storage(session, s3_helper=s3_helper)
            for report in reports:
                _print_report(report, show_keys=args.show_keys)

    total_orphans = sum(r.orphan_count for r in reports)
    print(
        f"Done: {len(reports)} org(s) scanned, {total_orphans} orphan object(s) found."
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--org-id", type=str, help="Reconcile a single organization")
    target.add_argument(
        "--all", action="store_true", help="Reconcile every active organization"
    )
    parser.add_argument(
        "--show-keys",
        action="store_true",
        help="Print every orphan key (not just the count) to stdout",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
