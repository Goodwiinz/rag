"""
Chat API endpoints for conversational AI
Provides chat completion functionality using Azure OpenAI with optional RAG
"""

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from src.core.dependencies import get_current_user, require_admin
from src.models.search_schemas import (
    SearchQuery,  # Pydantic schema, not SQLAlchemy model
)
from src.models.user import User, UserRole
from src.services.infrastructure.azure_openai_service import azure_openai_service
from src.services.infrastructure.llm_response_cache import llm_response_cache
from src.services.search.hybrid_search_service import hybrid_search_service
from src.utils.logging import truncate_for_logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """A single chat message"""

    role: str = Field(..., description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message content")


class RetrievedContext(BaseModel):
    """Retrieved document context"""

    document_id: Optional[str] = None
    title: str
    content: str
    score: float
    source: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """Request for chat completion"""

    messages: List[ChatMessage] = Field(..., description="Conversation history")
    model: str = Field(default="gpt-4o", description="Model to use")
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Sampling temperature"
    )
    max_tokens: Optional[int] = Field(
        default=2048, ge=1, le=8192, description="Maximum tokens to generate"
    )
    system_prompt: Optional[str] = Field(
        default="You are an advanced AI assistant. Provide precise, well-structured responses.",
        description="System prompt to use",
    )
    # RAG settings
    use_rag: bool = Field(
        default=True,
        description="Enable RAG to retrieve context from indexed documents",
    )
    max_context_docs: int = Field(
        default=5, ge=1, le=10, description="Maximum documents to retrieve for context"
    )


class ChatCompletionResponse(BaseModel):
    """Response from chat completion"""

    message: ChatMessage
    model: str
    usage: Dict[str, int]
    finish_reason: str
    timestamp: str
    # RAG info
    rag_enabled: bool = False
    retrieved_contexts: Optional[List[RetrievedContext]] = None
    diagnostics_trace_id: Optional[str] = None


RAG_SYSTEM_PROMPT = """You are an AI research assistant with access to a knowledge base of academic papers and documents.
When answering questions, use the provided context from retrieved documents to give accurate, well-cited responses.

CRITICAL CITATION REQUIREMENTS - YOU MUST FOLLOW THESE EXACTLY:
1. ALWAYS use the EXACT format [Doc 1], [Doc 2], [Doc 3] etc. - NOT [1] or (1) or any other format
2. Cite EVERY document that provides relevant information - if 5 documents are provided and all are relevant, cite all 5
3. Place citations INLINE immediately after the statement they support, e.g., "RAG improves accuracy [Doc 1] by combining retrieval with generation [Doc 2]."
4. When multiple documents support a point, cite ALL of them: [Doc 1, Doc 2, Doc 3]
5. Each paragraph should typically have 2-4 citations if the documents are relevant

Example of CORRECT citation format:
"Retrieval-Augmented Generation (RAG) enhances LLM performance [Doc 1] by integrating external knowledge [Doc 2]. This approach is particularly effective for domain-specific tasks [Doc 3, Doc 4]."

Example of INCORRECT format (DO NOT USE):
"RAG is useful [1]." ← Wrong! Must be [Doc 1]

If the context doesn't contain relevant information, say so clearly.
Always be precise and ensure EVERY factual claim is properly cited using [Doc N] format."""


async def retrieve_context(
    query: str, max_docs: int = 5
) -> tuple[List[RetrievedContext], Optional[str]]:
    """
    Retrieve relevant context from indexed documents using hybrid search.

    Returns:
        Tuple of (contexts, diagnostics_trace_id).
        diagnostics_trace_id is None if diagnostics storage fails.
    """
    try:
        search_request = SearchQuery(query=query, limit=max_docs, search_type="hybrid")

        # Execute hybrid search with diagnostics (sync method, run in thread pool)
        import asyncio

        loop = asyncio.get_event_loop()
        search_response, trace = await loop.run_in_executor(
            None,
            lambda: hybrid_search_service.search_with_diagnostics(
                search_request=search_request, user_id=None, organization_id=None
            ),
        )

        logger.info(f"Hybrid search returned {len(search_response.results)} results")

        contexts = []
        total_chars_before = 0
        total_chars_after = 0
        truncated_docs = []

        for result in search_response.results[:max_docs]:
            doc_id = getattr(result, "document_id", None)
            title = getattr(result, "title", "Untitled")

            metadata = getattr(result, "metadata", {}) or {}
            # Prefer full chunk text when available; preview fields are fallbacks only.
            content = metadata.get("full_text") or metadata.get("text", "")

            if not content:
                content = getattr(result, "content_preview", None)
            if not content:
                content = getattr(result, "content_snippet", None)
            if not content:
                content = getattr(result, "content", "")

            if content is None:
                content = ""

            if not title or title == "Untitled":
                additional_data = (
                    metadata.get("additional_data", {})
                    or metadata.get("metadata", {})
                    or {}
                )
                title = additional_data.get("title", metadata.get("title", "Untitled"))

            # Track truncation for diagnostics
            original_len = len(content)
            total_chars_before += original_len

            if original_len > 3000:
                content = content[:3000] + "..."
                truncated_docs.append(
                    {"doc_id": str(doc_id), "before": original_len, "after": 3000}
                )

            total_chars_after += len(content)

            score = getattr(result, "relevance_score", 0.0)

            metadata = getattr(result, "metadata", {}) or {}
            source = metadata.get("source_type") or metadata.get("source", "unknown")

            contexts.append(
                RetrievedContext(
                    document_id=str(doc_id) if doc_id else None,
                    title=title,
                    content=content,
                    score=float(score),
                    source=source,
                )
            )

            logger.debug(
                f"Retrieved context: {doc_id} - {title[:30]}... (score: {score:.3f})"
            )

        # Populate context diagnostics on the trace
        from src.services.diagnostics.retrieval_diagnostics import ContextDiagnostics

        trace.context = ContextDiagnostics(
            docs_retrieved=len(search_response.results),
            docs_with_content=sum(1 for c in contexts if c.content),
            total_chars_before_truncation=total_chars_before,
            total_chars_after_truncation=total_chars_after,
            truncated_docs=truncated_docs,
            truncation_ratio=round(
                (total_chars_before - total_chars_after) / total_chars_before, 4
            )
            if total_chars_before > 0
            else 0.0,
        )

        # Store the trace
        trace_id = trace.trace_id
        try:
            from src.services.diagnostics.diagnostics_store import diagnostics_store

            await diagnostics_store.store_trace(trace)
        except Exception as store_err:
            logger.warning(f"Failed to store diagnostics trace: {store_err}")
            trace_id = None

        return contexts, trace_id

    except Exception as e:
        logger.warning(f"Failed to retrieve context: {str(e)}", exc_info=True)
        return [], None


async def _background_evaluate_rag(
    query: str,
    answer: str,
    contexts: List[RetrievedContext],
    trace_id: str,
) -> None:
    """Background task: evaluate RAG response quality and link to diagnostics trace."""
    try:
        from src.services.diagnostics.diagnostics_store import diagnostics_store
        from src.services.evaluation.rag_evaluation_service import (
            RAGEvaluationInput,
            rag_evaluation_service,
        )

        evaluation_input = RAGEvaluationInput(
            query=query,
            generated_answer=answer,
            retrieved_context=[ctx.content for ctx in contexts],
            document_ids=[ctx.document_id for ctx in contexts],
            search_type="hybrid",
            metadata={"trace_id": trace_id, "context_count": len(contexts)},
        )

        from src.core.database import get_db_sync

        db = next(get_db_sync())
        try:
            metrics = await rag_evaluation_service.run_rag_triad_evaluation(
                evaluation_input, None, None, db
            )
            scores = {
                "answer_relevancy": metrics.answer_relevancy,
                "faithfulness": metrics.faithfulness,
                "contextual_relevancy": metrics.contextual_relevancy,
                "overall_score": metrics.overall_score,
                "hallucination_rate": metrics.hallucination_rate,
            }
            await diagnostics_store.update_trace_evaluation(
                trace_id, evaluation_id=f"eval-{trace_id}", scores=scores
            )
            logger.info(
                f"Background RAG evaluation completed for trace {trace_id}: "
                f"overall={metrics.overall_score:.3f}"
            )
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Background RAG evaluation failed for trace {trace_id}: {e}")


def build_context_prompt(contexts: List[RetrievedContext]) -> str:
    """Build a context prompt from retrieved documents"""
    if not contexts:
        return ""

    context_parts = [
        "Here are relevant documents from the knowledge base. Use [Doc N] format to cite them:\n"
    ]

    for i, ctx in enumerate(contexts, 1):
        context_parts.append(f"\n=== [Doc {i}] ===")
        context_parts.append(f"Title: {ctx.title}")
        context_parts.append(f"ArXiv ID: {ctx.document_id}")
        context_parts.append(f"Relevance Score: {ctx.score:.2f}")
        if ctx.source:
            context_parts.append(f"Source: {ctx.source}")
        context_parts.append(f"\nContent:\n{ctx.content}")

    context_parts.append("\n\n=== End of Retrieved Documents ===")
    context_parts.append("Remember to cite sources using [Doc N] format!")
    return "\n".join(context_parts)


@router.post("/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest, background_tasks: BackgroundTasks
):
    """
    Get chat completion from Azure OpenAI.

    Supports multi-turn conversations by accepting full message history.
    Optionally enables RAG to retrieve context from indexed documents.
    Uses semantic caching to reduce API costs for similar queries.
    """
    try:
        # Check if Azure OpenAI chat is available
        if not azure_openai_service.is_chat_available():
            raise HTTPException(
                status_code=503,
                detail="Azure OpenAI chat service is not available. Please check configuration.",
            )

        retrieved_contexts = []
        diagnostics_trace_id = None

        # Get the last user message for caching and RAG
        user_messages = [m for m in request.messages if m.role == "user"]
        last_query = user_messages[-1].content if user_messages else ""

        # If RAG is enabled, retrieve context based on the last user message
        if request.use_rag:
            if last_query:
                retrieved_contexts, diagnostics_trace_id = await retrieve_context(
                    last_query, request.max_context_docs
                )
                logger.info(f"Retrieved {len(retrieved_contexts)} documents for RAG")

        # Build messages list
        messages = []

        # Add system prompt
        if request.use_rag:
            # Use RAG-specific system prompt with context
            system_content = RAG_SYSTEM_PROMPT
            if retrieved_contexts:
                context_prompt = build_context_prompt(retrieved_contexts)
                system_content = f"{RAG_SYSTEM_PROMPT}\n\n{context_prompt}"
            messages.append({"role": "system", "content": system_content})
        elif request.system_prompt:
            has_system = any(m.role == "system" for m in request.messages)
            if not has_system:
                messages.append({"role": "system", "content": request.system_prompt})

        # Add conversation history
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})

        logger.info(
            f"Chat completion request with {len(messages)} messages, RAG={'enabled' if request.use_rag else 'disabled'}"
        )

        # Generate cache key based on the full conversation context
        # Include conversation history to differentiate identical queries in different contexts
        # Use last 3 messages (excluding current query) to capture conversation context
        context_messages = []
        if len(request.messages) > 1:
            # Get previous messages for context (up to 3, excluding current query)
            prev_messages = request.messages[:-1][-3:]
            context_messages = [f"{m.role}:{m.content[:100]}" for m in prev_messages]

        conversation_context_hash = ""
        if context_messages:
            context_str = "||".join(context_messages)
            conversation_context_hash = hashlib.sha256(
                context_str.encode()
            ).hexdigest()[:16]

        cache_query = last_query
        if conversation_context_hash:
            cache_query = f"{last_query}||conv:{conversation_context_hash}"

        if request.use_rag and retrieved_contexts:
            # Include context doc IDs to differentiate responses with different context
            context_ids = "|".join(sorted([c.document_id for c in retrieved_contexts]))
            cache_query = f"{cache_query}||ctx:{context_ids}"

        # Check LLM response cache (only for single-turn or last message caching)
        # Skip cache for high-temperature (more creative) requests
        use_cache = request.temperature <= 1.0 and len(request.messages) <= 5
        cached_response = None

        if use_cache:
            cached_response = await llm_response_cache.get(
                query=cache_query,
                model=request.model,
                temperature=request.temperature,
                use_semantic=not request.use_rag,  # Disable semantic for RAG (context-dependent)
            )

        if cached_response:
            logger.info(
                f"LLM cache hit ({cached_response.get('cache_type', 'unknown')})"
            )

            # For RAG responses, use the cached contexts that were used to generate the response
            # This ensures consistency between the response content (with citations) and contexts
            cached_contexts = None
            if request.use_rag:
                cached_context_dicts = cached_response.get("retrieved_contexts")
                if cached_context_dicts:
                    # Reconstruct RetrievedContext objects from cached dicts
                    cached_contexts = [
                        RetrievedContext(
                            document_id=ctx.get("document_id", "unknown"),
                            title=ctx.get("title", "Untitled"),
                            content=ctx.get("content", ""),
                            score=ctx.get("score", 0.0),
                            source=ctx.get("source"),
                        )
                        for ctx in cached_context_dicts
                    ]
                else:
                    # Fallback: no cached contexts available (legacy cache entries)
                    # Use freshly retrieved contexts but log a warning
                    logger.warning(
                        "Cache hit for RAG response but no cached contexts found. "
                        "Using fresh contexts which may not match response citations."
                    )
                    cached_contexts = retrieved_contexts

            return ChatCompletionResponse(
                message=ChatMessage(
                    role="assistant", content=cached_response["content"]
                ),
                model=cached_response.get("model", request.model),
                usage=cached_response.get(
                    "usage",
                    {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                ),
                finish_reason="stop",
                timestamp=datetime.now(timezone.utc).isoformat(),
                rag_enabled=request.use_rag,
                retrieved_contexts=cached_contexts if request.use_rag else None,
                diagnostics_trace_id=diagnostics_trace_id,
            )

        # Get completion from Azure OpenAI
        response = await azure_openai_service.chat_completion(
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,
        )

        # Cache the response for future similar queries
        if use_cache and response.get("content"):
            # Convert RetrievedContext objects to dicts for serialization
            contexts_for_cache = None
            if retrieved_contexts:
                contexts_for_cache = [
                    {
                        "document_id": ctx.document_id,
                        "title": ctx.title,
                        "content": ctx.content,
                        "score": ctx.score,
                        "source": ctx.source,
                    }
                    for ctx in retrieved_contexts
                ]

            await llm_response_cache.set(
                query=cache_query,
                response_content=response["content"],
                model=response.get("model", request.model),
                temperature=request.temperature,
                usage=response.get("usage"),
                metadata={
                    "rag_enabled": request.use_rag,
                    "context_count": len(retrieved_contexts)
                    if retrieved_contexts
                    else 0,
                },
                retrieved_contexts=contexts_for_cache,
            )

        # Trigger background RAG evaluation if RAG was used
        if request.use_rag and diagnostics_trace_id and retrieved_contexts:
            background_tasks.add_task(
                _background_evaluate_rag,
                query=last_query,
                answer=response["content"],
                contexts=retrieved_contexts,
                trace_id=diagnostics_trace_id,
            )

        # Build response
        return ChatCompletionResponse(
            message=ChatMessage(role="assistant", content=response["content"]),
            model=response.get("model", request.model),
            usage=response.get(
                "usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            ),
            finish_reason=response.get("finish_reason", "stop"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            rag_enabled=request.use_rag,
            retrieved_contexts=retrieved_contexts if request.use_rag else None,
            diagnostics_trace_id=diagnostics_trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get chat completion: {str(e)}"
        )


@router.get("/health")
async def chat_health_check():
    """
    Health check for chat service.
    """
    return {
        "status": "healthy"
        if azure_openai_service.is_chat_available()
        else "unavailable",
        "chat_available": azure_openai_service.is_chat_available(),
        "model_info": azure_openai_service.get_model_info(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/models")
async def list_available_models():
    """
    List available chat models.
    """
    models = []

    if azure_openai_service.is_chat_available():
        deployment = azure_openai_service.get_chat_deployment()
        models.append(
            {
                "id": "gpt-4o",
                "name": "GPT-4O",
                "provider": "azure_openai",
                "deployment": deployment,
                "description": "OpenAI flagship model with superior reasoning and multimodal capabilities",
                "available": True,
                "supports_rag": True,
            }
        )

    return {"models": models, "count": len(models)}


class SuggestionsRequest(BaseModel):
    """Request for follow-up suggestions"""

    messages: List[ChatMessage] = Field(..., description="Recent conversation history")
    citations: List[RetrievedContext] = Field(
        default=[], description="Retrieved contexts"
    )
    count: int = Field(
        default=3, ge=1, le=5, description="Number of suggestions to generate"
    )


class SuggestionsResponse(BaseModel):
    """Response with follow-up suggestions"""

    suggestions: List[str]


SUGGESTIONS_PROMPT = """Based on the conversation and retrieved documents below, generate {count} concise follow-up questions the user might want to ask.

Questions should:
- Be specific to the topic discussed
- Explore deeper aspects of the documents
- Be actionable and 10-15 words max each
- Not repeat what was already discussed

Conversation:
{conversation}

Retrieved Documents:
{documents}

Return ONLY a JSON array of {count} question strings, no explanation. Example format:
["Question 1?", "Question 2?", "Question 3?"]"""


@router.post("/suggestions", response_model=SuggestionsResponse)
async def generate_suggestions(
    request: SuggestionsRequest, current_user: User = Depends(get_current_user)
):
    """
    Generate AI-powered follow-up question suggestions based on conversation context.

    Uses the conversation history and retrieved documents to generate relevant
    follow-up questions the user might want to ask.
    Requires authentication to prevent unauthorized LLM API consumption.
    """
    try:
        if not azure_openai_service.is_chat_available():
            return SuggestionsResponse(suggestions=[])

        # Build conversation context
        conversation_text = "\n".join(
            [f"{msg.role}: {msg.content[:500]}" for msg in request.messages[-3:]]
        )

        # Build document context
        doc_text = ""
        if request.citations:
            doc_text = "\n".join(
                [
                    f"- {ctx.title}: {ctx.content[:200]}..."
                    if ctx.content
                    else f"- {ctx.title}"
                    for ctx in request.citations[:3]
                ]
            )
        else:
            doc_text = "No documents retrieved."

        # Build the prompt
        prompt = SUGGESTIONS_PROMPT.format(
            count=request.count, conversation=conversation_text, documents=doc_text
        )

        # Get suggestions from LLM
        response = await azure_openai_service.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates follow-up questions. Always respond with a valid JSON array.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=300,
            stream=False,
        )

        # Parse the response
        content = response.get("content", "[]")

        # Try to extract JSON array from response
        try:
            # Handle potential markdown code blocks
            if "```" in content:
                # Try to extract JSON from explicit code blocks first
                code_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
                if code_match:
                    content = code_match.group(1).strip()

            # Find the outermost array brackets using depth counting
            # This handles nested arrays correctly (e.g., ["Question [1]?", "Question 2?"])
            start = content.find("[")
            if start != -1:
                depth = 0
                for i, c in enumerate(content[start:], start):
                    if c == "[":
                        depth += 1
                    elif c == "]":
                        depth -= 1
                        if depth == 0:
                            content = content[start : i + 1]
                            break

            suggestions = json.loads(content)
            if isinstance(suggestions, list):
                # Ensure we return strings and limit to requested count
                suggestions = [
                    str(s).strip() for s in suggestions[: request.count] if s
                ]
                return SuggestionsResponse(suggestions=suggestions)
        except json.JSONDecodeError:
            logger.warning(
                f"Failed to parse suggestions JSON: {truncate_for_logging(content)}",
                extra={"raw_content_length": len(content)},
            )

        return SuggestionsResponse(suggestions=[])

    except Exception as e:
        logger.error(f"Suggestions generation error: {str(e)}")
        return SuggestionsResponse(suggestions=[])


@router.get(
    "/cache/stats",
    summary="Get LLM cache statistics",
    description="Returns cache hit/miss rates and entry counts. Requires authentication.",
    responses={
        200: {"description": "Cache statistics retrieved successfully"},
        401: {"description": "Not authenticated"},
    },
)
async def get_cache_stats(current_user: User = Depends(get_current_user)):
    """
    Get LLM response cache statistics.

    Requires authentication. Returns sanitized cache metrics.
    Only admins see full configuration details.
    """
    raw_stats = llm_response_cache.get_stats()

    # Filter sensitive configuration details for non-admins
    sanitized_stats = {
        "hit_count": raw_stats.get("hit_count", 0),
        "miss_count": raw_stats.get("miss_count", 0),
        "hit_rate_percent": raw_stats.get("hit_rate_percent", 0.0),
        "total_entries": raw_stats.get("total_entries", 0),
        "memory_entries": raw_stats.get("memory_entries", 0),
        "redis_entries": raw_stats.get("redis_entries", 0),
    }

    # Only admins see full config
    if current_user.has_permission(UserRole.ADMIN):
        sanitized_stats["config"] = raw_stats.get("config", {})

    logger.info(
        "Cache stats accessed",
        extra={
            "user_id": str(current_user.id),
            "is_admin": current_user.has_permission(UserRole.ADMIN),
        },
    )

    return {
        "status": "healthy",
        "cache_stats": sanitized_stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post(
    "/cache/clear",
    summary="Clear LLM cache",
    description="Clears all cached LLM responses. **Requires ADMIN role.** This is a destructive operation.",
    responses={
        200: {"description": "Cache cleared successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions (requires ADMIN role)"},
    },
)
async def clear_cache(current_user: User = Depends(require_admin)):
    """
    Clear the LLM response cache.

    **Requires ADMIN role.** This is a destructive operation that affects
    system performance by removing all cached LLM responses.
    """
    logger.warning(
        "Cache clear initiated",
        extra={"user_id": str(current_user.id), "admin_action": True},
    )

    cleared_count = await llm_response_cache.clear()

    logger.info(
        "Cache cleared successfully",
        extra={"cleared_entries": cleared_count, "user_id": str(current_user.id)},
    )

    return {
        "status": "success",
        "cleared_entries": cleared_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
