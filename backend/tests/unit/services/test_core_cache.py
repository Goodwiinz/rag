import logging
from unittest.mock import AsyncMock

import pytest

from src.services.core.cache import cache_get


@pytest.mark.asyncio
async def test_cache_get_degrades_to_a_warning_with_exception_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = AsyncMock()
    client.get.side_effect = ConnectionError("connection lost")

    with caplog.at_level(logging.WARNING, logger="src.services.core.cache"):
        result = await cache_get(client, "arxiv:search:cache-key")

    assert result is None
    record = caplog.records[-1]
    assert record.levelno == logging.WARNING
    assert record.exc_info is not None
