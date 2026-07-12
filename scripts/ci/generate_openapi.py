#!/usr/bin/env python3
"""Generate (or verify) the committed OpenAPI schema snapshot.

This is the backend half of the REST **contract ratchet** (audit finding C5).
The FastAPI app is the single source of truth for the REST contract; the
frontend's TypeScript request/response types are generated from the committed
snapshot (``backend/openapi.json``) via ``openapi-typescript``. CI regenerates
the snapshot and fails if it drifts from the committed copy, forcing every
contract change to travel with regenerated FE types in the *same* PR instead of
silently diverging from the hand-mirrored types.

The app imports **without booting infra** — it only needs an in-memory SQLite
URL and placeholder Azure OpenAI creds (the agent-graph constructor refuses to
import without them). No DB connection, Redis, or network call is made; missing
services log warnings but do not prevent ``app.openapi()`` from building.

Usage (run from the repo root)::

    # Regenerate and write backend/openapi.json
    python scripts/ci/generate_openapi.py

    # CI mode: rebuild the schema in-memory and diff it against the committed
    # snapshot; exit 1 with an actionable message if they differ.
    python scripts/ci/generate_openapi.py --check

Determinism: keys are sorted and the file ends with a trailing newline so the
committed snapshot and any CI regeneration are byte-identical for identical
source. ``info.title`` / ``info.version`` come from the static settings defaults
(``APP_NAME`` / ``VERSION``); the generator does not set them, so they must not
be overridden in the environment that produces the committed snapshot.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from pathlib import Path

# This file lives at <repo>/scripts/ci/generate_openapi.py — parents[2] is the
# repo root, and the FastAPI app is the `src` package under backend/.
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
DEFAULT_OUTPUT = BACKEND_DIR / "openapi.json"

# Placeholder env matching the CI unit-test lane. setdefault only — a real
# local/CI environment is never clobbered. ENVIRONMENT/DATABASE_URL keep the
# import offline; the Azure placeholders satisfy the agent-graph constructor.
_ENV_DEFAULTS = {
    "ENVIRONMENT": "testing",
    "DATABASE_URL": "sqlite:///:memory:",
    "AZURE_OPENAI_CHAT_ENDPOINT": "https://example.invalid",
    "AZURE_OPENAI_CHAT_API_KEY": "test-key-not-real",
    "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME": "test-deployment",
    "AZURE_OPENAI_CHAT_API_VERSION": "2024-02-01",
    "AZURE_OPENAI_ENDPOINT": "https://example.invalid",
    "AZURE_OPENAI_API_KEY": "test-key-not-real",
}


def _build_schema() -> dict:
    """Import the FastAPI app offline and return its OpenAPI schema."""
    for key, value in _ENV_DEFAULTS.items():
        os.environ.setdefault(key, value)

    # backend/ must be importable as the `src` package root regardless of cwd.
    backend = str(BACKEND_DIR)
    if backend not in sys.path:
        sys.path.insert(0, backend)

    from src.main import app  # noqa: E402  (import after env + sys.path setup)

    return app.openapi()


def _serialize(schema: dict) -> str:
    """Serialize deterministically: sorted keys + trailing newline."""
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed snapshot is up to date; do not write.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Snapshot path (default: backend/openapi.json).",
    )
    args = parser.parse_args(argv)

    output_path = Path(args.output)
    serialized = _serialize(_build_schema())

    if args.check:
        if not output_path.exists():
            print(
                f"ERROR: {output_path} does not exist. "
                "Run: python scripts/ci/generate_openapi.py",
                file=sys.stderr,
            )
            return 1
        committed = output_path.read_text(encoding="utf-8")
        if committed != serialized:
            diff = difflib.unified_diff(
                committed.splitlines(keepends=True),
                serialized.splitlines(keepends=True),
                fromfile=f"{output_path} (committed)",
                tofile="app.openapi() (regenerated)",
                n=2,
            )
            # Cap the diff so a large contract change does not flood CI logs.
            shown = 0
            for line in diff:
                sys.stderr.write(line)
                shown += 1
                if shown >= 200:
                    sys.stderr.write("... (diff truncated)\n")
                    break
            print(
                "\nERROR: backend contract changed; regenerate + review types.\n"
                "  1. python scripts/ci/generate_openapi.py\n"
                "  2. cd frontend && pnpm generate:api-types\n"
                "  3. review + commit backend/openapi.json and the regenerated types",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {output_path} is up to date.")
        return 0

    output_path.write_text(serialized, encoding="utf-8")
    print(f"Wrote {output_path} ({len(serialized)} bytes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
