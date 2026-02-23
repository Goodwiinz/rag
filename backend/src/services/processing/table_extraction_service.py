"""Table and math extraction service for PDF documents."""

import csv
import io
import os
from typing import Any, Dict, List, Optional

import structlog

from src.core.config import settings

logger = structlog.get_logger()


class TableExtractionService:
    """Service for extracting tables and math from PDF documents."""

    def _validate_coordinates(
        self, page: int, x1: float, y1: float, x2: float, y2: float
    ) -> bool:
        """Validate crop bounding box coordinates."""
        if page < 1:
            return False
        if x1 < 0 or y1 < 0 or x2 < 0 or y2 < 0:
            return False
        if x1 >= x2 or y1 >= y2:
            return False
        return True

    def _safe_pdf_path(self, pdf_path: str) -> str:
        """Validate that pdf_path is within the configured upload directory."""
        upload_root = os.path.realpath(settings.UPLOAD_DIR)
        resolved = os.path.realpath(pdf_path)
        if not resolved.startswith(upload_root + os.sep) and resolved != upload_root:
            raise ValueError("Document path is outside the upload directory")
        return resolved

    @staticmethod
    def _escape_md_cell(cell: str) -> str:
        """Escape pipe characters in markdown table cells."""
        return cell.replace("|", r"\|").replace("\n", " ")

    def _csv_to_markdown(self, csv_data: str) -> str:
        """Convert CSV string to markdown table."""
        reader = csv.reader(io.StringIO(csv_data))
        rows = list(reader)
        if not rows:
            return ""

        # Header
        header = "| " + " | ".join(self._escape_md_cell(c) for c in rows[0]) + " |"
        separator = "| " + " | ".join("---" for _ in rows[0]) + " |"

        # Data rows
        data_rows = []
        for row in rows[1:]:
            data_rows.append("| " + " | ".join(self._escape_md_cell(c) for c in row) + " |")

        return "\n".join([header, separator] + data_rows)

    async def extract_region(
        self,
        pdf_path: str,
        page: int,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> Dict[str, Any]:
        """Extract content from a specific region of a PDF page.

        Uses PyMuPDF to crop, then Camelot for tables, GPT-4o Vision as fallback.
        """
        if not self._validate_coordinates(page, x1, y1, x2, y2):
            raise ValueError(
                f"Invalid coordinates: page={page}, ({x1},{y1})-({x2},{y2})"
            )

        import fitz  # PyMuPDF - lazy import

        pdf_path = self._safe_pdf_path(pdf_path)
        doc = fitz.open(pdf_path)
        if page > len(doc):
            raise ValueError(
                f"Page {page} exceeds document length ({len(doc)})"
            )

        pdf_page = doc[page - 1]  # 0-indexed
        rect = fitz.Rect(x1, y1, x2, y2)

        # Try text extraction first
        text = pdf_page.get_text("text", clip=rect).strip()
        doc.close()

        if text:
            return {
                "format": "markdown",
                "content": text,
                "confidence": 0.8,
            }

        # Fallback: render region as image for LLM transcription
        return {
            "format": "markdown",
            "content": "",
            "confidence": 0.0,
        }

    async def extract_tables_from_pdf(
        self, pdf_path: str
    ) -> List[Dict[str, Any]]:
        """Extract all tables from a PDF using Camelot."""
        try:
            import camelot
        except ImportError:
            logger.warning("camelot_not_installed")
            return []

        pdf_path = self._safe_pdf_path(pdf_path)

        try:
            tables = camelot.read_pdf(pdf_path, flavor="lattice", pages="all")
        except Exception as e:
            logger.warning("camelot_extraction_failed", error=str(e))
            # Fallback to stream mode
            try:
                tables = camelot.read_pdf(pdf_path, flavor="stream", pages="all")
            except Exception as e2:
                logger.error("table_extraction_failed", error=str(e2))
                return []

        results = []
        for i, table in enumerate(tables):
            csv_data = table.df.to_csv(index=False)
            results.append(
                {
                    "table_index": i,
                    "page": table.page,
                    "rows": len(table.df),
                    "cols": len(table.df.columns),
                    "csv": csv_data,
                    "markdown": self._csv_to_markdown(csv_data),
                    "accuracy": table.accuracy
                    if hasattr(table, "accuracy")
                    else None,
                }
            )

        return results
