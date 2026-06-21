"""Regression: HTTP exception handler logs 4xx as warning, 5xx as error.

A 401 from an expired/missing JWT (and other 4xx) is a routine client
condition, not a server fault. The handler previously logged every
HTTPException at ERROR, flooding error logs and error-rate alerts with normal
auth traffic. 5xx must still log at ERROR.
"""

import types
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError

from src.main import http_exception_handler, validation_exception_handler


def _request(path="/api/v1/processing/jobs"):
    return types.SimpleNamespace(url=types.SimpleNamespace(path=path))


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422, 429])
async def test_4xx_logged_as_warning_not_error(status_code):
    with patch("src.main.logger") as log:
        resp = await http_exception_handler(
            _request(), HTTPException(status_code=status_code, detail="nope")
        )
    assert resp.status_code == status_code
    log.warning.assert_called_once()
    log.error.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [500, 502, 503])
async def test_5xx_logged_as_error(status_code):
    with patch("src.main.logger") as log:
        resp = await http_exception_handler(
            _request(), HTTPException(status_code=status_code, detail="boom")
        )
    assert resp.status_code == status_code
    log.error.assert_called_once()
    log.warning.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_401_preserves_www_authenticate_header():
    """Fix must be log-only — 401 keeps its WWW-Authenticate header."""
    with patch("src.main.logger"):
        resp = await http_exception_handler(
            _request(),
            HTTPException(
                status_code=401,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ),
        )
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validation_error_logged_as_warning():
    """422 (RequestValidationError) is a client error — warning, not error."""
    with patch("src.main.logger") as log:
        resp = await validation_exception_handler(
            _request(), RequestValidationError([])
        )
    assert resp.status_code == 422
    log.warning.assert_called_once()
    log.error.assert_not_called()
