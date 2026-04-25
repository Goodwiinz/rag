"""LLM-backed intent classifier with keyword fallback.

Classifies user queries into one of four intents:
  research, writing, knowledge_graph, general

Uses a lightweight LLM (gpt-4o-mini) with structured output for primary
classification, falling back to weighted keyword matching when the LLM is
unavailable or returns low confidence.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.services.agent.graph import INTENT_KEYWORDS, INTENT_PRIORITY

logger = logging.getLogger(__name__)

# Type alias matching the state schema
IntentType = Literal["research", "writing", "knowledge_graph", "general"]

# Confidence threshold below which the LLM result is discarded in favour of
# the keyword classifier.
_LLM_CONFIDENCE_THRESHOLD = 0.7


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class IntentClassification(BaseModel):
    """Structured output schema for the LLM classifier."""

    intent: Literal["research", "writing", "knowledge_graph", "general"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


@dataclass(frozen=True)
class ClassificationResult:
    """Immutable result returned by all classifier functions.

    Attributes:
        intent:     One of research, writing, knowledge_graph, general.
        confidence: 0.0-1.0 indicating classifier certainty.
        reasoning:  Short human-readable explanation.
        source:     Which classifier produced this result
                    ("llm", "keyword", or "fallback").
    """

    intent: IntentType
    confidence: float
    reasoning: str
    source: str  # "llm", "keyword", "fallback"


# ---------------------------------------------------------------------------
# LLM construction (gpt-4o-mini, mirrors _build_llm in graph.py)
# ---------------------------------------------------------------------------


def _build_classifier_llm():
    """Build a lightweight LangChain chat model for intent classification.

    Uses the same Azure/OpenAI config resolution as ``_build_llm`` in
    ``graph.py`` but targets gpt-4o-mini with temperature=0 for
    deterministic, fast classification.
    """
    from src.core.openai_endpoint import classify_openai_endpoint

    settings = get_settings()

    endpoint = (
        settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT or ""
    )
    api_key = (
        settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY or ""
    )
    api_version = (
        settings.AZURE_OPENAI_CHAT_API_VERSION or settings.AZURE_OPENAI_API_VERSION
    )

    if not endpoint or not api_key:
        raise RuntimeError(
            "Azure/OpenAI chat endpoint and API key must be configured. "
            "Set AZURE_OPENAI_CHAT_ENDPOINT + AZURE_OPENAI_CHAT_API_KEY "
            "(or the non-CHAT variants)."
        )

    if classify_openai_endpoint(endpoint) == "openai_compatible":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=api_key,
            base_url=endpoint,
            temperature=0,
            max_tokens=256,
        )
    else:
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_deployment="gpt-4o-mini",
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            temperature=0,
            max_tokens=256,
        )


# ---------------------------------------------------------------------------
# System prompt with few-shot examples
# ---------------------------------------------------------------------------

_CLASSIFIER_SYSTEM_PROMPT = """\
You are an intent classifier for a RAG-powered academic research platform.
Given the user's query, classify it into exactly ONE of these intents:

- **research**: Searching, finding, discovering, or ingesting papers and documents.
- **writing**: Drafting, summarizing, creating notes, literature reviews, bibliographies.
- **knowledge_graph**: Extracting entities, exploring relationships, ontology queries.
- **general**: Anything that doesn't clearly fit the above categories.

Return your classification with a confidence score (0.0-1.0) and brief reasoning.

## Few-shot examples

Query: "Find recent papers on transformer architectures"
→ intent: research, confidence: 0.95, reasoning: "Explicit search request for papers."

Query: "Summarize the key findings of this document"
→ intent: writing, confidence: 0.92, reasoning: "Summarization is a writing task."

Query: "What entities are mentioned in this paper?"
→ intent: knowledge_graph, confidence: 0.90, reasoning: "Entity extraction is a knowledge graph task."

Query: "Hello, can you help me?"
→ intent: general, confidence: 0.85, reasoning: "Greeting with no specific task."

Query: "try again"
Previous tool: ingest_arxiv_papers (status: skipped)
→ intent: research, confidence: 0.85, reasoning: "Retry of the prior failed ingest call — same intent as the original tool."

## Common confusions

- "search the knowledge graph" → knowledge_graph (NOT research)
- "find entities" → knowledge_graph (NOT research)
- "write about papers I found" → writing (NOT research)
- "create a note summarizing..." → writing (NOT general)
- "import papers" or "ingest" → research (ingestion pipeline)
- Short retry phrases ("try again", "retry", "do it", "again") inherit the intent of the previous tool call when one is shown below.

## Page context
{page_context_text}

## Previous assistant turn
{previous_turn_text}

## Previous tool call
{prior_tool_text}
"""


# ---------------------------------------------------------------------------
# Keyword classifier
# ---------------------------------------------------------------------------


def classify_intent_keywords(query: str) -> ClassificationResult:
    """Classify intent using weighted keyword matching.

    Extracts the keyword logic from graph.py's intent_classifier_node.
    Returns a ClassificationResult with source="keyword".
    """
    query_lower = query.lower()

    scores: Dict[str, int] = {intent: 0 for intent in INTENT_KEYWORDS}
    for intent, keyword_weights in INTENT_KEYWORDS.items():
        for kw, weight in keyword_weights:
            if kw in query_lower:
                scores[intent] += weight

    best_score = max(scores.values())

    if best_score == 0:
        return ClassificationResult(
            intent="general",
            confidence=0.0,
            reasoning="No keyword matches found.",
            source="keyword",
        )

    # Among intents with the best score, pick by priority
    candidates = [i for i, s in scores.items() if s == best_score]
    best_intent: IntentType = candidates[0]
    for preferred in INTENT_PRIORITY:
        if preferred in candidates:
            best_intent = preferred  # type: ignore[assignment]
            break

    # Normalise confidence: best_score / (best_score + 2) gives a
    # value in (0, 1) that saturates toward 1 for high scores.
    confidence = best_score / (best_score + 2)

    return ClassificationResult(
        intent=best_intent,
        confidence=round(confidence, 2),
        reasoning=f"Keyword match (score {best_score}) for intent '{best_intent}'.",
        source="keyword",
    )


# ---------------------------------------------------------------------------
# LLM classifier
# ---------------------------------------------------------------------------


def _format_prior_tool(prior_tool: Optional[Dict[str, Any]]) -> str:
    """Render the prior tool call as a compact text block for the prompt.

    Returns "None" when no prior tool is available. Truncates large fields
    to keep the prompt within ~150 extra tokens.
    """
    if not prior_tool:
        return "None"
    name = prior_tool.get("name") or "unknown"
    raw_args = prior_tool.get("args") or {}
    raw_result = prior_tool.get("result") or ""
    try:
        args_text = json.dumps(raw_args, default=str)[:200]
    except (TypeError, ValueError):
        args_text = str(raw_args)[:200]
    result_text = (
        raw_result if isinstance(raw_result, str) else json.dumps(raw_result, default=str)
    )[:200]
    return (
        f"Tool: {name}\n"
        f"Args: {args_text}\n"
        f"Result (truncated): {result_text}"
    )


async def classify_intent_llm(
    query: str,
    page_context: Dict[str, Any],
    previous_turn: str = "",
    prior_tool: Optional[Dict[str, Any]] = None,
) -> ClassificationResult:
    """Classify intent using a lightweight LLM with structured output.

    Args:
        query:          The user's current query.
        page_context:   Page context dict (type, project_id, etc.).
        previous_turn:  The previous assistant message (for conversational context).
        prior_tool:     Optional dict with keys ``name``, ``args``, ``result``
                        describing the most recent tool call. Helps classify
                        retry phrases like "try again".

    Returns:
        ClassificationResult with source="llm".

    Raises:
        Any exception from the LLM call (caller should handle).
    """
    llm = _build_classifier_llm()
    chain = llm.with_structured_output(IntentClassification)

    page_type = page_context.get("type", "unknown")
    project_id = page_context.get("project_id", "")
    if page_type == "project" and project_id:
        page_context_text = (
            f"User is on a project page (project_id={project_id})."
        )
    elif page_type != "unknown":
        page_context_text = f"User is on the {page_type} page."
    else:
        page_context_text = "No specific page context."

    previous_turn_text = previous_turn if previous_turn else "None"
    prior_tool_text = _format_prior_tool(prior_tool)

    system_text = _CLASSIFIER_SYSTEM_PROMPT.format(
        page_context_text=page_context_text,
        previous_turn_text=previous_turn_text,
        prior_tool_text=prior_tool_text,
    )

    messages = [
        SystemMessage(content=system_text),
        HumanMessage(content=query),
    ]

    classification: IntentClassification = await chain.ainvoke(messages)

    return ClassificationResult(
        intent=classification.intent,
        confidence=classification.confidence,
        reasoning=classification.reasoning,
        source="llm",
    )


# ---------------------------------------------------------------------------
# Fallback-aware classifier
# ---------------------------------------------------------------------------


async def classify_intent_with_fallback(
    query: str,
    page_context: Dict[str, Any],
    previous_turn: str = "",
    prior_tool: Optional[Dict[str, Any]] = None,
) -> ClassificationResult:
    """Classify intent with keyword-first, LLM-escalation strategy.

    1. Run keyword classifier. If confidence >= 0.7, return immediately (no LLM).
    2. For ambiguous queries, escalate to LLM for better accuracy.
    3. If the LLM call fails or returns low confidence, fall back to the
       keyword result.

    Args:
        query:          The user's current query.
        page_context:   Page context dict.
        previous_turn:  Previous assistant message for context.
        prior_tool:     Optional prior tool call (name/args/result) — passed
                        through to the LLM classifier for retry-style queries.

    Returns:
        ClassificationResult (never raises).
    """
    keyword_result = classify_intent_keywords(query)

    if keyword_result.confidence >= _LLM_CONFIDENCE_THRESHOLD:
        logger.debug(
            "Keyword classifier confident (%.2f) for intent '%s', skipping LLM",
            keyword_result.confidence,
            keyword_result.intent,
        )
        return keyword_result

    # Ambiguous query — escalate to LLM for better accuracy
    try:
        llm_result = await classify_intent_llm(
            query, page_context, previous_turn, prior_tool
        )

        if llm_result.confidence >= _LLM_CONFIDENCE_THRESHOLD:
            return llm_result

        logger.info(
            "LLM confidence %.2f < %.2f for ambiguous query, using keyword result",
            llm_result.confidence,
            _LLM_CONFIDENCE_THRESHOLD,
        )
    except Exception as exc:
        logger.warning("LLM classifier failed, using keyword result: %s", exc)

    return keyword_result
