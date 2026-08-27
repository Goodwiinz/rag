# mypy: disable-error-code=no-untyped-def

import ast
from pathlib import Path

from scripts.nous_run import build_parser


def test_gitio_is_the_only_coordination_subprocess_boundary():
    for path in Path("scripts/nous").glob("*.py"):
        if path.name == "gitio.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(
            (
                isinstance(node, ast.Import)
                and any(alias.name == "subprocess" for alias in node.names)
            )
            or (isinstance(node, ast.ImportFrom) and node.module == "subprocess")
            for node in ast.walk(tree)
        ), path


def test_coordination_cli_has_no_force_delete_or_compaction_command():
    text = Path("scripts/nous_run.py").read_text(encoding="utf-8")
    commands = next(
        action.choices
        for action in build_parser()._actions
        if hasattr(action, "choices") and action.choices
    )
    assert "compact" not in commands
    assert "rollback" in commands
    assert "--force" not in text
    assert "--delete" not in text


def test_canonical_workflow_marks_remote_cutover_as_two_machine_gated():
    text = Path("docs/engineering/nous-loop.md").read_text(encoding="utf-8")
    for required in (
        "remote-required",
        "nous-coordination",
        ".remote-required",
        "at most five attempts",
        "Do not run a real tick",
        "two-machine",
    ):
        assert required in text
