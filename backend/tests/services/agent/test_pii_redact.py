"""PII redactor strips emails, phones, UUIDs from memory values."""

from __future__ import annotations

import pytest

from src.services.agent._pii_redact import redact_nested_pii, redact_pii


@pytest.mark.unit
class TestRedactPII:
    def test_strips_email(self):
        assert redact_pii("contact me at jane@example.com please") == (
            "contact me at <email> please"
        )

    def test_strips_phone_us(self):
        assert redact_pii("call +1-415-555-0123 today") == ("call <phone> today")

    def test_strips_uuid(self):
        assert (
            redact_pii("project 5ed25258-5ad2-4b06-9678-4a4abe5ecac1 is active")
            == "project <uuid> is active"
        )

    def test_strips_postgres_url(self):
        text = "DB is postgresql://user:secret@host.example.com:5432/db?sslmode=require"
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
        assert redact_pii("call +1-415-555-0123 today") == ("call <phone> today")
        assert redact_pii("(415) 555-0123") == "<phone>"
        assert redact_pii("415-555-0123") == "<phone>"

    def test_strips_jwt(self):
        # Synthetic JWT-shaped token (eyJ + 20+ chars per segment), built
        # from repeated filler so secret-scrubbing history rewrites never
        # mistake it for a real credential and mangle the fixture.
        jwt = ".".join(["eyJ" + "a" * 30, "eyJ" + "b" * 30, "c" * 30])
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

    # GitHub issues five distinct token prefixes and the module docstring
    # already claims OAuth coverage. ``gho_`` reaching model-visible context
    # is what failed the retrieval-safety benchmark (evals/AGENT_FLOW_BASELINE.md,
    # P1); ``ghu_``/``ghr_`` are the same family and were never covered either.
    @pytest.mark.parametrize(
        "prefix",
        ["ghp", "gho", "ghu", "ghs", "ghr"],
        ids=["pat", "oauth", "user-to-server", "server-to-server", "refresh"],
    )
    def test_strips_every_github_token_prefix(self, prefix):
        token = f"{prefix}_abcdefghijklmnopqrstuvwxyz123456"
        assert redact_pii(f"token {token}") == "token <token>"

    def test_strips_benchmark_oauth_marker(self):
        """The exact literal the retrieval-safety benchmark plants."""
        marker = "gho_000000000000000000000000000000000000"
        assert marker not in redact_pii(f"see {marker} in the doc")

    @pytest.mark.parametrize(
        "near_miss",
        [
            "ghx_abcdefghijklmnopqrstuvwxyz123456",  # not a GitHub prefix
            "gh_abcdefghijklmnopqrstuvwxyz123456",  # missing family letter
            "ghp_tooshort",  # below the 30-char body minimum
        ],
    )
    def test_leaves_non_token_lookalikes_intact(self, near_miss):
        """Widening the prefix class must not turn the regex into a wildcard."""
        assert near_miss in redact_pii(f"value {near_miss} here")

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

    def test_mixed_pii_in_one_string_exact_output(self):
        text = (
            "Email jane@example.com about +1-415-555-0123 "
            "regarding postgresql://u:p@h.example.com:5432/db "
            "for project 5ed25258-5ad2-4b06-9678-4a4abe5ecac1"
        )
        assert redact_pii(text) == (
            "Email <email> about <phone> "
            "regarding <postgres-url> "
            "for project <uuid>"
        )

    def test_phone_does_not_match_bare_version_no_letter_prefix(self):
        # Bare 1.234.567.8901 at start of string — used to be eaten as
        # country-code 1 + area-code 234 + exchange 567 + line 8901.
        assert redact_pii("1.234.567.8901") == "1.234.567.8901"
        assert redact_pii("Released 1.234.567.8901 today") == (
            "Released 1.234.567.8901 today"
        )

    def test_phone_plus1_country_code_still_matches(self):
        # Regression guard for the explicit + requirement.
        assert redact_pii("+1-415-555-0123") == "<phone>"
        assert redact_pii("ring +1 415 555 0123") == "ring <phone>"

    def test_phone_bare_us_format_still_matches(self):
        # 10-digit US shapes without country code stay redacted.
        assert redact_pii("415-555-0123") == "<phone>"
        assert redact_pii("(415) 555-0123") == "<phone>"
        assert redact_pii("415.555.0123") == "<phone>"


@pytest.mark.unit
class TestRedactNestedPII:
    def test_recursively_redacts_metadata_strings_without_truncating(self):
        token = "sk-proj-" + "a" * 24
        metadata = {
            "summary": "ordinary research notes remain readable",
            "contact": "synthetic.user@example.test",
            "nested": [
                {"phone": "+1-415-555-0123", "ssn": "123-45-6789"},
                {"credential": "postgresql://user:synthetic@host.test:5432/db"},
                {"token": token},
                {"secret_id": "11111111-2222-4333-8444-555555555555"},
            ],
        }

        redacted = redact_nested_pii(metadata)

        assert redacted == {
            "summary": "ordinary research notes remain readable",
            "contact": "<email>",
            "nested": [
                {"phone": "<phone>", "ssn": "[REDACTED_SSN]"},
                {"credential": "<postgres-url>"},
                {"token": "<token>"},
                {"secret_id": "<uuid>"},
            ],
        }
        assert metadata["contact"] == "synthetic.user@example.test"
        assert redacted["summary"] == "ordinary research notes remain readable"

    def test_nested_redaction_does_not_apply_browser_cap(self):
        long_prose = "safe text " * 100

        assert redact_nested_pii({"note": long_prose}) == {"note": long_prose}
