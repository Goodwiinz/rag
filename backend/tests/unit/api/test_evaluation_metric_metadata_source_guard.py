"""R5-H5 source guard: no live reader/writer of EvaluationMetric may use the
`.metadata` attribute or a bare `metadata=` constructor kwarg — the column is
`metric_metadata`.

This complements the model-level tests in
`tests/unit/models/test_evaluation_metric_metadata.py`: those pin the
attribute-shadowing mechanism; this pins the exact three call sites that were
broken (the metrics-list route, and the RAG-triad + batch metric writers) so
a regression back to `.metadata` in any of them fails a test directly instead
of only failing at runtime against a live DB.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_BACKEND_SRC = Path(__file__).resolve().parents[3] / "src"

_FILES = [
    _BACKEND_SRC / "api" / "infrastructure" / "evaluation.py",
    _BACKEND_SRC / "services" / "evaluation" / "rag_evaluation_service.py",
    _BACKEND_SRC / "tasks" / "evaluation_tasks.py",
]

# `metric.metadata` / `metric_or_alias.metadata.get(...)` reads — the
# class-level MetaData registry, not row data. Deliberately narrow (requires
# a `.metadata` attribute access on something, not just the bare word
# "metadata") so it doesn't false-positive on RAGEvaluationInput/
# RAGTriadMetrics's own (correctly named) `.metadata` dataclass field.
_BAD_READ = re.compile(r"\bmetric\.metadata\b")

# `EvaluationMetric(...  metadata={ ...)` constructor kwarg.
_BAD_WRITE = re.compile(r"EvaluationMetric\(")


def test_no_file_reads_metric_dot_metadata() -> None:
    for path in _FILES:
        source = path.read_text()
        assert not _BAD_READ.search(source), (
            f"{path} reads metric.metadata — that's SQLAlchemy's class-level "
            "MetaData registry, not the row's JSON column. Use "
            "metric.metric_metadata."
        )


def test_no_evaluation_metric_construction_uses_bare_metadata_kwarg() -> None:
    for path in _FILES:
        source = path.read_text()
        for match in _BAD_WRITE.finditer(source):
            # Look at the following ~600 chars (comfortably past every
            # EvaluationMetric(...) call in these files) for a bare
            # `metadata=` kwarg that isn't `metric_metadata=`.
            window = source[match.end() : match.end() + 600]
            close_idx = window.find("\n    )")
            call_body = window[: close_idx if close_idx != -1 else len(window)]
            assert not re.search(r"(?<!_)\bmetadata=", call_body), (
                f"{path}: an EvaluationMetric(...) construction near offset "
                f"{match.start()} uses a bare `metadata=` kwarg — the "
                "declarative constructor accepts it silently and drops it "
                "(the column is metric_metadata); this is the exact R5-H5 "
                "writer-side bug."
            )
