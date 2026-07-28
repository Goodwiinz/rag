"""Shared UUID regexes for the agent layer.

Two flavours:

- ``UUID_STRICT_RE``: anchored (``^...$``) — use for whole-string validation
  (e.g. rejecting LLM-fabricated IDs like ``"proj_12345"`` in tool args).
- ``UUID_SEARCH_RE``: bounded (``\\b...\\b``) — use for extracting an
  embedded UUID from free text (e.g. ``/projects/<uuid>`` URLs).
"""

import re

UUID_STRICT_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

UUID_SEARCH_RE = re.compile(
    r"\b([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b"
)


def _extract_project_id_from_text(text):
    """Return the first project UUID found in *text*, preferring ``/projects/<uuid>``.

    Falls back to any standalone UUID in the text. Returns ``None`` if no
    UUID is present. (Moved from ``graph.py``.)
    """
    if not text:
        return None
    project_url_match = re.search(
        r"/projects/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        text,
    )
    if project_url_match:
        return project_url_match.group(1).lower()
    bare_match = UUID_SEARCH_RE.search(text)
    return bare_match.group(1).lower() if bare_match else None
