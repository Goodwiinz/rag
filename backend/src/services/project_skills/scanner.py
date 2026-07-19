"""Pure, deterministic safety scanner for project skill documents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .skill_document import SkillDocument, SkillDocumentError, parse_skill_document

MAX_DESCRIPTION_LENGTH = 240
MAX_INSTRUCTION_LINES = 500
MAX_ESTIMATED_TOKENS = 5_000
SCANNER_VERSION = "1"


@dataclass(frozen=True)
class ScanFinding:
    code: str
    severity: str
    message: str
    line: int | None = None


@dataclass(frozen=True)
class ScanResult:
    findings: tuple[ScanFinding, ...]
    scanner_version: str = SCANNER_VERSION

    @property
    def is_blocking(self) -> bool:
        return any(finding.severity == "blocker" for finding in self.findings)


def _line_for_match(text: str, match: re.Match[str], start_line: int) -> int:
    return start_line + text[: match.start()].count("\n")


def _known_tools() -> set[str]:
    """Read server-owned descriptors only; never accept executable metadata from input."""
    from src.services.agent.tools import TOOL_REGISTRY

    return {descriptor.name for descriptor in TOOL_REGISTRY.descriptors}


def _finding(code: str, severity: str, message: str, line: int | None) -> ScanFinding:
    return ScanFinding(code=code, severity=severity, message=message, line=line)


def _scan_document(
    document: SkillDocument,
    existing_names: set[str],
    known_tool_names: set[str],
) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    instructions = document.instructions
    start_line = document.instruction_start_line

    if document.name in existing_names:
        findings.append(
            _finding(
                "duplicate_name",
                "blocker",
                "skill name already exists in this project",
                2,
            )
        )
    if len(document.description) > MAX_DESCRIPTION_LENGTH:
        findings.append(
            _finding(
                "description_too_long",
                "blocker",
                "description exceeds 240 characters",
                3,
            )
        )
    if document.instruction_line_count > MAX_INSTRUCTION_LINES:
        findings.append(
            _finding(
                "instructions_too_many_lines",
                "blocker",
                "instructions exceed 500 lines",
                start_line,
            )
        )
    if document.estimated_tokens > MAX_ESTIMATED_TOKENS:
        findings.append(
            _finding(
                "instructions_too_many_tokens",
                "blocker",
                "instructions exceed 5,000 estimated tokens",
                start_line,
            )
        )

    blocker_patterns = (
        (
            "secret_detected",
            re.compile(
                r"(?:sk-[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:api[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{20,})",
                re.IGNORECASE,
            ),
            "embedded secret or private key",
        ),
        (
            "executable_payload",
            re.compile(
                r"^\s*(?:#!|```(?:bash|sh|python|javascript)|chmod\s+\+x)",
                re.IGNORECASE | re.MULTILINE,
            ),
            "executable payload marker",
        ),
        (
            "unsupported_payload",
            re.compile(
                r"(?:attachment\s*:|\[attachment\]|\.(?:zip|tar|gz|exe|dmg)\b)",
                re.IGNORECASE,
            ),
            "unsupported attachment or archive marker",
        ),
    )
    for code, pattern, message in blocker_patterns:
        for match in pattern.finditer(instructions):
            findings.append(
                _finding(
                    code,
                    "blocker",
                    message,
                    _line_for_match(instructions, match, start_line),
                )
            )

    for match in re.finditer(
        r"\b(?:call|use)\s+`?([a-z][a-z0-9_]*)`?", instructions, re.IGNORECASE
    ):
        name = match.group(1)
        if name not in known_tool_names:
            findings.append(
                _finding(
                    "unknown_tool_reference",
                    "warning",
                    f"unknown tool reference: {name}",
                    _line_for_match(instructions, match, start_line),
                )
            )

    warning_patterns = (
        (
            "external_network_instruction",
            re.compile(r"(?:https?://|\b(?:curl|wget)\b)", re.IGNORECASE),
            "external-network instruction",
        ),
        (
            "destructive_action_language",
            re.compile(r"\b(?:delete|destroy|drop|wipe)\b", re.IGNORECASE),
            "destructive-action language",
        ),
        (
            "policy_bypass_instruction",
            re.compile(
                r"\b(?:bypass|ignore)\s+(?:approval|policy|confirmation)", re.IGNORECASE
            ),
            "attempt to bypass approval or policy",
        ),
    )
    for code, pattern, message in warning_patterns:
        for match in pattern.finditer(instructions):
            findings.append(
                _finding(
                    code,
                    "warning",
                    message,
                    _line_for_match(instructions, match, start_line),
                )
            )
    return findings


def scan_skill_document(
    text: str,
    *,
    existing_names: Iterable[str] = (),
    known_tool_names: Iterable[str] | None = None,
) -> ScanResult:
    """Scan untrusted Markdown synchronously without import, fetch, render, or execution."""
    try:
        document = parse_skill_document(text)
    except SkillDocumentError as error:
        return ScanResult(
            (_finding("malformed_metadata", "blocker", str(error), None),)
        )

    tool_names = (
        set(known_tool_names) if known_tool_names is not None else _known_tools()
    )
    findings = _scan_document(document, set(existing_names), tool_names)
    return ScanResult(
        tuple(sorted(findings, key=lambda item: (item.line or 0, item.code)))
    )
