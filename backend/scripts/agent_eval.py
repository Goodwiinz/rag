"""``agent-eval`` CLI: regression harness wrapper for the agent.

Three modes:

  agent_eval golden                       Run all local golden cases (pytest)
  agent_eval golden --case <name>         Run a single golden case
  agent_eval replay <golden> <candidate>  Diff two ledger run directories

Wraps the existing pytest entry points in ``tests/eval/`` plus the
``replay_ledger`` library so a single command covers both ledger-based
behavioral regression and message-based golden case regression.

Examples::

    python -m scripts.agent_eval golden
    python -m scripts.agent_eval golden --case Find_recent_transformer_papers
    python -m scripts.agent_eval replay runs/golden_t1 runs/candidate_t1
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # backend/


def _run_pytest(args: list[str]) -> int:
    """Invoke pytest as a subprocess so test-discovery and conftest
    fixtures load identically to a manual pytest run.
    """
    cmd = [sys.executable, "-m", "pytest", *args]
    return subprocess.call(cmd, cwd=REPO_ROOT)


def _cmd_golden(args: argparse.Namespace) -> int:
    pytest_args = ["tests/eval/test_agent_regression.py", "-v", "--no-header"]
    if args.case:
        # pytest -k matches substring; users pass the case name from
        # golden_examples.py (the dataclass `name` field).
        pytest_args += ["-k", args.case]
    return _run_pytest(pytest_args)


def _cmd_replay(args: argparse.Namespace) -> int:
    """Delegate to the replay_ledger library."""
    sys.path.insert(0, str(REPO_ROOT))
    from tests.eval.replay_ledger import diff_runs

    golden = Path(args.golden)
    candidate = Path(args.candidate)
    if not golden.is_dir() or not candidate.is_dir():
        print("both paths must be existing directories", file=sys.stderr)
        return 2
    diff = diff_runs(golden, candidate)
    print(diff.format())
    return 1 if diff.has_drift else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent-eval",
        description="Agent regression harness — golden cases + ledger replay.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_golden = sub.add_parser("golden", help="Run local golden test cases")
    p_golden.add_argument(
        "--case",
        default=None,
        help="Filter to cases matching this substring (pytest -k)",
    )
    p_golden.set_defaults(func=_cmd_golden)

    p_replay = sub.add_parser(
        "replay", help="Diff two iteration-ledger run directories"
    )
    p_replay.add_argument("golden", help="Path to golden run dir")
    p_replay.add_argument("candidate", help="Path to candidate run dir")
    p_replay.set_defaults(func=_cmd_replay)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
