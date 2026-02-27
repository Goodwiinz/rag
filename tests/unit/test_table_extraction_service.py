"""Tests for the Table Extraction service."""

import pytest
from src.services.processing.table_extraction_service import TableExtractionService


def test_crop_coordinates_validation():
    service = TableExtractionService()
    assert service._validate_coordinates(1, 0, 0, 100, 100) is True
    assert service._validate_coordinates(1, -1, 0, 100, 100) is False
    assert service._validate_coordinates(1, 100, 0, 50, 100) is False  # x1 > x2


def test_csv_to_markdown():
    service = TableExtractionService()
    csv_data = "Name,Age,City\nAlice,30,NYC\nBob,25,LA"
    md = service._csv_to_markdown(csv_data)
    assert "| Name | Age | City |" in md
    assert "| Alice | 30 | NYC |" in md
    assert "---" in md
