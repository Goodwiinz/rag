"""Extraction Matrix service for structured data extraction from documents."""

import json
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger()


class ExtractionMatrixService:
    """Service for building extraction prompts and parsing LLM extraction results."""

    def _build_extraction_prompt(
        self, columns: List[Dict[str, Any]], document_text: str
    ) -> str:
        """Build a structured extraction prompt for the LLM.

        Args:
            columns: List of column definitions, each with 'name' and optional 'description'.
            document_text: The full text of the document to extract from.

        Returns:
            A prompt string instructing the LLM to return JSON with keys matching column names.
        """
        column_descriptions = []
        for col in columns:
            name = col["name"]
            desc = col.get("description") or "Extract relevant information"
            column_descriptions.append(f'- "{name}": {desc}')

        columns_block = "\n".join(column_descriptions)

        prompt = (
            "You are a research data extraction assistant. "
            "Extract the following information from the document text below.\n\n"
            "For each column, provide a JSON object with keys matching the column names. "
            "Each value should be an object with two fields:\n"
            '  - "value": the extracted information (string or null if not found)\n'
            '  - "citation": a brief quote or page reference from the source text (string or null)\n\n'
            "Columns to extract:\n"
            f"{columns_block}\n\n"
            "Document text:\n"
            f"{document_text}\n\n"
            "Respond ONLY with valid JSON. No markdown, no explanation."
        )

        return prompt

    def _parse_extraction_result(
        self, raw_json: str, columns: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Parse the LLM's JSON output into a structured result.

        Args:
            raw_json: Raw JSON string from the LLM.
            columns: List of column definitions to validate against.

        Returns:
            Dict mapping column names to {"value": ..., "citation": ...}.
            Missing columns are filled with None values.
        """
        result: Dict[str, Dict[str, Any]] = {}

        try:
            parsed = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "extraction_parse_failed",
                raw_preview=raw_json[:200] if raw_json else "",
            )
            parsed = {}

        for col in columns:
            name = col["name"]
            if name in parsed and isinstance(parsed[name], dict):
                result[name] = {
                    "value": parsed[name].get("value"),
                    "citation": parsed[name].get("citation"),
                }
            else:
                result[name] = {"value": None, "citation": None}

        return result
