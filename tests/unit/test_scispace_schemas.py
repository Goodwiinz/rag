"""Tests for SciSpace shared schemas."""

import pytest
from pydantic import ValidationError


def test_tone_option_valid():
    from src.shared.scispace_schemas import ToneOption

    assert ToneOption.ACADEMIC == "academic"
    assert ToneOption.SIMPLIFIED == "simplified"
    assert ToneOption.CONCISE == "concise"
    assert ToneOption.EXPANDED == "expanded"


def test_rewrite_request_valid():
    from src.shared.scispace_schemas import RewriteRequest

    req = RewriteRequest(text="Some text to rewrite here.", tone="academic")
    assert req.preserve_citations is True


def test_rewrite_request_short_text_rejected():
    from src.shared.scispace_schemas import RewriteRequest

    with pytest.raises(ValidationError):
        RewriteRequest(text="Too short", tone="academic")


def test_integrity_score_response():
    from src.shared.scispace_schemas import IntegrityScoreResponse

    resp = IntegrityScoreResponse(
        document_id="550e8400-e29b-41d4-a716-446655440000",
        ai_probability=0.73,
        human_probability=0.27,
        method="roberta-base-openai-detector",
    )
    assert resp.ai_probability == 0.73


def test_extraction_column_schema():
    from src.shared.scispace_schemas import ExtractionColumn

    col = ExtractionColumn(name="Methodology", description="Research methodology used")
    assert col.name == "Methodology"
