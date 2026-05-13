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

    def test_non_string_input_returns_empty_not_raises(self):
        # LangGraph multimodal HumanMessage.content can be list[dict].
        assert redact_pii([{"type": "text", "text": "hi"}]) == ""
        assert redact_pii(42) == ""
        assert redact_pii(b"bytes are not strings") == ""

    def test_phone_does_not_match_ipv4(self):
        # 192.168.100.1001 is an IPv4-ish string. Last 3-3-4 = 168.100.1001.
        assert redact_pii("server 192.168.100.1001 unreachable") == (
            "server 192.168.100.1001 unreachable"
        )

    def test_phone_does_not_match_version_string(self):
        assert redact_pii("v1.234.567.8901 ships tomorrow") == (
            "v1.234.567.8901 ships tomorrow"
        )

    def test_phone_still_matches_after_ip_pattern_added(self):
        # Sanity — the original phone shapes still get redacted.
        assert redact_pii("call +1-415-555-0123 today") == (
            "call <phone> today"
        )
        assert redact_pii("(415) 555-0123") == "<phone>"
        assert redact_pii("415-555-0123") == "<phone>"

    def test_strips_jwt(self):
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        assert redact_pii(f"Authorization: Bearer {jwt}") == (
            "Authorization: Bearer <token>"
        )

    def test_strips_openai_key(self):
        assert redact_pii("OPENAI_API_KEY=sk-proj-abcdefghij1234567890klmnop") == (
            "OPENAI_API_KEY=<token>"
        )

    def test_strips_anthropic_key(self):
        assert redact_pii("key sk-ant-api03-abcdefghijklmnopqrstuvwx") == (
            "key <token>"
        )

    def test_strips_github_pat(self):
        assert redact_pii("token ghp_abcdefghijklmnopqrstuvwxyz123456") == (
            "token <token>"
        )

    def test_mixed_pii_in_one_string(self):
        text = (
            "Email jane@example.com about +1-415-555-0123 "
            "regarding postgresql://u:p@h.example.com:5432/db "
            "for project 5ed25258-5ad2-4b06-9678-4a4abe5ecac1"
        )
        out = redact_pii(text)
        assert "jane@example.com" not in out
        assert "555-0123" not in out
        assert "postgresql://" not in out
        assert "5ed25258" not in out
        # All four sentinels present
        assert "<email>" in out
        assert "<phone>" in out
        assert "<postgres-url>" in out
        assert "<uuid>" in out
