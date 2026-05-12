"""Iteration-ledger replay diff for regression detection.

Builds on the per-turn ledger in ``src.services.agent.iteration_ledger``.
A "golden run" is just a thread directory under ``runs/<thread_id>/``
that someone (a maintainer, a CI nightly) recorded as the canonical
trace for a query. This module loads two such directories — a golden
and a candidate — and produces a structured diff focused on agent
behavior, not bit-for-bit equivalence.

Why not pytest dataclasses? Because the golden cases in
``golden_examples.py`` only assert intent + tool order. The ledger
captures the FULL state per turn (plan steps, page_context, retrieved
contexts, reflection verdict, errors, tools used). Replaying ledgers
catches behavioral regressions that the message-only tests miss —
e.g. "the agent now skips DO KB read in chat mode" or "reflection
no longer fires on transient failures."

CLI: ``python -m tests.eval.replay_ledger <golden> <candidate>``
or import as a library.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Per-turn fields whose drift is interesting (agent behavior changes).
# Other fields (timestamps, message contents, token counts) drift on
# every run and are noise.
_BEHAVIORAL_FIELDS = (
    "intent",
    "tools_used",
    "tool_loop_count",
    "error_count",
)

# State-snapshot keys whose presence/shape is interesting.
_SNAPSHOT_KEYS = (
    "plan",
    "page_context",
    "current_project_id",
    "model",
    "reflection_result",
    "retrieved_contexts",
)


@dataclass
class TurnDiff:
    """Per-turn comparison between golden and candidate ledgers."""

    turn: int
    summary_diff: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    snapshot_diff: dict[str, tuple[Any, Any]] = field(default_factory=dict)

    @property
    def is_drift(self) -> bool:
        return bool(self.summary_diff or self.snapshot_diff)


@dataclass
class LedgerDiff:
    """Result of comparing two run directories."""

    golden_path: Path
    candidate_path: Path
    turn_count_match: bool
    golden_turn_count: int
    candidate_turn_count: int
    turn_diffs: list[TurnDiff] = field(default_factory=list)
    final_diff: dict[str, tuple[Any, Any]] = field(default_factory=dict)

    @property
    def has_drift(self) -> bool:
        return (
            not self.turn_count_match
            or any(t.is_drift for t in self.turn_diffs)
            or bool(self.final_diff)
        )

    def format(self) -> str:
        """Human-readable diff report."""
        lines: list[str] = [
            f"Golden:    {self.golden_path}",
            f"Candidate: {self.candidate_path}",
            f"Turns:     golden={self.golden_turn_count} "
            f"candidate={self.candidate_turn_count}",
        ]
        if not self.has_drift:
            lines.append("\n  No behavioral drift detected.")
            return "\n".join(lines)

        if not self.turn_count_match:
            lines.append(
                "\n  TURN COUNT MISMATCH — extra/missing turns indicate "
                "structural drift."
            )

        for diff in self.turn_diffs:
            if not diff.is_drift:
                continue
            lines.append(f"\n  Turn {diff.turn}:")
            for key, (g, c) in diff.summary_diff.items():
                lines.append(f"    summary.{key}: golden={g!r} candidate={c!r}")
            for key, (g, c) in diff.snapshot_diff.items():
                lines.append(f"    snapshot.{key}: golden={g!r} candidate={c!r}")

        if self.final_diff:
            lines.append("\n  final.json drift:")
            for key, (g, c) in self.final_diff.items():
                lines.append(f"    {key}: golden={g!r} candidate={c!r}")

        return "\n".join(lines)


def _load_iterations(run_dir: Path) -> list[dict]:
    """Load every iterations/NNNN.json in numeric order."""
    iter_dir = run_dir / "iterations"
    if not iter_dir.is_dir():
        return []
    paths = sorted(
        (p for p in iter_dir.iterdir() if p.suffix == ".json"),
        key=lambda p: p.stem,
    )
    out: list[dict] = []
    for p in paths:
        try:
            out.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            continue
    return out


def _load_final(run_dir: Path) -> dict | None:
    final_path = run_dir / "final.json"
    if not final_path.exists():
        return None
    try:
        return json.loads(final_path.read_text())
    except json.JSONDecodeError:
        return None


def _diff_dict(golden: dict, candidate: dict, keys: tuple[str, ...]) -> dict:
    """Return ``{key: (golden_val, candidate_val)}`` for keys that differ.

    Sets are unordered; lists are compared positionally for ``tools_used``
    so the order of tool calls is preserved as a behavioral signal.
    """
    out: dict[str, tuple[Any, Any]] = {}
    for key in keys:
        g = golden.get(key) if isinstance(golden, dict) else None
        c = candidate.get(key) if isinstance(candidate, dict) else None
        if g != c:
            out[key] = (g, c)
    return out


def diff_runs(golden_dir: Path, candidate_dir: Path) -> LedgerDiff:
    """Compare two ledger run directories. Pure: no I/O outside the args."""
    golden_iters = _load_iterations(golden_dir)
    candidate_iters = _load_iterations(candidate_dir)

    diff = LedgerDiff(
        golden_path=golden_dir,
        candidate_path=candidate_dir,
        turn_count_match=len(golden_iters) == len(candidate_iters),
        golden_turn_count=len(golden_iters),
        candidate_turn_count=len(candidate_iters),
    )

    for g_iter, c_iter in zip(golden_iters, candidate_iters):
        turn_diff = TurnDiff(turn=g_iter.get("turn", -1))
        turn_diff.summary_diff = _diff_dict(
            g_iter.get("summary") or {},
            c_iter.get("summary") or {},
            _BEHAVIORAL_FIELDS,
        )
        turn_diff.snapshot_diff = _diff_dict(
            g_iter.get("state_snapshot") or {},
            c_iter.get("state_snapshot") or {},
            _SNAPSHOT_KEYS,
        )
        diff.turn_diffs.append(turn_diff)

    g_final = _load_final(golden_dir) or {}
    c_final = _load_final(candidate_dir) or {}
    diff.final_diff = _diff_dict(
        (g_final.get("summary") or {}),
        (c_final.get("summary") or {}),
        _BEHAVIORAL_FIELDS,
    )

    return diff


def _cli() -> int:
    """``python -m tests.eval.replay_ledger <golden> <candidate>``."""
    import sys

    if len(sys.argv) != 3:
        print(
            "usage: replay_ledger <golden_run_dir> <candidate_run_dir>",
            file=sys.stderr,
        )
        return 2
    golden = Path(sys.argv[1])
    candidate = Path(sys.argv[2])
    if not golden.is_dir() or not candidate.is_dir():
        print("both paths must be existing directories", file=sys.stderr)
        return 2
    diff = diff_runs(golden, candidate)
    print(diff.format())
    return 1 if diff.has_drift else 0


if __name__ == "__main__":
    raise SystemExit(_cli())
