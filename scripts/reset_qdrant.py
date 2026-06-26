"""Reset (delete) a Qdrant collection.

Consolidates the former reset_qdrant{,_debug,_env,_http}.py variants behind
CLI flags. Production credentials are never hardcoded: QDRANT_URL and
QDRANT_API_KEY must be provided via the environment.

Usage:
    python scripts/reset_qdrant.py --collection document_chunks
    python scripts/reset_qdrant.py --transport http --dry-run
    python scripts/reset_qdrant.py --force          # non-interactive, skips prod prompt
"""

from __future__ import annotations

import argparse
import os
import sys

VALID_IDENTIFIER = __import__("re").compile(r"^[A-Za-z_][A-Za-z0-9_\-]{0,63}$")


def _safe_collection(name: str) -> str:
    if not VALID_IDENTIFIER.match(name):
        raise ValueError(f"Invalid collection name: {name!r}")
    return name


def _is_production_url(url: str) -> bool:
    lowered = url.lower()
    return (
        "cloud.qdrant.io" in lowered
        or "qdrant.tech" in lowered
        or (
            lowered.startswith("https://")
            and "localhost" not in lowered
            and "127.0.0.1" not in lowered
        )
    )


def reset_qdrant(
    collection_name: str,
    transport: str = "auto",
    dry_run: bool = False,
    force: bool = False,
    debug: bool = False,
) -> None:
    url = os.environ.get("QDRANT_URL")
    key = os.environ.get("QDRANT_API_KEY")
    if not url:
        sys.exit(
            "Error: QDRANT_URL environment variable is required (no hardcoded fallback)."
        )
    if not key:
        sys.exit(
            "Error: QDRANT_API_KEY environment variable is required (no hardcoded fallback)."
        )

    collection_name = _safe_collection(collection_name)

    if _is_production_url(url) and not force:
        print(f"⚠️  Targeting a remote/production Qdrant instance:\n    {url}")
        confirm = input("Type 'yes' to permanently delete the collection: ")
        if confirm.strip().lower() != "yes":
            sys.exit("Aborted.")

    if dry_run:
        print(f"[dry-run] Would delete collection '{collection_name}' at {url}")
        return

    if transport in ("auto", "grpc"):
        from qdrant_client import QdrantClient

        client = QdrantClient(url=url, api_key=key, check_compatibility=not debug)
        try:
            if debug:
                collections = client.get_collections()
                print("Existing collections:")
                for c in collections.collections:
                    print(f" - {c.name}")
            if (
                any(
                    c.name == collection_name
                    for c in (client.get_collections().collections if debug else [])
                )
                or not debug
            ):
                client.delete_collection(collection_name)
                print(f"Deleted collection: {collection_name}")
            else:
                print(f"Collection {collection_name} not found.")
        except Exception as e:
            print(f"Error deleting collection {collection_name}: {e}")
    else:
        import requests

        delete_url = f"{url.rstrip('/')}/collections/{collection_name}"
        headers = {"api-key": key, "Content-Type": "application/json"}
        print(f"Sending DELETE to {delete_url}")
        try:
            response = requests.delete(delete_url, headers=headers, timeout=30)
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")
        except Exception as e:
            print(f"Exception during request: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset (delete) a Qdrant collection.")
    parser.add_argument(
        "--collection", default="document_chunks", help="Collection name to delete"
    )
    parser.add_argument(
        "--transport",
        choices=["auto", "http", "grpc"],
        default="auto",
        help="Transport: grpc client (auto/grpc) or raw HTTP (http)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without modifying data",
    )
    parser.add_argument(
        "--force", action="store_true", help="Skip production confirmation prompt"
    )
    parser.add_argument(
        "--debug", action="store_true", help="List collections before deleting"
    )
    args = parser.parse_args()
    reset_qdrant(
        collection_name=args.collection,
        transport=args.transport,
        dry_run=args.dry_run,
        force=args.force,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
