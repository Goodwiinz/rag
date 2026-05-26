"""Regression tests for observability instrumentation call signatures."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


pytestmark = [pytest.mark.unit, pytest.mark.regression]


@contextmanager
def _fake_trace_span(*args, **kwargs):
    span = MagicMock()
    yield span


def test_redis_instrumentation_records_counter_attributes_by_keyword():
    """Redis metrics must not pass the attributes dict as the counter value."""
    from src.observability.instrumentation import RedisInstrumentation

    redis_client = SimpleNamespace(execute_command=MagicMock(return_value="PONG"))

    with patch(
        "src.observability.instrumentation.trace_span", _fake_trace_span
    ), patch("src.observability.instrumentation.record_histogram"), patch(
        "src.observability.instrumentation.increment_counter"
    ) as increment_counter:
        RedisInstrumentation(redis_client)

        assert redis_client.execute_command("PING") == "PONG"

    increment_counter.assert_called_once_with(
        "redis_commands_total",
        attributes={"command": "PING", "success": "true"},
    )


def test_redis_instrumentation_records_error_attributes_by_keyword():
    """Redis errors should report attributes without confusing them for counter values."""
    from src.observability.instrumentation import RedisInstrumentation

    redis_client = SimpleNamespace(
        execute_command=MagicMock(side_effect=TimeoutError("redis timed out"))
    )

    with patch(
        "src.observability.instrumentation.trace_span", _fake_trace_span
    ), patch("src.observability.instrumentation.increment_counter") as increment_counter:
        RedisInstrumentation(redis_client)

        with pytest.raises(TimeoutError, match="redis timed out"):
            redis_client.execute_command("GET", "missing")

    increment_counter.assert_called_once_with(
        "redis_commands_total",
        attributes={
            "command": "GET",
            "success": "false",
            "error_type": "TimeoutError",
        },
    )


def test_http_client_instrumentation_records_counter_attributes_by_keyword():
    """HTTP client metrics must keep attributes separate from the counter value."""
    from src.observability.instrumentation import HTTPClientInstrumentation

    response = SimpleNamespace(status_code=201)
    client = SimpleNamespace(request=MagicMock(return_value=response))

    with patch(
        "src.observability.instrumentation.trace_span", _fake_trace_span
    ), patch("src.observability.instrumentation.record_histogram"), patch(
        "src.observability.instrumentation.increment_counter"
    ) as increment_counter:
        HTTPClientInstrumentation.instrument_httpx_client(client)

        assert client.request("post", "https://api.example.test/items") is response

    increment_counter.assert_called_once_with(
        "http_client_requests_total",
        attributes={
            "method": "POST",
            "status_code": "201",
            "target_host": "api.example.test",
        },
    )


def test_database_handle_error_listener_uses_sqlalchemy_exception_context():
    """SQLAlchemy handle_error dispatches one ExceptionContext argument."""
    from sqlalchemy import create_engine, text

    from src.observability.instrumentation import DatabaseInstrumentation

    engine = create_engine("sqlite:///:memory:")

    with patch(
        "src.observability.instrumentation.trace_span", _fake_trace_span
    ), patch("src.observability.instrumentation.increment_counter") as increment_counter:
        DatabaseInstrumentation.instrument_sqlalchemy(engine)

        with pytest.raises(Exception, match="missing_table"):
            with engine.connect() as conn:
                conn.execute(
                    text("SELECT * FROM missing_table").execution_options(
                        operation="read"
                    )
                )

    increment_counter.assert_called_with(
        "database_queries_total",
        attributes={
            "operation": "read",
            "success": "false",
            "error_type": "OperationalError",
        },
    )
