"""Regex PII redactor for memory values.

Run on every string we are about to persist to the long-term memory
store. Replaces emails, phone numbers, UUIDs, and postgres connection
strings with bracketed sentinels so the literal value never ends up
in the recall index.

Intentionally conservative — false positives (a UUID-shaped string in
prose) are cheap; false negatives (a real email stored verbatim) cost
us GDPR posture.
"""

from __future__ import annotations

import re
from typing import Final

_EMAIL_RE: Final = re.compile(r"\b[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
# US-ish phone with optional country code + separators.
_PHONE_RE: Final = re.compile(
    r"(?<!\w)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
_UUID_RE: Final = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
# postgres://user:pass@host:port/db or postgresql:// variant.
_PG_URL_RE: Final = re.compile(r"\bpostgres(?:ql)?://\S+\b")


def redact_pii(text: str | None) -> str:
    """Return *text* with emails, phones, UUIDs, and PG URLs replaced."""
    if not text:
        return ""
    out = _PG_URL_RE.sub("<postgres-url>", text)
    out = _EMAIL_RE.sub("<email>", out)
    out = _PHONE_RE.sub("<phone>", out)
    out = _UUID_RE.sub("<uuid>", out)
    return out


__all__ = ["redact_pii"]
