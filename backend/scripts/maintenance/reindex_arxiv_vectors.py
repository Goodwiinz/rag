"""
Reindex arXiv vectors with the current embedding model.

Usage:
  python backend/scripts/maintenance/reindex_arxiv_vectors.py \
    --organization-id <org-id> \
    --batch-size 50 \
    --dry-run
"""

import argparse
import json

from src.services.search.vector_search_service import vector_search_service


def main() -> int:
    parser = argparse.ArgumentParser(description="Reindex arXiv vectors")
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--all-content",
        action="store_true",
        help="Reindex all content in the organization instead of arXiv-only",
    )
    args = parser.parse_args()

    result = vector_search_service.reindex_all_content(
        organization_id=args.organization_id,
        batch_size=args.batch_size,
        arxiv_only=not args.all_content,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("success", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())

