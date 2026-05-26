"""Regression tests for application-level exception handlers."""

import json

import pytest
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request


pytestmark = [pytest.mark.unit, pytest.mark.regression]


def _request(path: str = "/api/test") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )


@pytest.mark.asyncio
async def test_validation_exception_handler_stringifies_non_json_ctx_values():
    """Pydantic ctx values can include exceptions that JSONResponse cannot encode."""
    from src.main import validation_exception_handler

    exc = RequestValidationError(
        [
            {
                "type": "value_error",
                "loc": ("body", "model"),
                "msg": "Value error, unsupported model",
                "input": "gpt-4o",
                "ctx": {
                    "error": ValueError("unsupported model"),
                    "limit_value": object(),
                },
            }
        ]
    )

    response = await validation_exception_handler(_request(), exc)
    body = json.loads(response.body)

    assert response.status_code == 422
    assert body["error"]["message"] == "Value error, unsupported model"
    assert body["error"]["type"] == "validation_error"
    assert body["error"]["details"][0]["ctx"]["error"] == "unsupported model"
    assert isinstance(body["error"]["details"][0]["ctx"]["limit_value"], str)


@pytest.mark.asyncio
async def test_validation_exception_handler_handles_empty_error_list():
    """An empty validation error list should still produce a stable response shape."""
    from src.main import validation_exception_handler

    response = await validation_exception_handler(
        _request(), RequestValidationError([])
    )
    body = json.loads(response.body)

    assert response.status_code == 422
    assert body == {
        "error": {
            "message": "Validation error",
            "status_code": 422,
            "type": "validation_error",
            "details": [],
        }
    }
