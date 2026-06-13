"""Unit tests for the agent UUID regex patterns.

Tests UUID_STRICT_RE (whole-string validation) and UUID_SEARCH_RE
(embedded UUID extraction) from src.services.agent._uuid.
"""

from __future__ import annotations

import re

import pytest

from src.services.agent._uuid import UUID_SEARCH_RE, UUID_STRICT_RE


# ---------------------------------------------------------------------------
# UUID_STRICT_RE — anchored whole-string match
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUUIDStrictRE:
    def test_valid_lowercase_uuid(self):
        assert UUID_STRICT_RE.match("550e8400-e29b-41d4-a716-446655440000")

    def test_valid_uppercase_uuid(self):
        assert UUID_STRICT_RE.match("550E8400-E29B-41D4-A716-446655440000")

    def test_valid_mixed_case_uuid(self):
        assert UUID_STRICT_RE.match("550e8400-E29b-41D4-a716-446655440000")

    def test_nil_uuid(self):
        assert UUID_STRICT_RE.match("00000000-0000-0000-0000-000000000000")

    def test_max_uuid(self):
        assert UUID_STRICT_RE.match("ffffffff-ffff-ffff-ffff-ffffffffffff")

    def test_rejects_uuid_with_prefix(self):
        assert not UUID_STRICT_RE.match("proj_550e8400-e29b-41d4-a716-446655440000")

    def test_rejects_uuid_with_suffix(self):
        assert not UUID_STRICT_RE.match("550e8400-e29b-41d4-a716-446655440000-extra")

    def test_rejects_uuid_without_dashes(self):
        assert not UUID_STRICT_RE.match("550e8400e29b41d4a716446655440000")

    def test_rejects_short_uuid(self):
        assert not UUID_STRICT_RE.match("550e8400-e29b-41d4-a716-44665544000")

    def test_rejects_long_uuid(self):
        assert not UUID_STRICT_RE.match("550e8400-e29b-41d4-a716-4466554400001")

    def test_rejects_guid_with_braces(self):
        assert not UUID_STRICT_RE.match("{550e8400-e29b-41d4-a716-446655440000}")

    def test_rejects_non_hex_chars(self):
        assert not UUID_STRICT_RE.match("550e8400-e29b-41d4-a716-44665544000g")

    def test_rejects_empty_string(self):
        assert not UUID_STRICT_RE.match("")

    def test_rejects_arbitrary_id_string(self):
        assert not UUID_STRICT_RE.match("proj_12345")

    def test_rejects_plain_integer(self):
        assert not UUID_STRICT_RE.match("12345")

    def test_rejects_url_with_embedded_uuid(self):
        # Anchored — does not match substrings
        assert not UUID_STRICT_RE.match("/projects/550e8400-e29b-41d4-a716-446655440000/docs")


# ---------------------------------------------------------------------------
# UUID_SEARCH_RE — word-boundary embedded extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUUIDSearchRE:
    def test_finds_uuid_in_path(self):
        text = "/projects/550e8400-e29b-41d4-a716-446655440000/docs"
        match = UUID_SEARCH_RE.search(text)
        assert match is not None
        assert match.group(1) == "550e8400-e29b-41d4-a716-446655440000"

    def test_finds_uuid_in_sentence(self):
        text = "Project 550e8400-e29b-41d4-a716-446655440000 is active"
        match = UUID_SEARCH_RE.search(text)
        assert match is not None
        assert match.group(1) == "550e8400-e29b-41d4-a716-446655440000"

    def test_finds_multiple_uuids(self):
        text = (
            "Thread 550e8400-e29b-41d4-a716-446655440000 "
            "and project 660f9511-f3ac-52e5-b827-557766551111"
        )
        matches = UUID_SEARCH_RE.findall(text)
        assert len(matches) == 2
        assert "550e8400-e29b-41d4-a716-446655440000" in matches
        assert "660f9511-f3ac-52e5-b827-557766551111" in matches

    def test_returns_none_when_no_uuid(self):
        assert UUID_SEARCH_RE.search("no uuid here") is None

    def test_does_not_match_partial_uuid(self):
        # Missing last group
        assert UUID_SEARCH_RE.search("550e8400-e29b-41d4-a716-44665544") is None

    def test_uppercase_uuid_extracted(self):
        text = "ID: 550E8400-E29B-41D4-A716-446655440000"
        match = UUID_SEARCH_RE.search(text)
        assert match is not None

    def test_nil_uuid_extracted(self):
        text = "default: 00000000-0000-0000-0000-000000000000"
        match = UUID_SEARCH_RE.search(text)
        assert match is not None
        assert match.group(1) == "00000000-0000-0000-0000-000000000000"

    def test_no_false_positive_on_shorter_hex_string(self):
        # 7-4-4-4-12 would be wrong; check 8-4-4-4-12 is required
        assert UUID_SEARCH_RE.search("1234567-e29b-41d4-a716-446655440000") is None

    def test_findall_returns_group_1(self):
        text = "550e8400-e29b-41d4-a716-446655440000"
        matches = UUID_SEARCH_RE.findall(text)
        assert matches == ["550e8400-e29b-41d4-a716-446655440000"]

    def test_uuid_at_start_of_string(self):
        text = "550e8400-e29b-41d4-a716-446655440000 is the thread id"
        match = UUID_SEARCH_RE.match(text)
        assert match is not None

    def test_uuid_at_end_of_string(self):
        text = "thread id is 550e8400-e29b-41d4-a716-446655440000"
        match = UUID_SEARCH_RE.search(text)
        assert match is not None

    def test_uuid_surrounded_by_slashes(self):
        # Word boundary behavior with non-word chars like /
        text = "/api/v1/threads/550e8400-e29b-41d4-a716-446655440000/messages"
        match = UUID_SEARCH_RE.search(text)
        assert match is not None
        assert match.group(1) == "550e8400-e29b-41d4-a716-446655440000"
