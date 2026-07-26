"""The arXiv rate gate must not burst, and must listen when arXiv says wait.

Two defects, both live:

* ``_ARXIV_MAX_WAIT_MS = 15000`` with a 3s interval meant only ~5 slots fit
  under the ceiling. Every caller past that got ``-1`` and fired **immediately
  with no reservation** — so a 10-paper ingest (the tool's own cap) ended in a
  simultaneous burst. The gate generated the 429 it exists to prevent, at
  exactly the batch size it was meant to smooth.
* The 429 retry slept a fixed 3s and never read ``Retry-After``, while arXiv's
  own message says to try again in 60 — guaranteeing the retry also 429'd.

Context: arXiv tightened server-side around 2026-02-25 and now returns 429s
even to callers honouring the documented 3s interval, so the client's job is
to degrade well, not merely to be polite.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestGateCeiling:
    def test_ceiling_covers_a_full_ingest_batch(self) -> None:
        """10 papers x 3s must fit under the cap, or the batch bursts."""
        from src.services.arxiv.arxiv_service import (
            _ARXIV_MAX_WAIT_MS,
            _ARXIV_MIN_INTERVAL_MS,
        )

        max_batch = 10  # _tool_ingest_arxiv rejects more than 10 per request
        needed_ms = (max_batch - 1) * _ARXIV_MIN_INTERVAL_MS
        assert _ARXIV_MAX_WAIT_MS >= needed_ms, (
            f"cap {_ARXIV_MAX_WAIT_MS}ms cannot queue a {max_batch}-paper batch "
            f"at {_ARXIV_MIN_INTERVAL_MS}ms spacing; callers past it fire unreserved"
        )

    def test_ceiling_stays_inside_the_tool_call_budget(self) -> None:
        """A cap above the tool timeout trades a 429 for a guaranteed timeout."""
        from src.services.agent._nodes_tools import AGENT_LLM_TIMEOUT_SECONDS
        from src.services.arxiv.arxiv_service import _ARXIV_MAX_WAIT_MS

        assert _ARXIV_MAX_WAIT_MS / 1000.0 < AGENT_LLM_TIMEOUT_SECONDS


class TestRetryAfter:
    def test_delta_seconds_header_is_honoured(self) -> None:
        from src.services.arxiv.arxiv_service import _retry_after_seconds

        assert _retry_after_seconds({"Retry-After": "10"}, default=3.0) == 10.0

    def test_case_insensitive(self) -> None:
        from src.services.arxiv.arxiv_service import _retry_after_seconds

        assert _retry_after_seconds({"retry-after": "7"}, default=3.0) == 7.0

    def test_large_value_is_clamped_not_obeyed_literally(self) -> None:
        """arXiv says 60s; the caller sits inside a tool-call timeout."""
        from src.services.arxiv.arxiv_service import _retry_after_seconds

        assert _retry_after_seconds({"Retry-After": "60"}, default=3.0) == 15.0

    def test_absent_header_falls_back_to_the_default(self) -> None:
        from src.services.arxiv.arxiv_service import _retry_after_seconds

        assert _retry_after_seconds({}, default=3.0) == 3.0

    def test_http_date_form_falls_back_rather_than_raising(self) -> None:
        from src.services.arxiv.arxiv_service import _retry_after_seconds

        header = {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
        assert _retry_after_seconds(header, default=3.0) == 3.0

    def test_garbage_header_falls_back(self) -> None:
        from src.services.arxiv.arxiv_service import _retry_after_seconds

        assert _retry_after_seconds({"Retry-After": "soon"}, default=3.0) == 3.0

    def test_negative_is_floored_at_zero(self) -> None:
        from src.services.arxiv.arxiv_service import _retry_after_seconds

        assert _retry_after_seconds({"Retry-After": "-5"}, default=3.0) == 0.0
