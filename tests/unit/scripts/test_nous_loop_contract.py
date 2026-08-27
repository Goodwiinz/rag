"""Static contracts for the repository-native NOUS improvement workflow.

Agent behavior is pressure-tested separately.  These tests guard the small,
machine-checkable part of the contract: one canonical document, thin runtime
adapters, portable language, and explicit terminal outcomes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_PATH = REPO_ROOT / "docs" / "engineering" / "nous-loop.md"
CLAUDE_ADAPTER_PATH = REPO_ROOT / ".claude" / "commands" / "nous-loop.md"
AGENT_ADAPTER_PATH = REPO_ROOT / "AGENTS.md"


def _canonical_text() -> str:
    return CANONICAL_PATH.read_text(encoding="utf-8")


def test_repository_native_workflow_is_canonical_and_discoverable() -> None:
    workflow = _canonical_text()
    engineering_index = (REPO_ROOT / "docs" / "engineering" / "README.md").read_text(
        encoding="utf-8"
    )

    assert workflow.startswith("# NOUS self-improvement loop\n")
    assert "[nous-loop.md](nous-loop.md)" in engineering_index


@pytest.mark.parametrize("adapter_path", [CLAUDE_ADAPTER_PATH, AGENT_ADAPTER_PATH])
def test_runtime_entrypoints_are_thin_adapters_to_the_canonical_workflow(
    adapter_path: Path,
) -> None:
    adapter = adapter_path.read_text(encoding="utf-8")

    assert "docs/engineering/nous-loop.md" in adapter
    assert len(adapter.splitlines()) <= 60
    assert re.search(
        r"read .*docs/engineering/nous-loop\.md.* completely", adapter, re.I
    )
    assert re.search(r"canonical", adapter, re.I)
    assert re.search(r"(?:may|must) not weaken|cannot weaken", adapter, re.I)


def test_canonical_workflow_is_runtime_neutral_and_has_no_stale_incidents() -> None:
    workflow = _canonical_text()
    runtime_specific_terms = {
        "Claude",
        "Codex",
        "Fable",
        "Opus",
        "ScheduleWakeup",
        "pr-review-toolkit",
    }

    for term in runtime_specific_terms:
        assert not re.search(rf"\b{re.escape(term)}\b", workflow, re.I)
    assert not re.search(r"\b20\d{2}-\d{2}-\d{2}\b", workflow)
    assert "/home/" not in workflow
    assert "GitHub Actions has been dead" not in workflow


def test_canonical_workflow_requires_live_preflight_and_honest_outcomes() -> None:
    workflow = _canonical_text()
    normalized = " ".join(workflow.split())

    assert "## Live preflight" in workflow
    completed_outcomes = re.findall(r"^- `([a-z-]+)` —", workflow, re.MULTILINE)
    assert completed_outcomes == ["merged", "ready-for-human", "dry"]
    assert (
        "user cancellation stops the workflow outside this outcome protocol"
        in normalized
    )
    assert "Never report a stronger outcome" in workflow


def test_canonical_workflow_enforces_core_evidence_gates() -> None:
    workflow = _canonical_text()
    normalized = " ".join(workflow.split())

    required_clauses = [
        "current task authorizes each remote mutation",
        "claim before editing",
        "Heartbeat before the claim expires",
        "separate review context that did not implement the change",
        "Capture its expected failure before changing production code",
        "repeat independent review whenever the diff changes",
        "repeat security review when applicable",
    ]

    for clause in required_clauses:
        assert clause in normalized
