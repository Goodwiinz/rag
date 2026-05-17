"""Load per-subgraph AGENTS_*.md driver protocols.

Inspired by K-Dense's `rowan-autosearch` AGENTS.md pattern: externalize the
agent's loop spec from Python strings into editable markdown files. This
lets non-developers tune subgraph behavior without code changes, and keeps
prompt revisions versionable + diffable in git.

Files live alongside this module:
    AGENTS_research.md
    AGENTS_writing.md
    AGENTS_data.md

The loader is process-cached (read once at import time per subgraph). Set
``AGENT_AGENTS_MD_RELOAD=true`` in the environment to bypass the cache —
useful when iterating on the markdown without restarting the backend.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_AGENTS_DIR = Path(__file__).parent
_CACHE: dict[str, str] = {}


def _reload_enabled() -> bool:
    """Per-call env check so test fixtures can flip without restart."""
    return os.environ.get("AGENT_AGENTS_MD_RELOAD", "").lower() in (
        "1",
        "true",
        "yes",
    )


def load_agents_md(subgraph: str) -> str:
    """Return the body of ``AGENTS_<subgraph>.md`` (without the YAML/H1
    boilerplate stripped — the caller composes the full system prompt).

    Returns an empty string if the file is missing — callers should
    treat that as a "fall back to inline prompt" signal rather than
    crashing the agent.
    """
    if not _reload_enabled() and subgraph in _CACHE:
        return _CACHE[subgraph]

    path = _AGENTS_DIR / f"AGENTS_{subgraph}.md"
    try:
        content = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning(
            "AGENTS_%s.md not found at %s — using empty driver protocol",
            subgraph,
            path,
        )
        content = ""
    except Exception as exc:  # noqa: BLE001 - never crash on prompt load
        logger.warning(
            "Failed to read AGENTS_%s.md: %s — using empty driver protocol",
            subgraph,
            exc,
        )
        content = ""

    _CACHE[subgraph] = content
    return content
