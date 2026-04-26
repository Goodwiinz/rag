"""Unit tests for ``AgentExecuteRequest.model`` validation.

Covers the relaxed schema: empty string keeps the server default, known
deployments (including ``claude-sonnet-4-5``) are accepted, and any other
name is rejected with a message naming the supported deployments.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def _build(**overrides):
    """Construct an AgentExecuteRequest with sensible defaults for the field
    under test."""
    from src.api.agent.execute import AgentExecuteRequest, AgentMessage

    payload = {
        "messages": [AgentMessage(role="user", content="hi")],
    }
    payload.update(overrides)
    return AgentExecuteRequest(**payload)


def test_default_model_is_empty_string_meaning_server_default():
    request = _build()
    assert request.model == ""


def test_known_openai_deployment_is_accepted():
    request = _build(model="gpt-4o-mini")
    assert request.model == "gpt-4o-mini"


def test_claude_deployment_is_accepted():
    request = _build(model="claude-sonnet-4-5")
    assert request.model == "claude-sonnet-4-5"


def test_gpt5_deployment_is_accepted():
    request = _build(model="gpt-5")
    assert request.model == "gpt-5"


def test_model_router_passthrough_is_accepted():
    request = _build(model="model-router")
    assert request.model == "model-router"


def test_unknown_model_raises_validation_error_naming_supported_set():
    with pytest.raises(ValidationError) as excinfo:
        _build(model="gpt-7-uberbrain")

    detail = str(excinfo.value)
    assert "gpt-7-uberbrain" in detail
    assert "claude-sonnet-4-5" in detail
    assert "gpt-4o-mini" in detail
