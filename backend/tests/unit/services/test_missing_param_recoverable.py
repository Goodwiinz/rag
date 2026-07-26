"""A missing required parameter is recoverable, not fatal.

Live on dev (synthetic writing_draft, 2026-07-26): the agent wrote a complete
note — title, ~700 words of content, tags — called ``create_project_note``,
and got::

    {"error": "project_id is required", "error_type": "fatal"}

``"project_id is required"`` matched none of the classifier's keyword sets
(credential, permission, transient, or the recoverable list of "not found" /
"does not exist" / "no results" / "invalid"), so it fell through to ``fatal``.
Fatal tells the agent not to recover, so the finished note was discarded
instead of being saved after a ``list_projects`` / ``create_project`` call.

A missing argument is the *most* recoverable failure there is: the value is
obtainable and the call can be retried.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _classify(tool: str, error: str):  # type: ignore[no-untyped-def]
    from src.services.agent.error_recovery import classify_error_from_payload

    return classify_error_from_payload(tool, {"error": error})


class TestMissingParameter:
    def test_project_id_required_is_recoverable(self) -> None:
        assert _classify("create_project_note", "project_id is required").category == (
            "recoverable"
        )

    def test_the_hint_says_where_a_project_id_comes_from(self) -> None:
        """A bare 'retry differently' does not tell the model what to do."""
        err = _classify("create_project_note", "project_id is required")

        assert "list_projects" in (err.suggestion or "")
        assert "create_project" in (err.suggestion or "")

    def test_create_draft_gets_the_same_hint(self) -> None:
        err = _classify("create_draft", "project_id is required")

        assert err.category == "recoverable"
        assert "list_projects" in (err.suggestion or "")

    @pytest.mark.parametrize(
        "message",
        [
            "title is required",
            "content is required",
            "Missing required field: name",
            "document_id must be provided",
        ],
    )
    def test_any_missing_argument_is_recoverable(self, message: str) -> None:
        """Generic rule, so a new tool's guard does not silently become fatal."""
        assert _classify("some_tool", message).category == "recoverable"


class TestNoRegression:
    """The categories that must NOT become recoverable."""

    def test_credentials_stay_user_fixable(self) -> None:
        assert _classify("x", "invalid api key").category == "user_fixable"

    def test_permission_stays_user_fixable(self) -> None:
        assert _classify("x", "permission denied").category == "user_fixable"

    def test_rate_limit_stays_transient(self) -> None:
        assert _classify("search_arxiv", "rate limited (429)").category == "transient"

    def test_a_genuinely_unknown_error_is_still_fatal(self) -> None:
        """Widening the recoverable set must not swallow everything."""
        assert _classify("x", "segmentation fault in worker").category == "fatal"
