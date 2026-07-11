"""Guard against resurrecting dead never-imported backend packages.

Regression guard for audit finding B4 / item P0.5 (system-design audit,
PR #1123). The ``src.architecture`` and ``src.resilience`` packages were
A/B-testing scaffolding with no production importers outside themselves and
were deleted in the first tranche of the dead-package cleanup. If a partial
revert (or a stray re-add) brings either package back, this test fails loudly
so the dead code cannot silently return.

Pure unit test — no external services, only importlib introspection.
"""

import importlib.util

import pytest


def _is_absent(module_name: str) -> bool:
    """True when the module cannot be located at all.

    ``find_spec`` returns ``None`` for a missing top-level package, but raises
    ``ModuleNotFoundError`` for a dotted submodule whose parent package is gone
    — both mean "not importable", which is what we want to assert.
    """
    try:
        return importlib.util.find_spec(module_name) is None
    except ModuleNotFoundError:
        return True


@pytest.mark.parametrize(
    "module_name",
    [
        "src.architecture",
        "src.architecture.ab_testing_microservices",
        "src.resilience",
        "src.resilience.ab_testing_resilience",
    ],
)
def test_dead_package_not_importable(module_name: str) -> None:
    """Deleted packages/modules must not be importable again."""
    assert _is_absent(
        module_name
    ), f"{module_name!r} was deleted for being dead code and must not return"
