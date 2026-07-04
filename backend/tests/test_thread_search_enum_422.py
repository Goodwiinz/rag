"""Guard: GET thread/message search must 422 (not 500) on bad enum values.

`search_threads_get` and `search_messages_get` cast user-supplied query
params to enums (``ThreadStatus`` / ``MessageRole``). Previously those casts
happened INSIDE a broad ``try/except Exception -> HTTPException(500, ...)``
with no ``except HTTPException: raise``, so an invalid-but-plausible value
(e.g. ``?status_filter=open`` or ``?roles=bot``) raised ``ValueError`` ->
caught -> 500 (and leaked the raw error) instead of a clean 422.

The fix parses the enums BEFORE the main handler ``try:`` and raises a 422 on
``ValueError`` so it isn't re-swallowed by the broad except. These source
guards keep the pattern from regressing.
"""

from pathlib import Path

# tests/ -> backend/
ROUTER = (
    Path(__file__).resolve().parents[1] / "src" / "api" / "threads" / "thread_search.py"
)


def _source() -> str:
    return ROUTER.read_text()


def test_both_handlers_raise_422():
    source = _source()
    # One 422 for status_filter (threads), one for roles (messages).
    assert source.count("status.HTTP_422_UNPROCESSABLE_ENTITY") >= 2, (
        "both search_threads_get and search_messages_get must raise "
        "HTTP_422_UNPROCESSABLE_ENTITY on invalid enum values"
    )


def test_parsed_status_defined_and_used():
    source = _source()
    assert "parsed_status = (" in source, "parsed_status must be parsed before the try"
    assert (
        "status=parsed_status," in source
    ), "ThreadSearchFilter must use the pre-parsed parsed_status"


def test_parsed_roles_defined_and_used():
    source = _source()
    assert "parsed_roles = " in source, "parsed_roles must be parsed before the try"
    assert (
        "roles=parsed_roles," in source
    ), "MessageSearchFilter must use the pre-parsed parsed_roles"


def test_bare_in_filter_casts_removed():
    source = _source()
    # The regressions: enum casts done inline inside the filter (caught by the
    # broad 500 except). These must have been replaced by the parsed_* vars.
    assert "status=[ThreadStatus(s) for s in status_filter]" not in source, (
        "inline ThreadStatus cast inside ThreadSearchFilter re-introduces the "
        "500-instead-of-422 bug"
    )
    assert "roles=[MessageRole(r) for r in roles]" not in source, (
        "inline MessageRole cast inside MessageSearchFilter re-introduces the "
        "500-instead-of-422 bug"
    )
