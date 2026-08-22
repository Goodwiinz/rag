"""PR2 (audit R6-H3/M8/M9/M10/L12/M13) regression guards.

The heavyweight proof is environmental: `alembic upgrade head` on an empty
database must reach add_chat_progress_steps with model-parity schema
(run_local_ci.sh's advisory empty-DB step does this when PostgreSQL is up).
These tests pin the invariants that make that true.
"""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (BACKEND_ROOT / rel).read_text()


# ---------------------------------------------------------------------------
# R6-H3 — baseline exists, sits between initial and the first FK revision
# ---------------------------------------------------------------------------


def test_baseline_revision_wiring() -> None:
    baseline = _read("alembic/versions/r6h3_model_baseline.py")
    assert 'down_revision = "258df00ea837"' in baseline
    assert "Base.metadata.create_all" in baseline

    child = _read("alembic/versions/f931599b6b5b_enhance_document_processing.py")
    assert 'down_revision = "r6h3_model_baseline"' in child


def test_alembic_heads_single() -> None:
    import re
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    ).stdout
    heads = [ln.split(" ")[0] for ln in out.splitlines() if "(head)" in ln]
    # Single linear head — the exact id advances as revisions land.
    assert len(heads) == 1
    assert heads[0] and heads[0] != "<base>"


def test_env_py_installs_idempotent_guards() -> None:
    source = _read("alembic/env.py")
    assert "_install_idempotent_op_guards" in source
    # The guard set must cover every DDL op class that historically collided
    for fn in (
        "create_table",
        "add_column",
        "create_index",
        "create_unique_constraint",
        "create_check_constraint",
        "create_foreign_key",
    ):
        assert f"_op.{fn} =" in source or f"{fn} skipped" in source


# ---------------------------------------------------------------------------
# R6-M8 — citation identifiers are not globally unique in the model either
# ---------------------------------------------------------------------------


def test_citation_model_doi_arxiv_not_unique() -> None:
    import sys

    sys.path.insert(0, str(BACKEND_ROOT))
    from src.models.citation import Citation

    doi = Citation.__table__.columns["doi"]
    arxiv = Citation.__table__.columns["arxiv_id"]
    assert not doi.unique
    assert not arxiv.unique


# ---------------------------------------------------------------------------
# R2-L19 / R6-M13 — scheduled report job no longer targets a fake org
# ---------------------------------------------------------------------------


def test_beat_generate_reports_has_no_placeholder_org() -> None:
    source = _read("src/tasks/document_processing_tasks.py")
    args_pos = source.find('"generate-reports"')
    args_line = source.find('"args"', args_pos)
    assert args_line != -1
    assert "(None, 30)" in source[args_line : args_line + 80]
    # No live placeholder anywhere outside comments/docstrings.
    import ast as _ast

    for node in _ast.walk(_ast.parse(source)):
        if isinstance(node, _ast.Constant) and isinstance(node.value, str):
            assert node.value != "default_organization_id"


def test_generate_report_task_accepts_none_org() -> None:
    import ast

    tree = ast.parse(_read("src/tasks/document_processing_tasks.py"))
    found = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "generate_processing_report":
                found = True
                arg = node.args.args[1] if len(node.args.args) > 1 else None
                assert arg is not None and arg.arg == "organization_id"
                # default value must be None-tolerant annotation-wise: check
                # the body handles falsy org via _org_filter/true()
                src = ast.get_source_segment(
                    _read("src/tasks/document_processing_tasks.py"), node
                )
                assert "_org_filter" in src
    assert found


# ---------------------------------------------------------------------------
# R6-L12 — dead config docs removed; APIKey tables registered in metadata
# ---------------------------------------------------------------------------


def test_env_example_has_no_dead_vector_config() -> None:
    content = _read(".env.example")
    assert "QDRANT_URL" not in content
    assert "QDRANT_API_KEY" not in content
    assert "DO_KB_SHADOW_READ" not in content


def test_apikey_models_registered_in_metadata() -> None:
    import sys

    sys.path.insert(0, str(BACKEND_ROOT))
    import src.models  # noqa: F401
    from src.models.base import Base

    assert "api_keys" in Base.metadata.tables
    assert "api_key_usage_log" in Base.metadata.tables


# ---------------------------------------------------------------------------
# R6-M10 — o2r3s4t5u6v7 downgrade must not resurrect global uniqueness
# ---------------------------------------------------------------------------


def test_citation_uniqueness_downgrade_is_noop() -> None:
    source = _read(
        "alembic/versions/o2r3s4t5u6v7_drop_citation_identifier_uniqueness.py"
    )
    down = source[source.find("def downgrade") :]
    assert "unique=True" not in down
