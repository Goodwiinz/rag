"""Shared fixtures for agent-service tests.

Drains any fire-and-forget background tasks created by ``memory_save_node``
after each test so mock assertions in existing tests remain synchronously
accurate. Without this, tasks created via ``asyncio.create_task`` in
``_persist_memory_async`` would still be pending when test assertions run.
"""

from __future__ import annotations

import asyncio

import pytest

from src.services.agent._nodes_memory import _BACKGROUND_TASKS


@pytest.fixture(autouse=True)
async def drain_memory_background_tasks() -> None:  # type: ignore[misc]
    """Await all pending memory-persist background tasks after each test.

    This keeps the existing unit-test assertions (``save_mock.assert_called_once()``,
    ``insights_mock.assert_awaited_once()``) valid after the persist work was
    moved off the critical path — mocks resolve instantly so the drain adds
    negligible overhead.
    """
    yield
    if _BACKGROUND_TASKS:
        await asyncio.gather(*list(_BACKGROUND_TASKS), return_exceptions=True)
