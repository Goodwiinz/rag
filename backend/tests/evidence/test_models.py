"""Evidence model serialization tests."""

from uuid import uuid4

from src.models.evidence import StanceClassificationModel


def test_stance_classification_serializes_provenance() -> None:
    classification = StanceClassificationModel(
        claim_hash="a" * 64,
        claim_text="Original claim",
        source_id=uuid4(),
        source_content_hash="b" * 64,
        organization_id=uuid4(),
        stance="supporting",
        confidence=0.9,
        model_version="model",
    )

    data = classification.to_dict()

    assert data["claim_text"] == "Original claim"
    assert data["source_content_hash"] == "b" * 64
