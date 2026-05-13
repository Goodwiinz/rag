"""PII redactor strips emails, phones, UUIDs from memory values."""
from __future__ import annotations

import pytest

from src.services.agent._pii_redact import redact_pii


@pytest.mark.unit
class TestRedactPII:
    def test_strips_email(self):
        assert redact_pii("contact me at jane@example.com please") == (
            "contact me at <email> please"
        )

    def test_strips_phone_us(self):
        assert redact_pii("call +1-415-555-0123 today") == (
            "call <phone> today"
        )

    def test_strips_uuid(self):
        assert redact_pii(
            "project 5ed25258-5ad2-4b06-9678-4a4abe5ecac1 is active"
        ) == "project <uuid> is active"

    def test_strips_postgres_url(self):
        text = (
            "DB is postgresql://user:secret@host.example.com:5432/db?sslmode=require"
        )
        assert redact_pii(text) == "DB is <postgres-url>"

    def test_passthrough_clean_text(self):
        assert redact_pii("find papers on transformers") == (
            "find papers on transformers"
        )

    def test_empty_input(self):
        assert redact_pii("") == ""
        assert redact_pii(None) == ""
