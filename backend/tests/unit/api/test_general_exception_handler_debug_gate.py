"""R4-M12 regression: general_exception_handler leaked exception details
outside production.

The old check was `settings.ENVIRONMENT not in ("production",)`, so a
staging or dev deployment (ENVIRONMENT="staging"/"development", DEBUG=False)
returned the raw exception type + message in the 500 body to any caller.
Must gate on settings.DEBUG instead, which config.py's
_enforce_debug_off_in_prod force-clears in production AND staging.
"""

import json
import types

import pytest

from src.main import general_exception_handler


def _request(path: str = "/api/v1/whatever") -> types.SimpleNamespace:
    return types.SimpleNamespace(url=types.SimpleNamespace(path=path))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_staging_environment_does_not_leak_exception_details(monkeypatch) -> None:
    from src.main import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(settings, "DEBUG", False)

    resp = await general_exception_handler(_request(), ValueError("db password is X"))  # type: ignore[arg-type]
    body = json.loads(resp.body)

    assert resp.status_code == 500
    assert body["error"]["message"] == "Internal server error"
    assert "db password is X" not in body["error"]["message"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_development_environment_does_not_leak_when_debug_off(
    monkeypatch,
) -> None:
    from src.main import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "DEBUG", False)

    resp = await general_exception_handler(_request(), ValueError("secret detail"))  # type: ignore[arg-type]
    body = json.loads(resp.body)

    assert body["error"]["message"] == "Internal server error"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_debug_true_includes_exception_details(monkeypatch) -> None:
    from src.main import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "DEBUG", True)

    resp = await general_exception_handler(_request(), ValueError("secret detail"))  # type: ignore[arg-type]
    body = json.loads(resp.body)

    assert "ValueError" in body["error"]["message"]
    assert "secret detail" in body["error"]["message"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_production_never_leaks(monkeypatch) -> None:
    from src.main import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "DEBUG", False)

    resp = await general_exception_handler(_request(), ValueError("secret detail"))  # type: ignore[arg-type]
    body = json.loads(resp.body)

    assert body["error"]["message"] == "Internal server error"
