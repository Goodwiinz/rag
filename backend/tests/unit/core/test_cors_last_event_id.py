"""The SSE resume cursor header must survive cross-origin preflight.

`agentChatService.resumeStream` sends `Last-Event-ID` on every resume request.
The frontend (Vercel) and backend (dev-api) are cross-origin, and
`Last-Event-ID` is not a CORS-safelisted request header, so it must appear in
the configured allowlist or the preflight fails with 400 and resume breaks in
every deployed environment.
"""

from src.core.config import get_settings


def test_last_event_id_is_cors_allowlisted() -> None:
    settings = get_settings()
    headers = [h.lower() for h in settings.cors_headers_list]
    assert "last-event-id" in headers, (
        "Last-Event-ID missing from CORS_ALLOWED_HEADERS — cross-origin SSE "
        "resume preflight will be rejected (400 Disallowed CORS headers)"
    )
