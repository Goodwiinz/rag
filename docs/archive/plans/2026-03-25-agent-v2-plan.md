# Agent v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance the NOUS agent with LLM-based intent classification, plan-and-execute, context compaction, reflection loops, structured error recovery, and persistent memory.

**Architecture:** Evolutionary enhancement — add new nodes to the existing LangGraph StateGraph. Each feature is a new module under `backend/src/services/agent/` wired into the graph. Subgraphs (research, writing, data) each get shared utility nodes (interrupt, compactor, reflection). Frontend gets new SSE events and a plan card component.

**Tech Stack:** LangGraph, langchain-openai (gpt-4o + gpt-4o-mini), PostgreSQL, Qdrant, Alembic, sentence-transformers, Zustand, Next.js 15

**Design doc:** `docs/plans/2026-03-25-agent-v2-design.md`

---

## Phase 1: Foundation (State + Error Recovery)

### Task 1: Extend AgentState Schema

**Files:**

- Modify: `backend/src/services/agent/state.py:8-29`

**Step 1: Write the failing test**

```python
# backend/tests/unit/services/test_agent_state.py
import pytest
from src.services.agent.state import AgentState

@pytest.mark.unit
class TestAgentStateV2Fields:
    def test_state_has_plan_field(self):
        state: AgentState = {
            "messages": [], "page_context": {}, "retrieved_contexts": [],
            "tool_executions": [], "thread_id": "", "tool_loop_count": 0,
            "error_count": 0, "last_error": "", "pending_confirmation": {},
            "user_confirmed": False, "intent": "general", "user_memories": [],
            "plan": [], "reflection_count": 0, "compaction_count": 0,
            "intent_confidence": 0.0, "last_error_info": {},
        }
        assert state["plan"] == []
        assert state["reflection_count"] == 0
        assert state["compaction_count"] == 0
        assert state["intent_confidence"] == 0.0
        assert state["last_error_info"] == {}
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/services/test_agent_state.py -v`
Expected: FAIL (missing keys in TypedDict)

**Step 3: Write minimal implementation**

Add the new fields to `backend/src/services/agent/state.py`:

```python
class AgentState(TypedDict):
    """Full agent state passed through the graph."""
    messages: Annotated[list, add_messages]
    page_context: dict
    retrieved_contexts: list
    tool_executions: list
    thread_id: str
    tool_loop_count: int
    error_count: int
    last_error: str
    pending_confirmation: dict
    user_confirmed: bool
    intent: str
    user_memories: list
    # --- v2 additions ---
    plan: list                # [{step, tool, args_hint}] advisory plan
    reflection_count: int     # Max 2 per turn, reset per user message
    compaction_count: int     # Increments each compaction, reset per turn
    intent_confidence: float  # LLM classifier confidence 0-1
    last_error_info: dict     # {category, message, suggestion}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/services/test_agent_state.py -v`
Expected: PASS

**Step 5: Update initial state construction**

Modify `backend/src/api/agent/execute.py` — find the `_run_agent_graph` function and the `event_generator` function where initial state is constructed. Add defaults:

```python
"plan": [],
"reflection_count": 0,
"compaction_count": 0,
"intent_confidence": 0.0,
"last_error_info": {},
```

**Step 6: Commit**

```bash
git add backend/src/services/agent/state.py backend/tests/unit/services/test_agent_state.py backend/src/api/agent/execute.py
git commit -m "feat(agent): extend AgentState with v2 fields (plan, reflection, compaction, confidence)"
```

---

### Task 2: Create Error Recovery Module

**Files:**

- Create: `backend/src/services/agent/error_recovery.py`
- Test: `backend/tests/unit/services/test_agent_error_recovery.py`

**Step 1: Write the failing tests**

```python
# backend/tests/unit/services/test_agent_error_recovery.py
import asyncio
import json
import pytest
from unittest.mock import AsyncMock

@pytest.mark.unit
class TestClassifyError:
    def test_timeout_is_transient(self):
        from src.services.agent.error_recovery import classify_error
        err = classify_error("search_arxiv", asyncio.TimeoutError())
        assert err.category == "transient"

    def test_connection_error_is_transient(self):
        from src.services.agent.error_recovery import classify_error
        err = classify_error("search_arxiv", ConnectionError("reset"))
        assert err.category == "transient"

    def test_not_found_payload_is_recoverable(self):
        from src.services.agent.error_recovery import classify_error_from_payload
        err = classify_error_from_payload(
            "add_document_to_project",
            {"error": "Document abc123 not found"}
        )
        assert err.category == "recoverable"
        assert "ingest" in err.suggestion.lower()

    def test_permission_denied_is_user_fixable(self):
        from src.services.agent.error_recovery import classify_error
        err = classify_error("search_documents", PermissionError("org mismatch"))
        assert err.category == "user_fixable"

    def test_generic_exception_is_fatal(self):
        from src.services.agent.error_recovery import classify_error
        err = classify_error("search_arxiv", RuntimeError("unexpected"))
        assert err.category == "fatal"

    def test_hint_for_known_tool_error(self):
        from src.services.agent.error_recovery import classify_error_from_payload
        err = classify_error_from_payload(
            "ingest_arxiv_papers",
            {"error": "timed out after 120s"}
        )
        assert err.category == "transient"

    def test_no_results_is_recoverable(self):
        from src.services.agent.error_recovery import classify_error_from_payload
        err = classify_error_from_payload(
            "search_arxiv",
            {"error": "No results found"}
        )
        assert err.category == "recoverable"
        assert "broader" in err.suggestion.lower()


@pytest.mark.unit
class TestToolErrorFormat:
    def test_to_tool_message_content(self):
        from src.services.agent.error_recovery import ToolError
        err = ToolError(
            category="recoverable",
            message="Document not found",
            suggestion="Ingest it first",
        )
        content = err.to_tool_message_content()
        parsed = json.loads(content)
        assert parsed["error"] == "Document not found"
        assert parsed["error_type"] == "recoverable"
        assert parsed["suggestion"] == "Ingest it first"


@pytest.mark.unit
class TestRetryTransient:
    @pytest.mark.asyncio
    async def test_retries_on_transient_then_succeeds(self):
        from src.services.agent.error_recovery import retry_transient

        call_count = 0
        async def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise asyncio.TimeoutError()
            return {"result": "ok"}

        result = await retry_transient(flaky_fn, max_attempts=3, base_delay=0.01)
        assert result == {"result": "ok"}
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self):
        from src.services.agent.error_recovery import retry_transient

        async def always_fails():
            raise ConnectionError("down")

        with pytest.raises(ConnectionError):
            await retry_transient(always_fails, max_attempts=3, base_delay=0.01)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/services/test_agent_error_recovery.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

```python
# backend/src/services/agent/error_recovery.py
"""Structured error recovery for agent tool execution."""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

logger = logging.getLogger(__name__)

ErrorCategory = Literal["transient", "recoverable", "user_fixable", "fatal"]

# Maps (tool_name, error_keyword) -> (category, suggestion)
TOOL_ERROR_HINTS: dict[tuple[str, str], tuple[ErrorCategory, str]] = {
    ("add_document_to_project", "not found"): (
        "recoverable",
        "The document must be ingested first. Use ingest_arxiv_papers with the arXiv paper IDs.",
    ),
    ("add_document_to_project", "not a valid uuid"): (
        "recoverable",
        "Use document UUIDs from ingest_arxiv_papers, not arXiv paper IDs.",
    ),
    ("ingest_arxiv_papers", "timed out"): (
        "transient",
        "ArXiv ingestion timed out. Try fewer papers (max 3 at a time).",
    ),
    ("search_arxiv", "no results"): (
        "recoverable",
        "No results found. Try broader search terms or different keywords.",
    ),
    ("search_documents", "no results"): (
        "recoverable",
        "No matching documents found. Try different search terms or ingest new papers first.",
    ),
}

# Exception types that are always transient
_TRANSIENT_EXCEPTIONS = (asyncio.TimeoutError, asyncio.CancelledError, ConnectionError, OSError)
_USER_FIXABLE_EXCEPTIONS = (PermissionError,)


@dataclass(frozen=True)
class ToolError:
    """Structured tool error with category and actionable suggestion."""
    category: ErrorCategory
    message: str
    suggestion: str = ""

    def to_tool_message_content(self) -> str:
        payload: dict[str, Any] = {
            "error": self.message,
            "error_type": self.category,
        }
        if self.suggestion:
            payload["suggestion"] = self.suggestion
        return json.dumps(payload)

    def to_state_info(self) -> dict:
        return {
            "category": self.category,
            "message": self.message,
            "suggestion": self.suggestion,
        }


def classify_error(tool_name: str, exc: Exception) -> ToolError:
    """Classify a thrown exception into a ToolError."""
    msg = str(exc)

    if isinstance(exc, _TRANSIENT_EXCEPTIONS):
        return ToolError(category="transient", message=msg, suggestion="Retrying automatically...")

    if isinstance(exc, _USER_FIXABLE_EXCEPTIONS):
        return ToolError(category="user_fixable", message=msg, suggestion="Check your permissions or ask the user for help.")

    # Check hints by keyword
    msg_lower = msg.lower()
    for (tn, keyword), (cat, suggestion) in TOOL_ERROR_HINTS.items():
        if tn == tool_name and keyword in msg_lower:
            return ToolError(category=cat, message=msg, suggestion=suggestion)

    return ToolError(category="fatal", message=msg)


def classify_error_from_payload(tool_name: str, payload: dict) -> ToolError:
    """Classify an error from a returned payload dict."""
    error_msg = payload.get("error", "")
    msg_lower = error_msg.lower()

    # Check hints by keyword
    for (tn, keyword), (cat, suggestion) in TOOL_ERROR_HINTS.items():
        if tn == tool_name and keyword in msg_lower:
            return ToolError(category=cat, message=error_msg, suggestion=suggestion)

    # Generic payload classification
    if any(kw in msg_lower for kw in ("timeout", "timed out", "connection")):
        return ToolError(category="transient", message=error_msg)
    if any(kw in msg_lower for kw in ("not found", "does not exist", "no results", "invalid")):
        return ToolError(category="recoverable", message=error_msg, suggestion="Check the input and try again.")
    if any(kw in msg_lower for kw in ("permission", "unauthorized", "forbidden")):
        return ToolError(category="user_fixable", message=error_msg, suggestion="You may need different permissions.")

    return ToolError(category="fatal", message=error_msg)


async def retry_transient(
    fn: Callable[[], Awaitable[Any]],
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> Any:
    """Retry a coroutine on transient errors with exponential backoff."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except _TRANSIENT_EXCEPTIONS as e:
            last_exc = e
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)
                logger.info("Transient error (attempt %d/%d), retrying in %.1fs: %s", attempt + 1, max_attempts, delay, e)
                await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/services/test_agent_error_recovery.py -v`
Expected: PASS (all 9 tests)

**Step 5: Commit**

```bash
git add backend/src/services/agent/error_recovery.py backend/tests/unit/services/test_agent_error_recovery.py
git commit -m "feat(agent): add structured error recovery module with ToolError taxonomy"
```

---

### Task 3: Wire Error Recovery into Tool Execution

**Files:**

- Modify: `backend/src/services/agent/graph.py:592-665` (`_execute_single_tool`)
- Modify: `backend/src/services/agent/graph.py:668-712` (`tool_node`)

**Step 1: Write the failing test**

```python
# backend/tests/unit/services/test_agent_error_wiring.py
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.unit
class TestErrorRecoveryWiring:
    @pytest.mark.asyncio
    async def test_transient_error_retried_not_counted(self):
        """Transient errors should be retried and not increment error_count."""
        from src.services.agent.graph import _execute_single_tool

        call_count = 0
        async def mock_execute_tool(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise asyncio.TimeoutError()
            return {"status": "ok", "papers": []}

        tc = {"name": "search_arxiv", "args": {"query": "test"}, "id": "tc1"}
        config = {"configurable": {"current_user": MagicMock(id="u1"), "db": None}}

        with patch("src.api.agent.execute.execute_tool", side_effect=mock_execute_tool):
            result = await _execute_single_tool(tc, config, {})

        assert result["error_increment"] == 0  # Transient retry succeeded
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_recoverable_error_has_suggestion(self):
        """Recoverable errors should include suggestion in ToolMessage content."""
        from src.services.agent.graph import _execute_single_tool

        async def mock_execute_tool(**kwargs):
            return {"error": "Document abc123 not found"}

        tc = {"name": "add_document_to_project", "args": {"document_id": "abc123"}, "id": "tc2"}
        config = {"configurable": {"current_user": MagicMock(id="u1"), "db": None}}

        with patch("src.api.agent.execute.execute_tool", side_effect=mock_execute_tool):
            result = await _execute_single_tool(tc, config, {})

        content = json.loads(result["message"].content)
        assert content["error_type"] == "recoverable"
        assert "ingest" in content["suggestion"].lower()

    @pytest.mark.asyncio
    async def test_error_count_resets_on_success(self):
        """tool_node should reset error_count to 0 after a successful tool call."""
        from src.services.agent.graph import tool_node
        from langchain_core.messages import AIMessage

        ai_msg = AIMessage(content="", tool_calls=[{"name": "search_arxiv", "args": {"query": "test"}, "id": "tc1"}])
        state = {
            "messages": [ai_msg],
            "tool_executions": [],
            "error_count": 2,
            "last_error": "previous error",
            "page_context": {},
            "tool_loop_count": 0,
        }

        async def mock_execute_tool(**kwargs):
            return {"papers": [{"id": "1", "title": "Test Paper"}]}

        config = {"configurable": {"current_user": MagicMock(id="u1"), "db": None}}

        with patch("src.api.agent.execute.execute_tool", side_effect=mock_execute_tool):
            result = await tool_node(state, config)

        assert result["error_count"] == 0  # Reset on success
```

**Step 2: Run to verify fails**

Run: `cd backend && python -m pytest tests/unit/services/test_agent_error_wiring.py -v`
Expected: FAIL (current \_execute_single_tool doesn't retry or classify)

**Step 3: Modify `_execute_single_tool` in `graph.py:592-665`**

Replace the existing `_execute_single_tool` with version that uses `retry_transient`, `classify_error`, and `classify_error_from_payload`. Key changes:

1. Wrap `execute_tool` call in `retry_transient` for transient errors
2. After success, check if result payload has `"error"` key — if so, classify with `classify_error_from_payload`
3. Return `ToolError.to_tool_message_content()` instead of raw error JSON
4. Set `error_increment = 0` for transient errors (they were retried)

**Step 4: Modify `tool_node` in `graph.py:668-712`**

After processing all results, if any tool call succeeded (`error_increment == 0`), reset `error_count` to 0 (consecutive error counter).

**Step 5: Run tests**

Run: `cd backend && python -m pytest tests/unit/services/test_agent_error_wiring.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/services/agent/graph.py backend/tests/unit/services/test_agent_error_wiring.py
git commit -m "feat(agent): wire structured error recovery into tool execution with retry and consecutive counter"
```

---

## Phase 2: LLM Intent Classifier

### Task 4: Create Classifier Module

**Files:**

- Create: `backend/src/services/agent/classifier.py`
- Test: `backend/tests/unit/services/test_agent_classifier.py`

**Step 1: Write the failing tests**

```python
# backend/tests/unit/services/test_agent_classifier.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.unit
class TestIntentClassification:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,expected_intent", [
        ("find papers about graph neural networks", "research"),
        ("search for transformer architecture papers", "research"),
        ("extract entities from this paper", "knowledge_graph"),
        ("summarize the relationship between these papers", "writing"),
        ("create a draft literature review", "writing"),
        ("what's the weather like", "general"),
        ("help me explore entity connections in my documents", "knowledge_graph"),
        ("ingest these arxiv papers into my project", "research"),
    ])
    async def test_llm_classifier_known_intents(self, query, expected_intent):
        """LLM classifier correctly routes known confusing queries."""
        from src.services.agent.classifier import classify_intent_llm

        # Mock the LLM to return structured output
        mock_response = MagicMock()
        mock_response.intent = expected_intent
        mock_response.confidence = 0.9
        mock_response.reasoning = "test"

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = AsyncMock(
            ainvoke=AsyncMock(return_value=mock_response)
        )

        with patch("src.services.agent.classifier._build_classifier_llm", return_value=mock_llm):
            result = await classify_intent_llm(query, page_context={})

        assert result.intent == expected_intent
        assert result.confidence >= 0.0

    @pytest.mark.asyncio
    async def test_fallback_on_low_confidence(self):
        """Falls back to keyword matcher when LLM confidence < 0.7."""
        from src.services.agent.classifier import classify_intent_with_fallback

        mock_response = MagicMock()
        mock_response.intent = "general"
        mock_response.confidence = 0.4
        mock_response.reasoning = "unsure"

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = AsyncMock(
            ainvoke=AsyncMock(return_value=mock_response)
        )

        with patch("src.services.agent.classifier._build_classifier_llm", return_value=mock_llm):
            result = await classify_intent_with_fallback(
                "search arxiv for papers", page_context={}
            )

        # Keyword matcher should pick up "search" + "arxiv" -> research
        assert result.intent == "research"

    @pytest.mark.asyncio
    async def test_fallback_on_llm_failure(self):
        """Falls back to keyword matcher when LLM call fails."""
        from src.services.agent.classifier import classify_intent_with_fallback

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = AsyncMock(
            ainvoke=AsyncMock(side_effect=Exception("API error"))
        )

        with patch("src.services.agent.classifier._build_classifier_llm", return_value=mock_llm):
            result = await classify_intent_with_fallback(
                "find papers on transformers", page_context={}
            )

        assert result.intent == "research"  # Keyword fallback


@pytest.mark.unit
class TestKeywordClassifier:
    @pytest.mark.parametrize("query,expected", [
        ("search arxiv", "research"),
        ("write a draft", "writing"),
        ("extract entities", "knowledge_graph"),
        ("hello", "general"),
    ])
    def test_keyword_classifier(self, query, expected):
        from src.services.agent.classifier import classify_intent_keywords
        result = classify_intent_keywords(query)
        assert result.intent == expected
```

**Step 2: Run to verify fails**

Run: `cd backend && python -m pytest tests/unit/services/test_agent_classifier.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

```python
# backend/src/services/agent/classifier.py
"""LLM-based intent classification with keyword fallback."""

import logging
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from src.core.config import get_settings

logger = logging.getLogger(__name__)

IntentType = Literal["research", "writing", "knowledge_graph", "general"]


class IntentClassification(BaseModel):
    """Structured output from the LLM classifier."""
    intent: IntentType
    confidence: float
    reasoning: str


@dataclass(frozen=True)
class ClassificationResult:
    intent: IntentType
    confidence: float
    reasoning: str
    source: str  # "llm", "keyword", "fallback"


# --- Keyword classifier (kept as fallback) ---
# Imported from graph.py: INTENT_KEYWORDS, INTENT_PRIORITY
from src.services.agent.graph import INTENT_KEYWORDS, INTENT_PRIORITY


def classify_intent_keywords(query: str) -> ClassificationResult:
    """Keyword-weighted intent classification (existing logic, extracted)."""
    query_lower = query.lower()
    scores = {intent: 0 for intent in INTENT_KEYWORDS}
    for intent, keyword_weights in INTENT_KEYWORDS.items():
        for kw, weight in keyword_weights:
            if kw in query_lower:
                scores[intent] += weight

    best_score = max(scores.values())
    if best_score == 0:
        return ClassificationResult(intent="general", confidence=0.0, reasoning="no keywords matched", source="keyword")

    candidates = [i for i, s in scores.items() if s == best_score]
    best_intent = candidates[0]
    for preferred in INTENT_PRIORITY:
        if preferred in candidates:
            best_intent = preferred
            break

    # Normalize confidence: score / max possible for that intent
    max_possible = sum(w for _, w in INTENT_KEYWORDS.get(best_intent, []))
    confidence = min(best_score / max(max_possible, 1), 1.0)

    return ClassificationResult(
        intent=best_intent, confidence=confidence,
        reasoning=f"keyword scores: {scores}", source="keyword",
    )


# --- LLM classifier ---

CLASSIFIER_SYSTEM_PROMPT = """Classify the user's intent into one of these categories:
- research: Finding, searching, ingesting, or organizing papers and documents
- writing: Creating drafts, notes, summaries, bibliographies, or comparing documents
- knowledge_graph: Extracting entities, querying relationships, exploring the knowledge graph
- general: Anything else, including code execution, general questions, or mixed-intent

Consider the full message context, not just individual keywords.

Examples:
- "find papers about graph neural networks" -> research (not knowledge_graph — "graph" here refers to GNNs, not the knowledge graph)
- "extract entities from this paper" -> knowledge_graph
- "summarize the relationship between these papers" -> writing
- "search for transformer architecture papers and add them to my project" -> research
- "create a literature review draft" -> writing
- "what entities are connected to BERT in the knowledge graph" -> knowledge_graph
"""


def _build_classifier_llm():
    """Build a gpt-4o-mini LLM for classification (temperature=0)."""
    settings = get_settings()

    endpoint = settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT or ""
    api_key = settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY or ""

    if not endpoint or not api_key:
        raise RuntimeError("Azure/OpenAI config required for classifier LLM")

    from src.services.agent.graph import _is_openai_compatible

    if _is_openai_compatible(endpoint):
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
        api_version = settings.AZURE_OPENAI_CHAT_API_VERSION or settings.AZURE_OPENAI_API_VERSION
        return AzureChatOpenAI(
            azure_deployment="gpt-4o-mini",
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            temperature=0,
            max_tokens=256,
        )


async def classify_intent_llm(
    query: str,
    page_context: dict,
    previous_turn: str = "",
) -> ClassificationResult:
    """Classify intent using gpt-4o-mini with structured output."""
    llm = _build_classifier_llm()
    structured_llm = llm.with_structured_output(IntentClassification)

    # Build minimal context (not full thread)
    context_parts = [f"User message: {query}"]
    if previous_turn:
        context_parts.insert(0, f"Previous assistant message: {previous_turn[:200]}")
    if page_context:
        page_type = page_context.get("type", "")
        if page_type:
            context_parts.append(f"User is on: {page_type} page")

    from langchain_core.messages import SystemMessage, HumanMessage
    messages = [
        SystemMessage(content=CLASSIFIER_SYSTEM_PROMPT),
        HumanMessage(content="\n".join(context_parts)),
    ]

    result = await structured_llm.ainvoke(messages)
    return ClassificationResult(
        intent=result.intent,
        confidence=result.confidence,
        reasoning=result.reasoning,
        source="llm",
    )


async def classify_intent_with_fallback(
    query: str,
    page_context: dict,
    previous_turn: str = "",
) -> ClassificationResult:
    """Classify intent with LLM, falling back to keywords."""
    try:
        llm_result = await classify_intent_llm(query, page_context, previous_turn)
        if llm_result.confidence >= 0.7:
            return llm_result

        # Low confidence — try keyword matcher as tiebreaker
        keyword_result = classify_intent_keywords(query)
        if keyword_result.confidence > 0.3:  # keyword matcher found a strong signal
            logger.debug(
                "LLM low confidence (%.2f), keyword override: %s -> %s",
                llm_result.confidence, llm_result.intent, keyword_result.intent,
            )
            return keyword_result

        # Both ambiguous — keep LLM result or default to general
        return llm_result if llm_result.confidence > 0 else ClassificationResult(
            intent="general", confidence=0.0, reasoning="both classifiers ambiguous", source="fallback",
        )
    except Exception as e:
        logger.warning("LLM classifier failed, falling back to keywords: %s", e)
        return classify_intent_keywords(query)
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/services/test_agent_classifier.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/agent/classifier.py backend/tests/unit/services/test_agent_classifier.py
git commit -m "feat(agent): add LLM-based intent classifier with keyword fallback"
```

---

### Task 5: Wire Classifier into Graph

**Files:**

- Modify: `backend/src/services/agent/graph.py:307-339` (replace `intent_classifier_node`)

**Step 1: Modify `intent_classifier_node`**

Replace the body of `intent_classifier_node` (graph.py:308-339) to call `classify_intent_with_fallback`:

```python
@track_node_execution("intent_classifier_node")
async def intent_classifier_node(state: AgentState, config: RunnableConfig) -> dict:
    """Classify user intent using LLM with keyword fallback."""
    last_user_msg = ""
    previous_turn = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) and not last_user_msg:
            last_user_msg = msg.content
        elif isinstance(msg, AIMessage) and last_user_msg and not previous_turn:
            previous_turn = msg.content if isinstance(msg.content, str) else ""
            break

    if not last_user_msg:
        return {"intent": "general", "intent_confidence": 0.0}

    from src.services.agent.classifier import classify_intent_with_fallback
    result = await classify_intent_with_fallback(
        last_user_msg,
        page_context=state.get("page_context", {}),
        previous_turn=previous_turn,
    )
    logger.info("Intent classified: %s (confidence=%.2f, source=%s)", result.intent, result.confidence, result.source)
    return {"intent": result.intent, "intent_confidence": result.confidence}
```

**Step 2: Run existing graph tests to verify nothing breaks**

Run: `cd backend && python -m pytest tests/unit/services/test_agent_integration.py tests/unit/services/test_agent_tools.py -v`
Expected: PASS (no regressions)

**Step 3: Commit**

```bash
git add backend/src/services/agent/graph.py
git commit -m "feat(agent): wire LLM intent classifier into graph, replacing keyword-only classification"
```

---

## Phase 3: Context Compactor

### Task 6: Create Compactor Module

**Files:**

- Create: `backend/src/services/agent/compactor.py`
- Test: `backend/tests/unit/services/test_agent_compactor.py`

**Step 1: Write the failing tests**

```python
# backend/tests/unit/services/test_agent_compactor.py
import pytest
from langchain_core.messages import AIMessage, ToolMessage

@pytest.mark.unit
class TestTokenEstimation:
    def test_estimates_tokens(self):
        from src.services.agent.compactor import estimate_tool_message_tokens
        msgs = [
            ToolMessage(content="x" * 400, tool_call_id="t1"),  # ~100 tokens
            ToolMessage(content="y" * 800, tool_call_id="t2"),  # ~200 tokens
        ]
        tokens = estimate_tool_message_tokens(msgs)
        assert 250 < tokens < 350

@pytest.mark.unit
class TestIDExtraction:
    def test_extracts_uuids(self):
        from src.services.agent.compactor import extract_ids
        text = 'document_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890" and arxiv: 2301.00001'
        uuids, arxiv_ids = extract_ids(text)
        assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" in uuids
        assert "2301.00001" in arxiv_ids

    def test_empty_text_returns_empty(self):
        from src.services.agent.compactor import extract_ids
        uuids, arxiv_ids = extract_ids("")
        assert uuids == set()
        assert arxiv_ids == set()

@pytest.mark.unit
class TestShouldCompact:
    def test_below_threshold_no_compact(self):
        from src.services.agent.compactor import should_compact
        msgs = [ToolMessage(content="short", tool_call_id="t1")]
        assert should_compact(msgs, compaction_count=0, threshold=8000) is False

    def test_above_threshold_compacts(self):
        from src.services.agent.compactor import should_compact
        msgs = [ToolMessage(content="x" * 40000, tool_call_id="t1")]
        assert should_compact(msgs, compaction_count=0, threshold=8000) is True

@pytest.mark.unit
class TestCompactedMarker:
    def test_skips_already_compacted(self):
        from src.services.agent.compactor import find_compaction_candidates
        msgs = [
            AIMessage(content="use tool", tool_calls=[{"id": "old", "name": "search", "args": {}}]),
            ToolMessage(content="[Compacted] search returned 5 results", tool_call_id="old"),
            AIMessage(content="use tool", tool_calls=[{"id": "new", "name": "search", "args": {}}]),
            ToolMessage(content='{"papers": [' + "x" * 5000 + "]}",  tool_call_id="new"),
        ]
        candidates = find_compaction_candidates(msgs)
        assert len(candidates) == 0  # Only old msg is candidate, but it's already compacted

@pytest.mark.unit
class TestIDValidation:
    def test_missing_ids_appended(self):
        from src.services.agent.compactor import validate_and_fix_compacted
        original_ids = ({"uuid-1", "uuid-2"}, {"2301.00001"})
        compacted = "[Compacted] search returned results for uuid-1"
        fixed = validate_and_fix_compacted(compacted, original_ids)
        assert "uuid-2" in fixed
        assert "2301.00001" in fixed
```

**Step 2: Run to verify fails**

Run: `cd backend && python -m pytest tests/unit/services/test_agent_compactor.py -v`

**Step 3: Write implementation**

Create `backend/src/services/agent/compactor.py` implementing:

- `estimate_tool_message_tokens(messages) -> int`
- `extract_ids(text) -> tuple[set[str], set[str]]` — regex for UUIDs and arXiv IDs
- `should_compact(messages, compaction_count, threshold=8000) -> bool`
- `find_compaction_candidates(messages) -> list[ToolMessage]` — all non-`[Compacted]` ToolMessages except the most recent tool batch
- `validate_and_fix_compacted(compacted, original_ids) -> str` — append missing IDs
- `compact_messages(candidates, config) -> list[ToolMessage]` — call gpt-4o-mini to summarize, validate IDs, return replacements with same id/tool_call_id
- `make_compactor_node()` — returns a graph node function

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/services/test_agent_compactor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/agent/compactor.py backend/tests/unit/services/test_agent_compactor.py
git commit -m "feat(agent): add context compactor with token-based triggering and ID preservation"
```

---

## Phase 4: Adaptive Planner

### Task 7: Create Planner Module

**Files:**

- Create: `backend/src/services/agent/planner.py`
- Test: `backend/tests/unit/services/test_agent_planner.py`

**Step 1: Write tests**

Test that:

- `check_complexity("search for papers", tools)` returns `step_count < 3`
- `check_complexity("find papers, ingest them, add to project, and write a summary", tools)` returns `step_count >= 3`
- `generate_plan()` returns `AgentPlan` with valid steps
- Planner node skips if `state["plan"]` already populated
- Planner uses gpt-4o-mini for complexity check, gpt-4o for plan

**Step 2: Write implementation**

Create `backend/src/services/agent/planner.py`:

- `ComplexityCheck(BaseModel)` — `step_count: int`
- `PlanStep(BaseModel)` — `step, description, tool, args_hint, depends_on`
- `AgentPlan(BaseModel)` — `steps, reasoning`
- `check_complexity(query, tool_names, page_context) -> int` — gpt-4o-mini structured output
- `generate_plan(query, tool_names, page_context) -> AgentPlan` — gpt-4o structured output
- `make_planner_node(tool_names) -> node_fn` — checks `state["plan"]`, skips if populated, runs complexity check, generates plan if >= 3 steps

**Step 3: Run tests, commit**

```bash
git commit -m "feat(agent): add adaptive planner with complexity gating"
```

---

## Phase 5: Reflection Gate

### Task 8: Create Reflection Module

**Files:**

- Create: `backend/src/services/agent/reflection.py`
- Test: `backend/tests/unit/services/test_agent_reflection.py`

**Step 1: Write tests**

Test that:

- Good response passes reflection (`passed=True`)
- Bad response triggers revision (`severity="major"`, routes back)
- Max 2 rounds respected (round 3 passes regardless)
- Only fires for `research` and `writing` intents
- `general` and `knowledge_graph` skip reflection

**Step 2: Write implementation**

Create `backend/src/services/agent/reflection.py`:

- `ReflectionResult(BaseModel)` — `passed, issues, severity`
- `reflect_on_response(state, config) -> ReflectionResult` — gpt-4o-mini structured output
- `make_reflection_gate(intent_filter={"research", "writing"})` — returns a node function + routing function
- Routing: `passed` or `minor` -> proceed, `major` and `count < 2` -> loop back, else proceed

**Step 3: Run tests, commit**

```bash
git commit -m "feat(agent): add reflection gate with severity-based routing"
```

---

## Phase 6: Enhanced Subgraphs

### Task 9: Enhance Research Subgraph

**Files:**

- Modify: `backend/src/services/agent/subgraphs/research_agent.py`

**Changes:**

1. Add `interrupt_node` (import from graph.py) — route destructive tools through it
2. Add compactor node between `research_tool_node` -> `research_llm_node`
3. Add reflection gate on terminal branch (where `research_should_continue` returns END)
4. Add planner node at entry point (before first `research_llm_node`)
5. Update `research_should_continue` to route through interrupt for destructive tools

New flow:

```
planner_node? -> research_llm_node -> research_should_continue ->
  | interrupt_node -> (confirmed?) -> research_tool_node -> compactor? -> research_llm_node
  | research_tool_node -> compactor? -> research_llm_node
  | reflection_gate -> END
```

**Test:** Verify the enhanced subgraph compiles and routes correctly.

**Commit:**

```bash
git commit -m "feat(agent): enhance research subgraph with interrupt, compactor, reflection, planner"
```

---

### Task 10: Enhance Writing Subgraph

**Files:**

- Modify: `backend/src/services/agent/subgraphs/writing_agent.py`

Same pattern as Task 9 but for writing tools. Writing subgraph has no destructive tools currently except `create_draft` and `create_project_note`, which ARE in `DESTRUCTIVE_TOOLS`.

**Commit:**

```bash
git commit -m "feat(agent): enhance writing subgraph with interrupt, compactor, reflection, planner"
```

---

### Task 11: Enhance Data Subgraph

**Files:**

- Modify: `backend/src/services/agent/subgraphs/data_agent.py`

Same pattern. Data subgraph has no destructive tools (extract_entities, search_knowledge_graph are read-only), so interrupt node will be a pass-through. Reflection gate skips for `knowledge_graph` intent.

**Commit:**

```bash
git commit -m "feat(agent): enhance data subgraph with compactor (reflection skipped for KG intent)"
```

---

### Task 12: Update General Path in Main Graph

**Files:**

- Modify: `backend/src/services/agent/graph.py:852-919` (`build_agent_graph`)

**Changes:**

1. Add `planner_node` (from planner module) before `llm_node`
2. Change edge: `tool_node` -> `compactor_node` -> `llm_node` (conditional, compactor may pass through)
3. Change `should_continue`: terminal branch goes to `reflection_gate` instead of `memory_save_node`
4. Add `reflection_gate` -> conditional -> `llm_node` (revise) or `memory_save_node` (proceed)

**Test:** Run all existing agent tests + new integration test.

**Commit:**

```bash
git commit -m "feat(agent): wire planner, compactor, reflection into general path"
```

---

## Phase 7: Persistent Memory

### Task 13: Alembic Migration for agent_memories

**Files:**

- Create: `backend/alembic/versions/m8o2p3q4r5s6_create_agent_memories.py`

**Step 1: Generate migration**

Run: `cd backend && alembic revision --autogenerate -m "create_agent_memories"`

If autogenerate doesn't pick it up, manually create:

```python
def upgrade():
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.dialects.postgresql.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.dialects.postgresql.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("organization_id", sa.dialects.postgresql.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.String(50)),
        sa.Column("embedding_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True)),
        sa.Column("access_count", sa.Integer(), server_default="0"),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(), server_default="{}"),
    )
    op.create_index("idx_agent_memories_user", "agent_memories", ["user_id"])
    op.create_index("idx_agent_memories_org", "agent_memories", ["organization_id"])

def downgrade():
    op.drop_table("agent_memories")
```

**Step 2: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: Table created

**Step 3: Commit**

```bash
git commit -m "feat(agent): add agent_memories table migration"
```

---

### Task 14: Create Memory Store Module

**Files:**

- Create: `backend/src/services/agent/memory_store.py`
- Test: `backend/tests/unit/services/test_agent_memory_store.py`

**Implementation:** Replace the InMemoryStore-based `memory.py` with PostgreSQL + Qdrant:

- `save_memory(db, user_id, org_id, content, memory_type, metadata)` — insert row, embed, index in Qdrant
- `search_memories(user_id, query, limit=5)` — embed query, semantic search Qdrant, hydrate from PostgreSQL
- `update_access(memory_id)` — bump `last_accessed_at` and `access_count`
- `cleanup_stale_memories(days=90)` — soft delete old memories

**Step 1: Write tests with mocked DB and Qdrant**
**Step 2: Implement**
**Step 3: Update `memory_retrieval_node` and `memory_save_node` in graph.py to use new module**

**Commit:**

```bash
git commit -m "feat(agent): add persistent memory store with PostgreSQL + Qdrant semantic retrieval"
```

---

## Phase 8: SSE & Frontend

### Task 15: Add Plan and Reflection SSE Events

**Files:**

- Modify: `backend/src/api/agent/execute.py` (`event_generator`, around line 1770-1891)

**Changes:**

1. After detecting planner node output in `astream_events`, emit:
   ```python
   yield f"event: plan\ndata: {json.dumps({'steps': plan_steps, 'reasoning': reasoning})}\n\n"
   ```
2. After detecting reflection gate output, emit:
   ```python
   yield f"event: reflection\ndata: {json.dumps({'passed': passed, 'issues': issues, 'round': round_num})}\n\n"
   ```

**Commit:**

```bash
git commit -m "feat(agent): emit plan and reflection SSE events in event_generator"
```

---

### Task 16: Frontend Service + Store + Types

**Files:**

- Modify: `frontend/src/services/agentChatService.ts:191-213` (SSE switch)
- Modify: `frontend/src/store/agentChatStore.ts:150-273` (SSE handlers)
- Modify: `frontend/src/types/agent-chat.ts` (new types)

**Step 1: Add types**

In `agent-chat.ts`:

```typescript
export interface PlanStep {
  step: number;
  description: string;
  tool: string;
  args_hint: Record<string, unknown>;
  depends_on: number[];
}

// Add to AgentChatState:
currentPlan: PlanStep[] | null;
```

**Step 2: Add SSE cases**

In `agentChatService.ts` switch:

```typescript
case 'plan':
  callbacks.onPlan?.(data.steps, data.reasoning);
  break;
case 'reflection':
  callbacks.onReflection?.(data.passed, data.issues, data.round);
  break;
```

In `agentChatStore.ts`:

```typescript
onPlan: (steps, reasoning) => {
  set({ currentPlan: steps });
},
onDone: () => {
  // ... existing logic ...
  set({ currentPlan: null });  // Clear plan on done
},
```

**Step 3: Run type-check**

Run: `cd frontend && npm run type-check`
Expected: PASS

**Step 4: Commit**

```bash
git commit -m "feat(frontend): add plan and reflection SSE handlers and types"
```

---

### Task 17: Plan Card UI Component

**Files:**

- Create: `frontend/src/components/agent/PlanCard.tsx`
- Modify: Agent chat message area to render PlanCard when `currentPlan` is non-null

**Implementation:** Collapsible card showing plan steps. Each step displays: step number, description, tool name. Steps marked pending/active/done based on `tool_start`/`tool_end` events matching tool names.

**Commit:**

```bash
git commit -m "feat(frontend): add collapsible PlanCard component for agent workflow plans"
```

---

## Phase 9: Code Reorganization

### Task 18: Split execute.py

**Files:**

- Modify: `backend/src/api/agent/execute.py` (split into 5 files)
- Create: `backend/src/api/agent/tools_impl.py`
- Create: `backend/src/api/agent/tool_helpers.py`
- Create: `backend/src/api/agent/streaming.py`
- Create: `backend/src/api/agent/jobs.py`

**Step 1: Extract `tools_impl.py`** — Move all `_tool_*` functions and `execute_tool` dispatcher
**Step 2: Extract `tool_helpers.py`** — Move `_resolve_document_id`, `_verify_project_ownership`, etc.
**Step 3: Extract `streaming.py`** — Move `event_generator`, SSE formatting, `stream_confirm`
**Step 4: Extract `jobs.py`** — Move `_jobs` dict, TTL cleanup, `_run_agent_graph`
**Step 5: Update imports in `execute.py`** — Keep only FastAPI route definitions
**Step 6: Run all tests**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: All tests PASS (import paths unchanged via re-exports)

**Step 7: Commit**

```bash
git commit -m "refactor(agent): split execute.py into tools_impl, tool_helpers, streaming, jobs modules"
```

---

## Phase 10: Integration Testing

### Task 19: Full Graph Integration Test

**Files:**

- Create: `backend/tests/unit/services/test_agent_v2_integration.py`

**Tests:**

1. `test_full_research_flow_with_plan` — Complex query triggers plan -> tools -> reflection -> memory save
2. `test_classifier_routes_correctly` — Known confusing queries route to correct subgraph
3. `test_compactor_fires_on_long_session` — After many tool calls, compaction reduces token count
4. `test_reflection_catches_bad_response` — Bad draft triggers revision loop
5. `test_error_recovery_consecutive_reset` — Errors reset on success
6. `test_interrupt_in_subgraph` — Destructive tools in research subgraph trigger HITL
7. `test_memory_persists_across_calls` — Memory saved then retrieved in next call

**Commit:**

```bash
git commit -m "test(agent): add v2 integration tests for full enhanced graph flow"
```

---

## Task Dependency Summary

```
Phase 1 (Foundation)
  Task 1: State schema ──┐
  Task 2: Error recovery ─┤
  Task 3: Wire errors ────┘─── all subsequent phases depend on Phase 1

Phase 2 (Classifier)
  Task 4: Classifier module
  Task 5: Wire into graph

Phase 3 (Compactor)
  Task 6: Compactor module

Phase 4 (Planner)
  Task 7: Planner module

Phase 5 (Reflection)
  Task 8: Reflection module

Phase 6 (Subgraph Enhancement) ──── depends on Phases 3, 4, 5
  Task 9: Research subgraph
  Task 10: Writing subgraph
  Task 11: Data subgraph
  Task 12: General path

Phase 7 (Memory) ──── independent of Phases 2-6
  Task 13: Migration
  Task 14: Memory store

Phase 8 (SSE/Frontend) ──── depends on Phase 4 (planner) + Phase 5 (reflection)
  Task 15: Backend SSE events
  Task 16: Frontend service/store/types
  Task 17: Plan card UI

Phase 9 (Code reorg) ──── independent, can run anytime after Phase 1
  Task 18: Split execute.py

Phase 10 (Integration) ──── depends on all previous phases
  Task 19: Full integration test
```

**Parallelizable:** Phases 2, 3, 4, 5, 7, 9 can all run in parallel after Phase 1 completes. Phase 6 blocks on 3+4+5. Phase 8 blocks on 4+5. Phase 10 is the final gate.
