"""Strict, deterministic parser for an instruction-only ``SKILL.md`` document."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256

import yaml

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SkillDocumentError(ValueError):
    """Raised when a document is not canonical project-skill Markdown."""


@dataclass(frozen=True)
class SkillDocument:
    """Canonical parsed metadata and untouched Markdown instruction body."""

    name: str
    description: str
    instructions: str
    canonical_text: str
    content_hash: str
    instruction_line_count: int
    estimated_tokens: int
    instruction_start_line: int


def normalize_skill_name(name: str) -> str:
    """Validate and return the canonical lower-kebab-case skill identity."""
    if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
        raise SkillDocumentError("name must be lowercase kebab-case")
    if len(name) > 128:
        raise SkillDocumentError("name must not exceed 128 characters")
    return name


def _canonicalize_text(text: str) -> str:
    if not isinstance(text, str):
        raise SkillDocumentError("document must be text")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_skill_document(text: str) -> SkillDocument:
    """Parse one canonical document without executing or rendering its contents."""
    canonical_text = _canonicalize_text(text)
    lines = canonical_text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise SkillDocumentError("document must start with YAML frontmatter")

    closing_index = next(
        (
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        ),
        None,
    )
    if closing_index is None:
        raise SkillDocumentError("frontmatter must end with ---")

    try:
        metadata = yaml.safe_load("".join(lines[1:closing_index]))
    except yaml.YAMLError as error:
        raise SkillDocumentError("frontmatter is malformed") from error
    if not isinstance(metadata, dict):
        raise SkillDocumentError("frontmatter must be a mapping")
    if set(metadata) != {"name", "description"}:
        raise SkillDocumentError("frontmatter must contain only name and description")

    name = normalize_skill_name(metadata.get("name"))
    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        raise SkillDocumentError("description must be a non-empty string")
    description = description.strip()
    if (
        "\n" in description
        or "\r" in description
        or any(ord(char) < 32 or ord(char) == 127 for char in description)
    ):
        raise SkillDocumentError("description must be a trimmed single line")

    instructions = "".join(lines[closing_index + 1 :])
    if not instructions.strip():
        raise SkillDocumentError("instructions must not be empty")
    content_hash = sha256(canonical_text.encode("utf-8")).hexdigest()
    return SkillDocument(
        name=name,
        description=description,
        instructions=instructions,
        canonical_text=canonical_text,
        content_hash=content_hash,
        instruction_line_count=len(instructions.splitlines()),
        estimated_tokens=(len(instructions) + 3) // 4,
        instruction_start_line=closing_index + 2,
    )
