"""Pipeline-A wiring: the PDF branch of `get_processing_pipeline` must run
figure extraction, as an optional (non-required) step."""

from __future__ import annotations

import pytest

from src.models.document import DocumentType
from src.services.processing.multimodal_processing_service import (
    MultimodalProcessingService,
)

pytestmark = pytest.mark.unit


def test_pdf_pipeline_includes_figure_extraction_step():
    # Skip __init__ (db session + service wiring) — get_processing_pipeline
    # only reads bound methods off the class, mirroring
    # test_multimodal_pdf_s3_path.py's `_svc()` helper.
    service = object.__new__(MultimodalProcessingService)

    steps = service.get_processing_pipeline(DocumentType.PDF)

    figure_steps = [s for s in steps if s.name == "Figure Extraction"]
    assert len(figure_steps) == 1
    assert figure_steps[0].required is False
