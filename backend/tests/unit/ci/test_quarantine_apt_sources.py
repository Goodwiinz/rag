"""Behavioral tests for scripts/ci/quarantine_apt_sources.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "quarantine_apt_sources.py"


def test_quarantine_moves_only_matching_apt_source_files(tmp_path: Path) -> None:
    sources = tmp_path / "sources.list.d"
    quarantine = tmp_path / "quarantined"
    sources.mkdir()

    azure_cli = sources / "azure-cli.list"
    azure_cli.write_text(
        "deb https://packages.microsoft.com/repos/azure-cli noble main\n",
        encoding="utf-8",
    )
    microsoft_prod = sources / "microsoft-prod.sources"
    microsoft_prod.write_text(
        "Types: deb\nURIs: https://packages.microsoft.com/ubuntu/24.04/prod\n",
        encoding="utf-8",
    )
    ubuntu = sources / "ubuntu.sources"
    ubuntu.write_text(
        "Types: deb\nURIs: http://archive.ubuntu.com/ubuntu\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--sources-dir",
            str(sources),
            "--quarantine-dir",
            str(quarantine),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in quarantine.iterdir()) == [
        "azure-cli.list",
        "microsoft-prod.sources",
    ]
    assert not azure_cli.exists()
    assert not microsoft_prod.exists()
    assert ubuntu.read_text(encoding="utf-8") == (
        "Types: deb\nURIs: http://archive.ubuntu.com/ubuntu\n"
    )
    assert (quarantine / "azure-cli.list").read_text(encoding="utf-8") == (
        "deb https://packages.microsoft.com/repos/azure-cli noble main\n"
    )
    assert (quarantine / "microsoft-prod.sources").read_text(encoding="utf-8") == (
        "Types: deb\nURIs: https://packages.microsoft.com/ubuntu/24.04/prod\n"
    )
