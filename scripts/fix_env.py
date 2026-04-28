"""Generate a development .env file from a template.

Issue #379: previously this script wrote a hard-coded .env containing specific
Azure endpoint URLs and placeholder secrets directly into source control. It
now reads each value from the environment, refuses to overwrite an existing
.env without --force, and surfaces which fields still hold placeholders so the
operator knows what to fill in.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PLACEHOLDER = "REPLACE_ME"


def _env(name: str, default: str = PLACEHOLDER) -> str:
    return os.environ.get(name, default)


def render_env() -> tuple[str, list[str]]:
    """Return (file_contents, list_of_fields_left_as_placeholder)."""
    fields = {
        "APP_NAME": _env("APP_NAME", "Multimodal Enterprise RAG System"),
        "VERSION": _env("APP_VERSION", "1.0.0"),
        "ENVIRONMENT": _env("ENVIRONMENT", "development"),
        "DEBUG": _env("DEBUG", "True"),
        "SECRET_KEY": _env("SECRET_KEY"),
        "DATABASE_URL": _env(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/multimodal_rag",
        ),
        "REDIS_URL": _env("REDIS_URL", "redis://localhost:6379"),
        "NEO4J_URI": _env("NEO4J_URI", "bolt://localhost:7687"),
        "NEO4J_USER": _env("NEO4J_USER", "neo4j"),
        "NEO4J_PASSWORD": _env("NEO4J_PASSWORD"),
        "QDRANT_URL": _env("QDRANT_URL", "http://localhost:6333"),
        "QDRANT_API_KEY": _env("QDRANT_API_KEY", ""),
        "AZURE_OPENAI_API_KEY": _env("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_ENDPOINT": _env("AZURE_OPENAI_ENDPOINT"),
        "AZURE_OPENAI_EMBEDDING_ENDPOINT": _env("AZURE_OPENAI_EMBEDDING_ENDPOINT"),
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME": _env(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small"
        ),
        "AZURE_OPENAI_API_VERSION": _env("AZURE_OPENAI_API_VERSION", "2023-05-15"),
        "AZURE_OPENAI_CHAT_API_KEY": _env("AZURE_OPENAI_CHAT_API_KEY"),
        "AZURE_OPENAI_CHAT_ENDPOINT": _env("AZURE_OPENAI_CHAT_ENDPOINT"),
        "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME": _env(
            "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini"
        ),
        "AZURE_OPENAI_CHAT_API_VERSION": _env(
            "AZURE_OPENAI_CHAT_API_VERSION", "2024-06-01"
        ),
        "EMBEDDING_PROVIDER": _env("EMBEDDING_PROVIDER", "azure_openai"),
        "EMBEDDING_MODEL": _env("EMBEDDING_MODEL", "text-embedding-3-small"),
        "COHERE_RERANK_ENDPOINT": _env("COHERE_RERANK_ENDPOINT"),
        "COHERE_RERANK_API_KEY": _env("COHERE_RERANK_API_KEY"),
        "COHERE_RERANK_MODEL": _env("COHERE_RERANK_MODEL", "Cohere-rerank-v4.0-pro"),
    }

    body = "\n".join(f'{k}="{v}"' for k, v in fields.items()) + "\n"
    placeholders = [name for name, value in fields.items() if value == PLACEHOLDER]
    return body, placeholders


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path", default=".env", help="Output path (default: .env in cwd)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite an existing file"
    )
    args = parser.parse_args()

    out_path = Path(args.path)
    if out_path.exists() and not args.force:
        print(
            f"Refusing to overwrite existing {out_path} (use --force to replace).",
            file=sys.stderr,
        )
        return 1

    body, placeholders = render_env()
    out_path.write_text(body)

    print(f"Wrote {out_path}.")
    if placeholders:
        print(
            "Warning: the following fields still hold the REPLACE_ME placeholder — "
            "set them via environment variables and re-run:",
            file=sys.stderr,
        )
        for name in placeholders:
            print(f"  - {name}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
