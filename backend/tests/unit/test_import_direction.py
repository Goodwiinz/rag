"""Import-direction guard: the service layer must not import the API layer.

Audit finding B1 moved the agent tool implementations out of
``src/api/agent/`` into ``src/services/agent/`` precisely because service
code importing route modules inverts the dependency direction (API depends
on services, never the reverse). This test locks that in: any module under
``backend/src/services/`` that imports ``src.api`` (top-level or deferred,
absolute or relative) fails the build.

The allowlist is a ratchet: it enumerates the exact pre-existing violations
at the time this guard was introduced and must only ever shrink. Do not add
entries; fix the dependency direction instead (move the shared code into
``src/services/`` or ``src/shared/``).
"""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

BACKEND_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = BACKEND_DIR / "src"
SERVICES_DIR = SRC_DIR / "services"

# Module paths (relative to backend/, posix-style) permitted to import
# src.api. RATCHET — only remove entries, never add (see module docstring).
ALLOWED_VIOLATIONS: frozenset[str] = frozenset(
    {
        # Pre-existing (predates this guard): consumes ConsensusLevel /
        # EvidenceMeter / Stance, Pydantic types defined in
        # src/api/evidence/schemas.py via a relative `from ...api.evidence`
        # import. Fix by moving those schemas into src/shared/ or
        # src/services/evidence/ — out of scope for the B1 tools_impl move.
        "src/services/evidence/consensus_calculator.py",
    }
)


def _module_name_for(path: Path) -> str:
    """Dotted module name for a file under backend/ (e.g. src.services.agent.tools)."""
    rel = path.relative_to(BACKEND_DIR).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _resolve_relative(module_name: str, is_package: bool, node: ast.ImportFrom) -> str:
    """Resolve a relative ``from ... import`` to an absolute dotted module path."""
    parts = module_name.split(".")
    # Level 1 refers to the containing package: the module itself for an
    # __init__.py, the parent package for a plain module. Each further level
    # walks one package up.
    package = parts if is_package else parts[:-1]
    base = package[: len(package) - (node.level - 1)]
    if node.module:
        base.append(node.module)
    return ".".join(base)


def _api_imports(path: Path) -> list[str]:
    """Return descriptions of every ``src.api`` import in the file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module_name = _module_name_for(path)
    is_package = path.name == "__init__.py"
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "src.api" or alias.name.startswith("src.api."):
                    hits.append(f"{path}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                target = node.module or ""
            else:
                target = _resolve_relative(module_name, is_package, node)
            if target == "src.api" or target.startswith("src.api."):
                names = ", ".join(a.name for a in node.names)
                hits.append(f"{path}:{node.lineno}: from {target} import {names}")
    return hits


def test_services_layer_does_not_import_api_layer() -> None:
    assert SERVICES_DIR.is_dir(), f"services dir not found: {SERVICES_DIR}"

    violations: list[str] = []
    for py_file in sorted(SERVICES_DIR.rglob("*.py")):
        rel = py_file.relative_to(BACKEND_DIR).as_posix()
        if rel in ALLOWED_VIOLATIONS:
            continue
        violations.extend(_api_imports(py_file))

    assert not violations, (
        "Service-layer modules must not import from src.api (audit B1). "
        "Move the shared code into src/services/ or src/shared/ instead.\n"
        + "\n".join(violations)
    )


def test_guard_scans_a_meaningful_number_of_files() -> None:
    """Fail loudly if the scan silently goes blind (e.g. path layout changes)."""
    scanned = list(SERVICES_DIR.rglob("*.py"))
    assert len(scanned) > 20, (
        f"Import-direction guard only found {len(scanned)} files under "
        f"{SERVICES_DIR} — the services tree moved and this guard needs updating."
    )
