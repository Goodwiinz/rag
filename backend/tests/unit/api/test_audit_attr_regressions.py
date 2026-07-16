"""Regression tests for the 2026-07-16 deep-audit live findings.

Each guards a bug where code referenced an attribute/enum member that does not
exist (or shadowed a name), failing at build/validation time while a broad
except converted the failure into a 500 or a silent drop:

1. GET /documents/{id}/entities used Entity.confidence_score / entity.metadata
   (real: confidence / properties) — 500 for any document with entities.
2. The evaluation report endpoint was named `generate_evaluation_report`,
   shadowing the imported Celery task of the same name, so `.delay` resolved to
   the endpoint function — reports never generated, client told "started".
3. arXiv affiliation extraction emitted extraction_method="metadata", not an
   ExtractionMethod member — pydantic ValidationError swallowed, every
   institution entity silently dropped.
"""

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy import select


@pytest.mark.unit
def test_entity_confidence_filter_compiles():
    """The entities-endpoint filter must use real Entity columns."""
    from src.models.entity import Entity, EntityType

    stmt = select(Entity).where(
        Entity.entity_type == EntityType.PERSON,
        Entity.confidence >= 0.5,
    )
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "confidence" in compiled

    # The attributes the response construction reads must be mapped columns,
    # not accidental class-level objects (entity.metadata resolves to the
    # SQLAlchemy declarative MetaData registry — never row data).
    mapped = {c.key for c in Entity.__table__.columns}
    assert "confidence" in mapped
    assert "properties" in mapped
    assert "confidence_score" not in mapped


@pytest.mark.unit
def test_evaluation_report_task_not_shadowed():
    """The module global `generate_evaluation_report` must stay the Celery task
    (something with .delay), not be rebound to an endpoint function."""
    from src.api.infrastructure import evaluation

    assert hasattr(evaluation.generate_evaluation_report, "delay"), (
        "generate_evaluation_report was shadowed — the report endpoint must "
        "not reuse the Celery task's name"
    )


@pytest.mark.unit
def test_affiliation_entities_use_valid_extraction_method():
    """Affiliation entities must carry a valid ExtractionMethod value, or the
    CreateEntityRequest validation drops them silently."""
    from src.models.graph import ExtractionMethod
    from src.services.arxiv.arxiv_kg_integration import (
        ArXivKnowledgeGraphIntegration,
    )

    integration = ArXivKnowledgeGraphIntegration()
    entities = integration._extract_affiliations(
        {
            "authors_detailed": [
                {"name": "A. Vaswani", "affiliations": ["Google Brain"]}
            ]
        }
    )

    assert entities, "expected an institution entity for the affiliation"
    valid_values = {m.value for m in ExtractionMethod}
    for entity in entities:
        assert entity["extraction_method"] in valid_values
