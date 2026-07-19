"""Canonical project-skill document contracts."""

import pytest

from src.services.project_skills.skill_document import (
    SkillDocumentError,
    parse_skill_document,
)

DOCUMENT = """---
name: research-helper
description: Produce a concise, cited research brief.
---
# Research helper

Use the search_arxiv tool when it is relevant.
"""


def test_parses_canonical_skill_document_deterministically():
    document = parse_skill_document(DOCUMENT)

    assert document.name == "research-helper"
    assert document.description == "Produce a concise, cited research brief."
    assert document.instructions.startswith("# Research helper")
    assert document.canonical_text == DOCUMENT
    assert len(document.content_hash) == 64
    assert document.instruction_line_count == 3
    assert document.estimated_tokens > 0
    assert parse_skill_document(DOCUMENT).content_hash == document.content_hash


@pytest.mark.parametrize(
    "content, message",
    [
        ("# no frontmatter", "frontmatter"),
        ("---\nname: Not Valid\ndescription: x\n---\nbody", "name"),
        ("---\nname: valid-name\n---\nbody", "description"),
    ],
)
def test_rejects_noncanonical_metadata(content, message):
    with pytest.raises(SkillDocumentError, match=message):
        parse_skill_document(content)
