# RAG + WebLLM Integration Plan

## Feature Overview
Integrate backend RAG (Retrieval-Augmented Generation) with frontend WebLLM local models to enable context-aware responses from in-browser models like Phi-3.5-mini, Llama, and Gemma.

## Current State Analysis

### Cloud Models (Already Working)
Cloud models in `frontend/app/chat/page.tsx` already have RAG:
```typescript
// Lines 1463-1563 in handleSubmit()
const data = await apiClient.post('/chat/completions', {
  messages: [...],
  model: selectedModel,
  use_rag: true,  // RAG ENABLED
  max_context_docs: 5,
});
// Citations extracted from data.retrieved_contexts
```

### Local Models (Gap to Fill)
Local WebLLM models do NOT have RAG:
```typescript
// Lines 1564-1579 in handleSubmit()
} else {
  // Use local WebLLM engine - NO RAG!
  const response = await engineRef.current!.chat.completions.create({
    messages: [...],  // Raw messages without context
    stream: true,
  });
}
```

## Implementation Architecture

### Hybrid Approach
- **Backend**: Handles RAG retrieval via existing `/api/v1/search/hybrid`
- **Frontend**: Constructs augmented prompts for local WebLLM models

### Key Files to Modify
1. `frontend/app/chat/page.tsx` - Main chat logic
2. `frontend/src/services/ragService.ts` - New RAG context service (optional)
3. `frontend/src/components/chat/RAGToggle.tsx` - New toggle component

## GoodFlows Plan Reference
- Phase: `02-rag-webllm-integration`
- Plan: `02-01-PLAN.md`
- Tasks: 5 (4 auto + 1 human checkpoint)

## Implementation Tasks

### Task 1: RAG Context Retrieval Function
```typescript
async function retrieveRAGContext(query: string): Promise<RAGContext> {
  const response = await apiClient.post('/search/hybrid', {
    query,
    limit: 5,
    include_snippets: true,
  });
  return {
    contexts: response.results.map(r => ({
      document_id: r.document_id,
      title: r.title,
      content: r.content_preview,
      score: r.relevance_score,
    })),
    query,
  };
}
```

### Task 2: RAG Toggle UI
- Add `enableRAG` state (default: true)
- Create toggle switch styled with Terminal Observatory theme
- Persist to localStorage

### Task 3: Integrate RAG into WebLLM Flow
```typescript
// In handleSubmit(), for local models:
if (enableRAG && !isCloudModel) {
  setIsRetrieving(true);
  const ragContext = await retrieveRAGContext(userMessage);
  setIsRetrieving(false);
  
  const contextBlock = formatContextForPrompt(ragContext);
  const augmentedSystemPrompt = `${settings.systemPrompt}\n\n${contextBlock}`;
  
  // Send to WebLLM with augmented prompt
  const response = await engineRef.current!.chat.completions.create({
    messages: [
      { role: 'system', content: augmentedSystemPrompt },
      ...userMessages,
    ],
    stream: true,
  });
}
```

### Task 4: Citation Mapping
```typescript
const citations: Citation[] = ragContext.contexts.map((ctx, idx) => ({
  id: `local-cite-${idx}`,
  document_id: ctx.document_id,
  document_title: ctx.title,
  snippet: ctx.content,
  confidence: ctx.score,
  file_type: 'document',
}));
// Store with assistant message
```

## Success Criteria
- [ ] Local WebLLM models can access backend document knowledge
- [ ] RAG toggle allows users to enable/disable context retrieval
- [ ] Citations display for local model responses
- [ ] No regression in cloud model RAG functionality
- [ ] Graceful fallback when RAG retrieval fails
- [ ] RAG retrieval < 2s latency

## Theme Constants (Terminal Observatory)
- PHOSPHOR_GREEN = '#00ff9f'
- AMBER = '#ffb700'
- CYAN = '#00d4ff'
