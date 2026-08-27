# mypy: disable-error-code=no-untyped-def

from pathlib import Path

import pytest

from scripts.nous.coordination import ValidationError
from scripts.nous.preflight import load_runtime_config
from scripts.nous_run import build_parser


def test_runtime_config_requires_explicit_machine_and_uses_planned_defaults(tmp_path):
    config = load_runtime_config(
        {"NOUS_MACHINE_ID": "mac-nous", "LOOP_BRIDGE_DIR": str(tmp_path / "bridge")},
        repo_root=tmp_path / "rag",
    )
    assert config.coord_mode == "local"
    assert config.git_remote == "origin"
    assert config.coordination_branch == "nous-coordination"
    assert config.github_repository == "Goodwiinz/rag"

    with pytest.raises(ValidationError):
        load_runtime_config({}, repo_root=tmp_path / "rag")


def test_cli_exposes_only_coordination_milestone_commands():
    parser = build_parser()
    subcommands = next(
        action.choices
        for action in parser._actions
        if hasattr(action, "choices") and action.choices
    )
    assert set(subcommands) == {
        "bootstrap",
        "cutover",
        "claim",
        "renew",
        "release",
        "rollback",
        "list",
        "check",
    }
