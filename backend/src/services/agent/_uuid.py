"""Shared UUID regexes for the agent layer.

Two flavours:

- ``UUID_STRICT_RE``: anchored (``^...$``) — use for whole-string validation
  (e.g. rejecting LLM-fabricated IDs like ``"proj_12345"`` in tool args).
- ``UUID_SEARCH_RE``: bounded (``\\b...\\b``) — use for extracting an
  embedded UUID from free text (e.g. ``/projects/<uuid>`` URLs).
"""

import re

UUID_STRICT_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-" r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
UUID_STRICT_RE = re.compile(UUID_STRICT_PATTERN)

UUID_SEARCH_RE = re.compile(
    r"\b([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b"
)
