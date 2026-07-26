"""PDF fetches must not open one connection per paper.

The Redis slot gate covers ``export.arxiv.org/api`` only. ``ingest_papers``
gathers a whole batch at once (``batch_size=10``) against a session built with
``TCPConnector(limit=10)``, so a ten-paper ingest hit ``arxiv.org/pdf`` ten
times simultaneously — the least polite thing this service does, and entirely
invisible to the gate.

Deliberately a concurrency cap rather than the 3s API gate: ten papers
serialized at 3s is ~27s of pure waiting inside the 50s tool budget, which
trades a burst for a guaranteed timeout. ``test_deep_queue_proceeds_now``
rejects that same trade on the API path.
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.unit


class TestSemaphore:
    def test_cap_is_small_but_not_serial(self) -> None:
        from src.services.arxiv.arxiv_service import _MAX_CONCURRENT_PDF_DOWNLOADS

        assert 1 < _MAX_CONCURRENT_PDF_DOWNLOADS < 10, (
            "1 would serialize a batch past the tool budget; 10 is the burst "
            "this exists to remove"
        )

    async def test_same_loop_reuses_one_semaphore(self) -> None:
        """A fresh semaphore per call would cap nothing."""
        from src.services.arxiv.arxiv_service import _pdf_download_semaphore

        assert _pdf_download_semaphore() is _pdf_download_semaphore()

    def test_a_new_event_loop_gets_its_own_semaphore(self) -> None:
        """Module-level Semaphores bind to their creating loop.

        This service runs under uvicorn and under Celery workers; reusing a
        semaphore across loops raises "attached to a different loop".
        """
        from src.services.arxiv.arxiv_service import _pdf_download_semaphore

        first = asyncio.run(_as_coro(_pdf_download_semaphore))
        second = asyncio.run(_as_coro(_pdf_download_semaphore))

        assert first is not second

    async def test_concurrency_never_exceeds_the_cap(self) -> None:
        """The property that matters, measured rather than asserted by shape."""
        from src.services.arxiv.arxiv_service import (
            _MAX_CONCURRENT_PDF_DOWNLOADS,
            _pdf_download_semaphore,
        )

        live = 0
        peak = 0

        async def worker() -> None:
            nonlocal live, peak
            async with _pdf_download_semaphore():
                live += 1
                peak = max(peak, live)
                await asyncio.sleep(0.01)
                live -= 1

        await asyncio.gather(*(worker() for _ in range(10)))

        assert peak <= _MAX_CONCURRENT_PDF_DOWNLOADS, (
            f"{peak} simultaneous fetches — a 10-paper batch must not open one "
            "connection per paper"
        )


async def _as_coro(fn):  # type: ignore[no-untyped-def]
    return fn()
