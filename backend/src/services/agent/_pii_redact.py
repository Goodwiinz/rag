"""Regex PII redactor for memory values.

Run on every string we are about to persist to the long-term memory
store. Replaces emails, phone numbers, UUIDs, postgres connection
strings, and bearer tokens / API keys with bracketed sentinels so the
literal value never ends up in the recall index.

Intentionally conservative — false positives (a UUID-shaped string in
prose) are cheap; false negatives (a real email stored verbatim) cost
us GDPR posture.
"""

from __future__ import annotations

import re
from typing import Final

_EMAIL_RE: Final = re.compile(r"\b[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
# US-ish phone with optional country code + separators.
# (?<!\d\.) prevents matching mid-IPv4 ("192.168.100.1001") or mid-version
# ("v1.234.567.8901") where a digit-group is preceded by "<digit>.".
_PHONE_RE: Final = re.compile(
    r"(?<!\w)(?<!\d\.)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
_UUID_RE: Final = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
# postgres://user:pass@host:port/db or postgresql:// variant.
_PG_URL_RE: Final = re.compile(r"\bpostgres(?:ql)?://\S+\b")
# Bearer tokens / API keys: JWT, OpenAI (sk-proj-), Anthropic (sk-ant-),
# GitHub PAT (ghp_, gho_, github_pat_).
_TOKEN_RE: Final = re.compile(
    r"\b(?:eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_.-]{20,}"  # JWT
    r"|sk-(?:proj|ant)-[A-Za-z0-9_-]{20,}"                                  # OpenAI / Anthropic
    r"|gh[ps]_[A-Za-z0-9]{30,}"                                             # GitHub PAT / OAuth
    r"|github_pat_[A-Za-z0-9_]{30,})\b"
)


def redact_pii(text: str | None) -> str:
    """Return *text* with emails, phones, UUIDs, PG URLs, and tokens replaced."""
    if not text:
        return ""
    if not isinstance(text, str):
        # Best-effort: non-str inputs (multimodal HumanMessage.content as
        # list[dict], ints, bytes, etc.) cannot be regex-redacted safely.
        # Coerce to empty so the caller's save still succeeds with a
        # placeholder query rather than raising mid-re.sub.
        return ""
    out = _PG_URL_RE.sub("<postgres-url>", text)
    out = _TOKEN_RE.sub("<token>", out)
    out = _EMAIL_RE.sub("<email>", out)
    out = _PHONE_RE.sub("<phone>", out)
    out = _UUID_RE.sub("<uuid>", out)
    return out


__all__ = ["redact_pii"]
