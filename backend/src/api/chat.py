"""
Chat API endpoints for conversational AI
Provides chat completion functionality using Azure OpenAI with optional RAG
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from ..services.azure_openai_service import azure_openai_service
from ..services.hybrid_search_service import hybrid_search_service
from ..models.search import SearchQuery

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

If the context doesn't contain relevant information to answer the question, say so clearly and provide your best general knowledge response.

Always be precise, cite specific papers or documents when relevant, and structure your responses clearly."""


async def retrieve_context(query: str, max_docs: int = 5) -> List[RetrievedContext]:
    """Retrieve relevant context from indexed documents using hybrid search"""
    try:
        search_request = SearchQuery(
            query=query,
            limit=max_docs,
            search_type="hybrid"
        )
        
        # Execute hybrid search
        search_response = await hybrid_search_service.search(
            search_request=search_request,
            user_id=None,
            organization_id=None
        )
        
        logger.info(f"Hybrid search returned {len(search_response.results)} results")
        
        contexts = []
        for result in search_response.results[:max_docs]:
            # Extract fields from SearchResult object
            # Note: API returns document_id, content_preview/content_snippet, not id/content
            doc_id = getattr(result, 'document_id', 'unknown')
            title = getattr(result, 'title', 'Untitled')
            
            # Prefer content_preview or content_snippet
            content = getattr(result, 'content_preview', None)
            if not content:
                content = getattr(result, 'content_snippet', None)
            
            # Fallback to content if others are missing, but this is likely empty
            if not content:
                content = getattr(result, 'content', '')
            
            # Ensure content is a string
            if content is None:
                content = ""
            
            # Limit content length to fit in context window
            if len(content) > 2000:
                content = content[:2000] + "..."
            
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
    
    context_parts = ["Here are relevant documents from the knowledge base:\n"]
    
    for i, ctx in enumerate(contexts, 1):
        context_parts.append(f"\n--- Document {i}: {ctx.title} ---")
        context_parts.append(f"Relevance Score: {ctx.score:.2f}")
        if ctx.source:
            context_parts.append(f"Source: {ctx.source}")
        context_parts.append(f"\n{ctx.content}")
    
    context_parts.append("\n\n--- End of Retrieved Context ---\n")
    return "\n".join(context_parts)


@router.post("/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest
):
    """
    Get chat completion from Azure OpenAI.
    
    Supports multi-turn conversations by accepting full message history.
    Optionally enables RAG to retrieve context from indexed documents.
    """
    try:
        # Check if Azure OpenAI chat is available
        if not azure_openai_service.is_chat_available():
            raise HTTPException(
                status_code=503,
                detail="Azure OpenAI chat service is not available. Please check configuration."
            )
        
        retrieved_contexts = []
        
        # If RAG is enabled, retrieve context based on the last user message
        if request.use_rag:
            # Get the last user message for retrieval
            user_messages = [m for m in request.messages if m.role == "user"]
            if user_messages:
                last_query = user_messages[-1].content
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
        
        # Get completion from Azure OpenAI
        response = await azure_openai_service.chat_completion(
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False
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
            timestamp=datetime.utcnow().isoformat(),
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
        "timestamp": datetime.utcnow().isoformat()
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
