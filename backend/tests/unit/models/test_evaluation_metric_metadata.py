"""R5-H5: EvaluationMetric.metadata doesn't exist — the JSON column is
`metric_metadata`.

`metadata` is a reserved name on every SQLAlchemy declarative class: it's the
class-level `MetaData` registry object (`Base.metadata`), inherited onto
every instance. Reading `metric.metadata.get(...)` doesn't raise at
attribute-access time — `.metadata` resolves fine, to the wrong object — it
raises `AttributeError` at `.get(...)` because `MetaData` has no `.get`. That
turned `GET /evaluation/jobs/{id}/metrics` into a 500, and every writer that
passed `metadata={...}` to `EvaluationMetric(...)` had the kwarg silently
accepted by the declarative constructor (mapped to nothing) and dropped —
`calculation_method`/`model_used` provenance was NULL forever, no error.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import MetaData

from src.models.evaluation import EvaluationMetric

pytestmark = pytest.mark.unit


def test_metric_metadata_round_trips() -> None:
    metric = EvaluationMetric(
        metric_type="rag_triad_faithfulness",
        metric_name="Faithfulness",
        value=0.9,
        query="q",
        metric_metadata={
            "calculation_method": "llm_judgment",
            "model_used": "gpt-3.5-turbo",
        },
    )

    assert metric.metric_metadata == {
        "calculation_method": "llm_judgment",
        "model_used": "gpt-3.5-turbo",
    }


def test_metadata_attribute_is_the_class_registry_not_row_data() -> None:
    """Pins the exact failure mode: `.metadata` is real (no AttributeError on
    the attribute itself) but is SQLAlchemy's MetaData registry, not this
    row's JSON — `.get(...)` on it is where the 500 came from. A future
    regression back to `EvaluationMetric(metadata=...)` / `metric.metadata`
    would be caught here before it reaches production."""
    metric = EvaluationMetric(
        metric_type="rag_triad_faithfulness",
        metric_name="Faithfulness",
        value=0.9,
        query="q",
        metric_metadata={"model_used": "gpt-4"},
    )

    assert isinstance(metric.metadata, MetaData)
    with pytest.raises(AttributeError):
        metric.metadata.get("model_used")  # type: ignore[attr-defined]


def test_metadata_kwarg_is_silently_dropped_not_persisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reproduces the writer-side half of R5-H5: passing `metadata=` to the
    constructor does not error and does not populate `metric_metadata` —
    exactly the "accepted but dropped" behavior that made the bug silent."""
    metric: Any = EvaluationMetric(
        metric_type="rag_triad_faithfulness",
        metric_name="Faithfulness",
        value=0.9,
        query="q",
        metadata={"calculation_method": "llm_judgment"},
    )

    # The real column default from the model (`default=dict`) only applies at
    # INSERT time via the ORM, so on a bare unflushed instance this is None —
    # the point is it is NOT the dict that was passed as `metadata=`.
    assert metric.metric_metadata is None
