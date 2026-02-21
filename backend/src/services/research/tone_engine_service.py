"""Scholarly Tone Engine service for text rewriting with citation preservation."""

import re
from typing import Any, Dict, List, Optional

import structlog

from src.core.config import settings
from src.core.prompts.tone_prompts import TONE_PROMPTS

logger = structlog.get_logger()

CITATION_RE = re.compile(r"\[\d+\]")


class ToneEngineService:
    """Service for rewriting text with adjustable academic tone."""

    def __init__(self) -> None:
        import openai
        self._openai = openai
        api_key = settings.OPENAI_API_KEY or None
        self._client = openai.AsyncOpenAI(api_key=api_key) if api_key else None  # type: ignore[assignment]

    def _extract_citations(self, text: str) -> List[str]:
        """Extract all citation markers from text."""
        return CITATION_RE.findall(text)

    async def rewrite(
        self,
        text: str,
        tone: str,
        model: Optional[str] = None,
        preserve_citations: bool = True,
    ) -> Dict[str, Any]:
        """Rewrite text with the specified tone."""
        system_prompt = TONE_PROMPTS.get(tone)
        if not system_prompt:
            raise ValueError(f"Unknown tone: {tone}. Valid: {list(TONE_PROMPTS.keys())}")

        if self._client is None:
            raise RuntimeError("OpenAI API key is not configured")

        original_citations = self._extract_citations(text) if preserve_citations else []

        model_id = model or "gpt-4o"

        try:
            response = await self._client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.7,
            )
        except self._openai.APIError as e:
            raise RuntimeError(f"OpenAI API error: {e}") from e

        if not response.choices:
            raise RuntimeError("OpenAI returned no completion choices")

        rewritten = response.choices[0].message.content or ""

        # Verify citation preservation
        rewritten_citations = self._extract_citations(rewritten)
        preserved = [c for c in original_citations if c in rewritten_citations]

        if preserve_citations and set(original_citations) != set(rewritten_citations):
            logger.warning(
                "citation_mismatch",
                original=original_citations,
                rewritten=rewritten_citations,
            )

        return {
            "original": text,
            "rewritten": rewritten,
            "tone_applied": tone,
            "citations_preserved": preserved,
        }
