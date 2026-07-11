"""Guard against resurrecting dead never-imported backend packages (tranche 2).

Regression guard for audit finding B4 (system-design audit, PR #1123),
second tranche of the dead-package cleanup (tranche 1 = ``src.architecture``
/ ``src.resilience`` in PR #1124). The following were deleted because they had
zero production importers outside themselves:

* ``src.performance`` — perf/benchmark scaffolding; only importer was a
  stand-alone, non-CI ``scripts/validate_performance_optimizations.py``.
* ``src.evaluation`` — DeepEval demo scaffolding; no importers (distinct from
  the *live* ``src.api.infrastructure.evaluation`` router and
  ``src.models.evaluation`` model, which remain).
* ``src.monitoring`` — a self-contained observability stack whose router is
  never mounted in ``main.py``; its only production importers were two dead
  files inside the live ``src.observability`` package, deleted alongside it:
  ``document_processing_observability`` and ``sli_slo_monitoring``.

If a partial revert or stray re-add brings any of these back, this test fails
loudly so the dead code cannot silently return.

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


@pytest.mark.parametrize("module_name", ["src", "src.shared.enums"])
def test_positive_control_parent_is_importable(module_name: str) -> None:
    """Non-vacuous guard: the import machinery and the ``src`` root resolve.

    Without this, an environment where *nothing* is importable would make the
    ``_is_absent`` assertions below pass for the wrong reason.
    """
    assert (
        importlib.util.find_spec(module_name) is not None
    ), f"{module_name!r} should be importable; the test environment is broken"


@pytest.mark.parametrize(
    "module_name",
    [
        # Deleted top-level packages.
        "src.performance",
        "src.performance.benchmarks",
        "src.performance.multi_tier_cache",
        "src.evaluation",
        "src.evaluation.deepeval_integration",
        "src.evaluation.evaluation_runner",
        "src.monitoring",
        "src.monitoring.main",
        "src.monitoring.api.websocket_handlers",
        "src.monitoring.services.observability_manager",
        # Dead files removed from the still-live src.observability package
        # (they were the only production importers of src.monitoring).
        "src.observability.document_processing_observability",
        "src.observability.sli_slo_monitoring",
    ],
)
def test_dead_package_not_importable(module_name: str) -> None:
    """Deleted packages/modules must not be importable again."""
    assert _is_absent(
        module_name
    ), f"{module_name!r} was deleted for being dead code and must not return"
