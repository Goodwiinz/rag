"""Extraction Matrix service for structured data extraction from documents."""

import json
from typing import Any, Dict, List, Optional
from uuid import UUID

import openai
import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.models.document import Document
from src.models.extraction_matrix import ExtractionCell

logger = structlog.get_logger()

# In-memory store for background extraction status (same pattern as draft generation)
_extraction_status: Dict[str, Dict[str, Any]] = {}


class ExtractionMatrixService:
    """Service for building extraction prompts and parsing LLM extraction results."""

    @staticmethod
    def get_extraction_status(task_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a background extraction task."""
        return _extraction_status.get(task_id)

    @staticmethod
    def _get_openai_client() -> tuple:
        """Create an OpenAI client from settings. Returns (client, model)."""
        from src.core.config import settings

        azure_key = settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY
        azure_endpoint = (
            settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT
        )
        azure_deployment = getattr(
            settings, "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o"
        )
        azure_api_version = getattr(
            settings, "AZURE_OPENAI_CHAT_API_VERSION", "2024-05-01-preview"
        )
        openai_key = settings.OPENAI_API_KEY

        if azure_key and azure_endpoint:
            client = openai.AsyncAzureOpenAI(
                api_key=azure_key,
                azure_endpoint=azure_endpoint,
                api_version=azure_api_version,
            )
            return client, azure_deployment
        elif openai_key:
            client = openai.AsyncOpenAI(api_key=openai_key)
            return client, "gpt-4o-mini"
        else:
            raise RuntimeError("No OpenAI or Azure OpenAI API key configured.")

    async def run_background_extraction(
        self,
        matrix_id: UUID,
        document_ids: List[UUID],
        columns: List[Dict[str, Any]],
        task_id: str,
    ) -> None:
        """Run extraction in the background using its own DB session.

        Updates _extraction_status as it progresses.
        """
        _extraction_status[task_id] = {
            "status": "running",
            "matrix_id": str(matrix_id),
            "total": len(document_ids),
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "error": None,
        }

        try:
            client, model = self._get_openai_client()
        except RuntimeError as e:
            _extraction_status[task_id]["status"] = "failed"
            _extraction_status[task_id]["error"] = str(e)
            return

        async with AsyncSessionLocal() as db:
            for doc_id in document_ids:
                try:
                    doc_result = await db.execute(
                        select(Document).where(Document.id == doc_id)
                    )
                    document = doc_result.scalar_one_or_none()
                    if not document or not document.content_text:
                        _extraction_status[task_id]["skipped"] += 1
                        logger.info(
                            "bg_extraction_skip",
                            task_id=task_id,
                            document_id=str(doc_id),
                        )
                        continue

                    doc_text = document.content_text[:12000]
                    prompt = self._build_extraction_prompt(columns, doc_text)

                    response = await client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=2000,
                    )
                    raw_json = response.choices[0].message.content or ""
                    parsed = self._parse_extraction_result(raw_json, columns)

                    # Upsert cells
                    for col_name, cell_data in parsed.items():
                        existing = await db.execute(
                            select(ExtractionCell).where(
                                and_(
                                    ExtractionCell.matrix_id == matrix_id,
                                    ExtractionCell.document_id == doc_id,
                                    ExtractionCell.column_name == col_name,
                                )
                            )
                        )
                        existing_cell = existing.scalar_one_or_none()

                        if existing_cell:
                            existing_cell.value = cell_data.get("value")
                            existing_cell.citation_snippet = cell_data.get("citation")
                            existing_cell.confidence = 0.8
                        else:
                            db.add(
                                ExtractionCell(
                                    matrix_id=matrix_id,
                                    document_id=doc_id,
                                    column_name=col_name,
                                    value=cell_data.get("value"),
                                    citation_snippet=cell_data.get("citation"),
                                    confidence=0.8,
                                )
                            )

                    await db.commit()
                    _extraction_status[task_id]["completed"] += 1

                except Exception as e:
                    logger.error(
                        "bg_extraction_doc_failed",
                        task_id=task_id,
                        document_id=str(doc_id),
                        error=str(e),
                    )
                    _extraction_status[task_id]["failed"] += 1

        _extraction_status[task_id]["status"] = "completed"
        logger.info(
            "bg_extraction_complete",
            task_id=task_id,
            matrix_id=str(matrix_id),
            total=_extraction_status[task_id]["total"],
            completed=_extraction_status[task_id]["completed"],
            failed=_extraction_status[task_id]["failed"],
            skipped=_extraction_status[task_id]["skipped"],
        )

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

        # Strip markdown code fences if present
        cleaned = raw_json.strip() if raw_json else ""
        if cleaned.startswith("```"):
            # Remove opening fence (```json or ```)
            first_newline = cleaned.find("\n")
            if first_newline != -1:
                cleaned = cleaned[first_newline + 1:]
            # Remove closing fence
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()

        try:
            parsed = json.loads(cleaned)
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
