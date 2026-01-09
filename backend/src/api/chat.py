"""
Chat API endpoints for conversational AI
Provides chat completion functionality using Azure OpenAI with optional RAG
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..core.dependencies import get_current_user, require_admin
from ..models.user import User, UserRole
from typing import List, Optional, Dict, Any
import logging
import json
import re
from datetime import datetime, timezone

from ..services.azure_openai_service import azure_openai_service
from ..services.hybrid_search_service import hybrid_search_service
from ..services.llm_response_cache import llm_response_cache
from ..utils.logging import truncate_for_logging
from ..models.search_schemas import SearchQuery  # Pydantic schema, not SQLAlchemy model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """A single chat message"""
    role: str = Field(..., description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message content")


class RetrievedContext(BaseModel):
    """Retrieved document context"""
    document_id: str
    title: str
    content: str
    score: float
    source: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """Request for chat completion"""
    messages: List[ChatMessage] = Field(..., description="Conversation history")
    model: str = Field(default="gpt-4o-mini", description="Model to use")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=2048, ge=1, le=8192, description="Maximum tokens to generate")
    system_prompt: Optional[str] = Field(
        default="You are an advanced AI assistant. Provide precise, well-structured responses.",
        description="System prompt to use"
    )
    # RAG settings
    use_rag: bool = Field(default=False, description="Enable RAG to retrieve context from indexed documents")
    max_context_docs: int = Field(default=5, ge=1, le=10, description="Maximum documents to retrieve for context")


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


RAG_SYSTEM_PROMPT = """You are an AI research assistant with access to a knowledge base of academic papers and documents. 
When answering questions, use the provided context from retrieved documents to give accurate, well-cited responses.

IMPORTANT CITATION RULES:
1. When referencing information from a document, ALWAYS cite it using the format [Doc N] where N is the document number (1, 2, 3, etc.)
2. Include the paper title when first citing a document, e.g., "According to 'Paper Title' [Doc 1]..."
3. Use citations inline with your statements, not at the end
4. If multiple documents support a point, cite all of them, e.g., [Doc 1, Doc 3]

If the context doesn't contain relevant information to answer the question, say so clearly and provide your best general knowledge response.

Always be precise, structure your responses clearly, and ensure every factual claim from the papers is properly cited."""


async def retrieve_context(query: str, max_docs: int = 5) -> List[RetrievedContext]:
    """Retrieve relevant context from indexed documents using hybrid search"""
    try:
        search_request = SearchQuery(
            query=query,
            limit=max_docs,
            search_type="hybrid"
        )
        
        # Execute hybrid search (sync method, run in thread pool)
        import asyncio
        loop = asyncio.get_event_loop()
        search_response = await loop.run_in_executor(
            None,
            lambda: hybrid_search_service.search(
                search_request=search_request,
                user_id=None,
                organization_id=None
            )
        )
        
        logger.info(f"Hybrid search returned {len(search_response.results)} results")
        
        contexts = []
        for result in search_response.results[:max_docs]:
            # Extract fields from SearchResult object
            # Note: API returns document_id, content_preview/content_snippet, not id/content
            doc_id = getattr(result, 'document_id', 'unknown')
            title = getattr(result, 'title', 'Untitled')
            
            # Get metadata - it often contains the full text
            metadata = getattr(result, 'metadata', {}) or {}
            
            # Try to get full content from metadata.text first (contains full chunk)
            content = metadata.get('text', '')
            
            # Fallback to content_preview or content_snippet
            if not content:
                content = getattr(result, 'content_preview', None)
            if not content:
                content = getattr(result, 'content_snippet', None)
            if not content:
                content = getattr(result, 'content', '')
            
            # Ensure content is a string
            if content is None:
                content = ""
            
            # Get title from metadata if not in main object
            if not title or title == 'Untitled':
                additional_data = metadata.get('additional_data', {}) or metadata.get('metadata', {}) or {}
                title = additional_data.get('title', metadata.get('title', 'Untitled'))
            
            # Limit content length to fit in context window
            if len(content) > 3000:
                content = content[:3000] + "..."
            
            score = getattr(result, 'relevance_score', 0.0)
            
            # Get source info from metadata
            metadata = getattr(result, 'metadata', {}) or {}
            source = metadata.get('source_type') or metadata.get('source', 'unknown')
            
            contexts.append(RetrievedContext(
                document_id=str(doc_id),
                title=title,
                content=content,
                score=float(score),
                source=source
            ))
            
            logger.debug(f"Retrieved context: {doc_id} - {title[:30]}... (score: {score:.3f})")
        
        return contexts
        
    except Exception as e:
        logger.warning(f"Failed to retrieve context: {str(e)}", exc_info=True)
        return []


def build_context_prompt(contexts: List[RetrievedContext]) -> str:
    """Build a context prompt from retrieved documents"""
    if not contexts:
        return ""
    
    context_parts = ["Here are relevant documents from the knowledge base. Use [Doc N] format to cite them:\n"]
    
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
    request: ChatCompletionRequest
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
                detail="Azure OpenAI chat service is not available. Please check configuration."
            )
        
        retrieved_contexts = []
        
        # Get the last user message for caching and RAG
        user_messages = [m for m in request.messages if m.role == "user"]
        last_query = user_messages[-1].content if user_messages else ""
        
        # If RAG is enabled, retrieve context based on the last user message
        if request.use_rag:
            if last_query:
                retrieved_contexts = await retrieve_context(last_query, request.max_context_docs)
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
        
        logger.info(f"Chat completion request with {len(messages)} messages, RAG={'enabled' if request.use_rag else 'disabled'}")
        
        # Generate cache key based on the full conversation context
        # For RAG queries, include context document IDs in cache consideration
        cache_query = last_query
        if request.use_rag and retrieved_contexts:
            # Include context doc IDs to differentiate responses with different context
            context_ids = "|".join(sorted([c.document_id for c in retrieved_contexts]))
            cache_query = f"{last_query}||ctx:{context_ids}"
        
        # Check LLM response cache (only for single-turn or last message caching)
        # Skip cache for high-temperature (more creative) requests
        use_cache = request.temperature <= 1.0 and len(request.messages) <= 5
        cached_response = None
        
        if use_cache:
            cached_response = await llm_response_cache.get(
                query=cache_query,
                model=request.model,
                temperature=request.temperature,
                use_semantic=not request.use_rag  # Disable semantic for RAG (context-dependent)
            )
        
        if cached_response:
            logger.info(f"LLM cache hit ({cached_response.get('cache_type', 'unknown')})")

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
                    role="assistant",
                    content=cached_response["content"]
                ),
                model=cached_response.get("model", request.model),
                usage=cached_response.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
                finish_reason="stop",
                timestamp=datetime.now(timezone.utc).isoformat(),
                rag_enabled=request.use_rag,
                retrieved_contexts=cached_contexts if request.use_rag else None
            )
        
        # Get completion from Azure OpenAI
        response = await azure_openai_service.chat_completion(
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False
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
                    "context_count": len(retrieved_contexts) if retrieved_contexts else 0,
                },
                retrieved_contexts=contexts_for_cache,
            )
        
        # Build response
        return ChatCompletionResponse(
            message=ChatMessage(
                role="assistant",
                content=response["content"]
            ),
            model=response.get("model", request.model),
            usage=response.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
            finish_reason=response.get("finish_reason", "stop"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            rag_enabled=request.use_rag,
            retrieved_contexts=retrieved_contexts if request.use_rag else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chat completion: {str(e)}"
        )


@router.get("/health")
async def chat_health_check():
    """
    Health check for chat service.
    """
    return {
        "status": "healthy" if azure_openai_service.is_chat_available() else "unavailable",
        "chat_available": azure_openai_service.is_chat_available(),
        "model_info": azure_openai_service.get_model_info(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/models")
async def list_available_models():
    """
    List available chat models.
    """
    models = []
    
    if azure_openai_service.is_chat_available():
        deployment = azure_openai_service.get_chat_deployment()
        models.append({
            "id": "gpt-4o-mini",
            "name": "GPT-4O Mini",
            "provider": "azure_openai",
            "deployment": deployment,
            "description": "OpenAI flagship mini model with superior reasoning capabilities",
            "available": True,
            "supports_rag": True
        })
    
    return {
        "models": models,
        "count": len(models)
    }


class SuggestionsRequest(BaseModel):
    """Request for follow-up suggestions"""
    messages: List[ChatMessage] = Field(..., description="Recent conversation history")
    citations: List[RetrievedContext] = Field(default=[], description="Retrieved contexts")
    count: int = Field(default=3, ge=1, le=5, description="Number of suggestions to generate")


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
    request: SuggestionsRequest,
    current_user: User = Depends(get_current_user)
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
        conversation_text = "\n".join([
            f"{msg.role}: {msg.content[:500]}" for msg in request.messages[-3:]
        ])

        # Build document context
        doc_text = ""
        if request.citations:
            doc_text = "\n".join([
                f"- {ctx.title}: {ctx.content[:200]}..." if ctx.content else f"- {ctx.title}"
                for ctx in request.citations[:3]
            ])
        else:
            doc_text = "No documents retrieved."

        # Build the prompt
        prompt = SUGGESTIONS_PROMPT.format(
            count=request.count,
            conversation=conversation_text,
            documents=doc_text
        )

        # Get suggestions from LLM
        response = await azure_openai_service.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates follow-up questions. Always respond with a valid JSON array."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300,
            stream=False
        )

        # Parse the response
        content = response.get("content", "[]")

        # Try to extract JSON array from response
        try:
            # Handle potential markdown code blocks
            if "```" in content:
                # Try to extract JSON from explicit code blocks first
                code_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
                if code_match:
                    content = code_match.group(1).strip()

            # Find the outermost array brackets using depth counting
            # This handles nested arrays correctly (e.g., ["Question [1]?", "Question 2?"])
            start = content.find('[')
            if start != -1:
                depth = 0
                for i, c in enumerate(content[start:], start):
                    if c == '[':
                        depth += 1
                    elif c == ']':
                        depth -= 1
                        if depth == 0:
                            content = content[start:i+1]
                            break

            suggestions = json.loads(content)
            if isinstance(suggestions, list):
                # Ensure we return strings and limit to requested count
                suggestions = [str(s).strip() for s in suggestions[:request.count] if s]
                return SuggestionsResponse(suggestions=suggestions)
        except json.JSONDecodeError:
            logger.warning(
                f"Failed to parse suggestions JSON: {truncate_for_logging(content)}",
                extra={"raw_content_length": len(content)}
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
    }
)
async def get_cache_stats(
    current_user: User = Depends(get_current_user)
):
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
            "is_admin": current_user.has_permission(UserRole.ADMIN)
        }
    )

    return {
        "status": "healthy",
        "cache_stats": sanitized_stats,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.post(
    "/cache/clear",
    summary="Clear LLM cache",
    description="Clears all cached LLM responses. **Requires ADMIN role.** This is a destructive operation.",
    responses={
        200: {"description": "Cache cleared successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions (requires ADMIN role)"},
    }
)
async def clear_cache(
    current_user: User = Depends(require_admin)
):
    """
    Clear the LLM response cache.

    **Requires ADMIN role.** This is a destructive operation that affects
    system performance by removing all cached LLM responses.
    """
    logger.warning(
        "Cache clear initiated",
        extra={
            "user_id": str(current_user.id),
            "admin_action": True
        }
    )

    cleared_count = await llm_response_cache.clear()

    logger.info(
        "Cache cleared successfully",
        extra={
            "cleared_entries": cleared_count,
            "user_id": str(current_user.id)
        }
    )

    return {
        "status": "success",
        "cleared_entries": cleared_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
