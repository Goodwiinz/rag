"""Contract tests for scripts/ci/check_tsconfig_exclusions.py.

``frontend/tsconfig.json`` excludes dozens of production files from
type-checking. The ratchet freezes that debt in
``frontend/quality-baseline.json`` and fails when:

- a production exclusion is added without a reviewed baseline update;
- a changed production file remains excluded (touch it → fix its types);
- a baseline entry points to a file that no longer exists;
- a baseline entry no longer appears in tsconfig (stale debt record that
  would let the exclusion silently return later).

Structural exclusions (node_modules, test/story globs, e2e, test setup)
are not debt and never require baseline entries.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "check_tsconfig_exclusions.py"

STRUCTURAL = [
    "node_modules",
    "e2e/**/*",
    "**/*.test.ts",
    "**/*.test.tsx",
    "**/*.spec.ts",
    "**/*.stories.tsx",
    "playwright.config.ts",
    "src/test/setup.ts",
    "src/components/__tests__/**/*",
]


def _make_root(
    tmp_path: Path,
    *,
    exclude: list[str],
    baseline: list[str],
    files: Sequence[str] = (),
) -> Path:
    root = tmp_path / "project"
    frontend = root / "frontend"
    frontend.mkdir(parents=True)
    (frontend / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {}, "exclude": STRUCTURAL + exclude}),
        encoding="utf-8",
    )
    (frontend / "quality-baseline.json").write_text(
        json.dumps({"tsconfigProductionExclusions": baseline}),
        encoding="utf-8",
    )
    for relative in files:
        path = frontend / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("export {}\n", encoding="utf-8")
    return root


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        capture_output=True,
        text=True,
    )


def test_passes_when_tsconfig_and_baseline_agree(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        exclude=["src/legacy/Old.tsx"],
        baseline=["src/legacy/Old.tsx"],
        files=["src/legacy/Old.tsx"],
    )
    result = _run(root)
    assert result.returncode == 0, result.stdout + result.stderr


def test_fails_on_exclusion_missing_from_baseline(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        exclude=["src/legacy/Old.tsx", "src/sneaky/New.tsx"],
        baseline=["src/legacy/Old.tsx"],
        files=["src/legacy/Old.tsx", "src/sneaky/New.tsx"],
    )
    result = _run(root)
    assert result.returncode == 1
    assert "src/sneaky/New.tsx" in result.stdout


def test_structural_exclusions_never_need_baseline(tmp_path: Path) -> None:
    root = _make_root(tmp_path, exclude=[], baseline=[])
    result = _run(root)
    assert result.returncode == 0, result.stdout + result.stderr


def test_fails_when_changed_file_remains_excluded(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        exclude=["src/legacy/Old.tsx"],
        baseline=["src/legacy/Old.tsx"],
        files=["src/legacy/Old.tsx"],
    )
    result = _run(root, "--changed", "frontend/src/legacy/Old.tsx")
    assert result.returncode == 1
    assert "src/legacy/Old.tsx" in result.stdout


def test_fails_when_changed_file_matches_excluded_glob(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        exclude=["src/router/**/*"],
        baseline=["src/router/**/*"],
        files=["src/router/index.ts", "src/router/deep/nested.ts"],
    )
    result = _run(root, "--changed", "frontend/src/router/deep/nested.ts")
    assert result.returncode == 1
    assert "src/router/**/*" in result.stdout


def test_changed_unexcluded_file_passes(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        exclude=["src/legacy/Old.tsx"],
        baseline=["src/legacy/Old.tsx"],
        files=["src/legacy/Old.tsx", "src/fresh/New.tsx"],
    )
    result = _run(root, "--changed", "frontend/src/fresh/New.tsx")
    assert result.returncode == 0, result.stdout + result.stderr


def test_fails_on_baseline_entry_for_missing_file(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        exclude=["src/legacy/Gone.tsx"],
        baseline=["src/legacy/Gone.tsx"],
        files=[],  # the excluded file does not exist on disk
    )
    result = _run(root)
    assert result.returncode == 1
    assert "Gone.tsx" in result.stdout


def test_fails_on_stale_baseline_entry(tmp_path: Path) -> None:
    # Entry removed from tsconfig but forgotten in the baseline: the debt
    # record must shrink too, or the exclusion can silently come back.
    root = _make_root(
        tmp_path,
        exclude=[],
        baseline=["src/legacy/Old.tsx"],
        files=["src/legacy/Old.tsx"],
    )
    result = _run(root)
    assert result.returncode == 1
    assert "src/legacy/Old.tsx" in result.stdout


def test_passes_when_removed_from_both(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        exclude=[],
        baseline=[],
        files=["src/legacy/Old.tsx"],
    )
    result = _run(root, "--changed", "frontend/src/legacy/Old.tsx")
    assert result.returncode == 0, result.stdout + result.stderr


def test_emit_baseline_prints_current_production_exclusions(
    tmp_path: Path,
) -> None:
    root = _make_root(
        tmp_path,
        exclude=["src/b/B.tsx", "src/a/A.tsx"],
        baseline=[],  # intentionally out of date
        files=["src/a/A.tsx", "src/b/B.tsx"],
    )
    result = _run(root, "--emit-baseline")
    assert result.returncode == 0
    emitted = json.loads(result.stdout)
    assert emitted == ["src/a/A.tsx", "src/b/B.tsx"]  # sorted, structural omitted


def test_real_repo_baseline_matches_tsconfig() -> None:
    """The committed baseline must stay in sync with the real tsconfig."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(REPO_ROOT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
