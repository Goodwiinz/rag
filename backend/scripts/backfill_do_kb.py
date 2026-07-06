"""CLI: backfill existing Documents into DigitalOcean Knowledge Bases.

Examples:
  python -m scripts.backfill_do_kb --org-id 11111111-...  --batch-size 50
  python -m scripts.backfill_do_kb --all --dry-run
  python -m scripts.backfill_do_kb --org-id 11111111-... --resume

Recovery (DO KB deleted on DO's side):
  python -m scripts.backfill_do_kb --org-id 11111111-... --reprovision

  Nulls the org's dead do_kb_uuid + every doc's dead do_kb_data_source_uuid +
  resets the backfill progress row, THEN backfills — which provisions a FRESH
  KB and re-adds every data source + kicks indexing. Without --reprovision a
  backfill of a deleted-KB org is a no-op (ensure_kb_for_org only null-checks
  the uuid; sync skips docs whose data-source uuid is already set).

Resumable: progress is committed per document so re-runs continue from
last_document_id without re-uploading already synced docs.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.services.do_kb import (
    BackfillReport,
    ReprovisionResult,
    backfill_org,
    iter_organizations_to_backfill,
    reprovision_org,
)

logger = logging.getLogger("do_kb_backfill")


def _print_reprovision(result: ReprovisionResult) -> None:
    print(
        f"[org {result.organization_id}] reprovision reset: "
        f"old_kb={result.old_kb_uuid or '(none)'} cleared → will provision fresh; "
        f"docs_reset={result.docs_reset}"
    )


def _print_report(report: BackfillReport) -> None:
    print(
        f"[org {report.organization_id}] completed={report.completed} "
        f"failed={report.failed} skipped={report.skipped} "
        f"last_doc={report.last_document_id} finished={report.finished} "
        f"indexing_started={report.indexing_started}"
    )
    if report.completed > 0 and not report.indexing_started:
        print(
            f"  WARNING: uploaded {report.completed} data sources but "
            "indexing_started=False — docs are NOT queryable yet. "
            "Re-run to retry the indexing kick.",
            file=sys.stderr,
        )


async def _run(args: argparse.Namespace) -> int:
    if not settings.DO_KB_ENABLED:
        print("ERROR: DO_KB_ENABLED is false. Set it in .env first.", file=sys.stderr)
        return 2

    if args.reprovision and args.dry_run:
        print(
            "ERROR: --reprovision cannot be combined with --dry-run "
            "(it mutates DB state to force a fresh KB).",
            file=sys.stderr,
        )
        return 2

    # Reprovisioning nulls the org's cached KB uuid + every doc's data-source
    # uuid so backfill provisions a fresh KB. Doing that for EVERY org at once is
    # destructive — require an explicit --yes.
    if args.reprovision and not args.org_id and not args.yes:
        print(
            "ERROR: --reprovision --all reprovisions EVERY org's KB (destructive). "
            "Re-run with --yes to confirm, or pass --org-id for a single org.",
            file=sys.stderr,
        )
        return 2

    async with AsyncSessionLocal() as session:
        if args.org_id:
            if args.reprovision:
                _print_reprovision(await reprovision_org(session, args.org_id))
            report = await backfill_org(
                session,
                args.org_id,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
            )
            _print_report(report)
            return 0

        orgs = await iter_organizations_to_backfill(session)
        if not orgs:
            print("No active organizations found.")
            return 0

        for org in orgs:
            try:
                if args.reprovision:
                    _print_reprovision(await reprovision_org(session, str(org.id)))
                report = await backfill_org(
                    session,
                    str(org.id),
                    batch_size=args.batch_size,
                    dry_run=args.dry_run,
                )
                _print_report(report)
            except Exception as exc:  # noqa: BLE001
                logger.exception("backfill failed for org %s", org.id)
                print(f"[org {org.id}] FAILED: {exc}", file=sys.stderr)
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--org-id", type=str, help="Backfill a single organization")
    target.add_argument(
        "--all", action="store_true", help="Backfill every active organization"
    )
    parser.add_argument(
        "--batch-size", type=int, default=25, help="Documents per DB query (default 25)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Iterate without calling DO KB or persisting state changes",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="No-op flag for clarity; backfill is always resumable from progress row",
    )
    parser.add_argument(
        "--reprovision",
        action="store_true",
        help=(
            "Recovery: the org's DO KB was deleted on DO's side. BEFORE backfill, "
            "null the org's cached do_kb_uuid + every doc's do_kb_data_source_uuid "
            "+ reset progress, so backfill provisions a FRESH KB and re-indexes "
            "everything. Requires --org-id (use --all --yes to reprovision every org)."
        ),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm a destructive --reprovision --all (reprovisions every org).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
