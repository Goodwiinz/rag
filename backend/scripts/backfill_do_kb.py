"""CLI: backfill existing Documents into DigitalOcean Knowledge Bases.

Examples:
  python -m scripts.backfill_do_kb --org-id 11111111-...  --batch-size 50
  python -m scripts.backfill_do_kb --all --dry-run
  python -m scripts.backfill_do_kb --org-id 11111111-... --resume

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
    backfill_org,
    iter_organizations_to_backfill,
)

logger = logging.getLogger("do_kb_backfill")


def _print_report(report: BackfillReport) -> None:
    print(
        f"[org {report.organization_id}] completed={report.completed} "
        f"failed={report.failed} skipped={report.skipped} "
        f"last_doc={report.last_document_id} finished={report.finished}"
    )


async def _run(args: argparse.Namespace) -> int:
    if not settings.DO_KB_ENABLED:
        print("ERROR: DO_KB_ENABLED is false. Set it in .env first.", file=sys.stderr)
        return 2

    async with AsyncSessionLocal() as session:
        if args.org_id:
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
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
