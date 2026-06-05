"""Unit tests for ``src.core.async_utils.reraise_if_cancelled``.

Regression guard for the systemic CancelledError footgun found by the
async-correctness sweep: ``gather(return_exceptions=True)`` results handled with
``isinstance(_, Exception)`` let a cancelled task (a BaseException) slip through
as a success. ``reraise_if_cancelled`` is called before that check.
"""

from __future__ import annotations

import asyncio

import pytest

from src.core.async_utils import reraise_if_cancelled


@pytest.mark.unit
def test_reraises_cancelled_error():
    with pytest.raises(asyncio.CancelledError):
        reraise_if_cancelled(asyncio.CancelledError())


@pytest.mark.unit
def test_noop_for_regular_exception():
    # A regular Exception is left for the caller's isinstance(_, Exception) branch.
    assert reraise_if_cancelled(ValueError("boom")) is None


@pytest.mark.unit
def test_noop_for_values():
    assert reraise_if_cancelled({"ok": 1}) is None
    assert reraise_if_cancelled(None) is None
    assert reraise_if_cancelled([1, 2, 3]) is None
