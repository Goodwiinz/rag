"""Regression: multimodal_processing_service must import `io`.

The PDF OCR path does `Image.open(io.BytesIO(img_data))` but `io` was never
imported, so every OCR attempt raised NameError — caught by the surrounding
best-effort handler, silently dropping all OCR text from image-only PDFs. This
pins the import so the OCR path can run.
"""

from __future__ import annotations

import io as stdlib_io

import pytest

from src.services.processing import multimodal_processing_service as mod


@pytest.mark.unit
def test_module_imports_io():
    # The name `io` must resolve to the stdlib module in the service's namespace
    # (so `io.BytesIO(...)` in the OCR path doesn't NameError).
    assert getattr(mod, "io", None) is stdlib_io
    assert hasattr(mod.io, "BytesIO")
