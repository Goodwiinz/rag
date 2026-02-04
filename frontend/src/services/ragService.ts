/**
 * RAG Context Service for Local WebLLM Models
 *
 * Retrieves relevant context from the backend hybrid search
 * for use with in-browser local models (WebLLM).
 *
 * Phase 1 Improvements:
 * - Token-based budgeting (not character-based)
 * - Document IDs and relevance scores in prompts
 * - Simplified citation instructions for small models
 *
 * Phase 2 Improvements:
 * - Model-aware sizing (different budgets for 1B/3B/7B+ models)
 * - Few-shot citation examples for better citation compliance
 * - Conversation history trimming for small models
 */

import { apiClient } from './apiClient';
import { citationService } from './citationService';
import type { CitationCreate } from '@/types/research';

// ============================================
// MODEL SIZE DETECTION
// ============================================

/**
 * Model size categories for adaptive RAG configuration
 */
export type ModelSize = 'small' | 'medium' | 'large' | 'cloud';

/**
 * Detect model size from model ID string
 * Used to adapt RAG configuration for different model capabilities
 */
export function getModelSize(modelId: string): ModelSize {
  if (!modelId) return 'medium';

  const id = modelId.toLowerCase();

  // Cloud models (unlimited context, best instruction following)
  if (id.includes('gpt-') || id.includes('claude') || id.includes('gemini-pro')) {
    return 'cloud';
  }

  // Small models (1B-2B): Very limited context, simple instructions only
  if (id.includes('1b') || id.includes('1.5b') || id.includes('2b')) {
    return 'small';
  }

  // Medium models (3B-4B): Moderate context, can follow basic instructions
  if (id.includes('3b') || id.includes('3.5b') || id.includes('4b') || id.includes('3.8b')) {
    return 'medium';
  }

  // Large models (7B+): Good context, can follow complex instructions
  if (id.includes('7b') || id.includes('8b') || id.includes('13b') || id.includes('70b')) {
    return 'large';
  }

  // Default to medium for unknown models
  return 'medium';
}

/**
 * Model-aware RAG configuration
 * Adapts token budgets and document counts based on model size
 */
export interface ModelAwareRAGConfig {
  maxDocs: number;
  maxTokens: number;
  maxHistoryMessages: number;
  useFewShotExamples: boolean;
  useSimplePrompt: boolean;
}

/**
 * Get RAG configuration optimized for model size
 */
export function getRAGConfigForModel(modelSize: ModelSize): ModelAwareRAGConfig {
  switch (modelSize) {
    case 'small':
      // 1B-2B models: ~4K context, very limited
      return {
        maxDocs: 2,
        maxTokens: 600,      // Leave room for response
        maxHistoryMessages: 2,
        useFewShotExamples: false, // Too expensive for small models
        useSimplePrompt: true,
      };
    case 'medium':
      // 3B-4B models: ~4K-8K context
      return {
        maxDocs: 3,
        maxTokens: 1000,
        maxHistoryMessages: 4,
        useFewShotExamples: true,
        useSimplePrompt: true,
      };
    case 'large':
      // 7B+ models: 8K+ context, better instruction following
      return {
        maxDocs: 5,
        maxTokens: 2000,
        maxHistoryMessages: 8,
        useFewShotExamples: true,
        useSimplePrompt: false,
      };
    case 'cloud':
      // Cloud models: Large context, excellent instruction following
      return {
        maxDocs: 8,
        maxTokens: 4000,
        maxHistoryMessages: 20,
        useFewShotExamples: false, // Cloud models don't need examples
        useSimplePrompt: false,
      };
    default:
      return {
        maxDocs: 3,
        maxTokens: 1200,
        maxHistoryMessages: 4,
        useFewShotExamples: true,
        useSimplePrompt: true,
      };
  }
}

/**
 * RAG context item representing a relevant document chunk
 */
export interface RAGContextItem {
  documentId: string;
  title: string;
  content: string;
  score: number;
  source?: string;
  documentType?: string;
}

/**
 * RAG retrieval result containing context and metadata
 */
export interface RAGRetrievalResult {
  contexts: RAGContextItem[];
  query: string;
  retrievalTimeMs: number;
  totalResults: number;
  tokenEstimate: number;
}

/**
 * RAG retrieval options
 */
export interface RAGRetrievalOptions {
  /** Maximum number of context documents to retrieve (default: 3) */
  maxDocs?: number;
  /** Minimum relevance score threshold (default: 0.05) */
  minScore?: number;
  /** Maximum total context tokens (default: 1200 for small models) */
  maxTokens?: number;
}

// ============================================
// TOKEN ESTIMATION
// ============================================

/**
 * Estimate token count for a string
 * Uses rough approximation: 1 token ≈ 4 characters for English text
 * This is conservative to avoid exceeding context windows
 */
export function estimateTokens(text: string): number {
  if (!text) return 0;
  return Math.ceil(text.length / 4);
}

/**
 * Trim contexts to fit within token budget
 * Prioritizes higher-scoring documents (already sorted by score)
 */
function trimContextsToTokenBudget(
  contexts: RAGContextItem[],
  maxTokens: number
): { contexts: RAGContextItem[]; totalTokens: number } {
  let totalTokens = 0;
  const result: RAGContextItem[] = [];

  for (const ctx of contexts) {
    // Estimate tokens for this context including formatting overhead
    const headerTokens = estimateTokens(`=== [Doc ${result.length + 1}] ===\nTitle: ${ctx.title}\nID: ${ctx.documentId}\nRelevance: ${Math.round(ctx.score * 100)}%\nType: ${ctx.documentType || 'document'}\n\n`);
    const contentTokens = estimateTokens(ctx.content);
    const ctxTokens = headerTokens + contentTokens + 10; // +10 for separators

    if (totalTokens + ctxTokens <= maxTokens) {
      result.push(ctx);
      totalTokens += ctxTokens;
    } else if (result.length === 0) {
      // At least include 1 context, truncated to fit
      const availableContentTokens = maxTokens - headerTokens - 20;
      if (availableContentTokens > 50) {
        const truncatedContent = ctx.content.slice(0, availableContentTokens * 4) + '...';
        result.push({
          ...ctx,
          content: truncatedContent,
        });
        totalTokens = maxTokens;
      }
      break;
    } else {
      break;
    }
  }

  return { contexts: result, totalTokens };
}

// ============================================
// CONTENT EXTRACTION
// ============================================

/**
 * Extract the best content from a search result
 * Implements robust fallback chain matching backend behavior
 */
function extractBestContent(result: {
  content_preview: string;
  snippets?: Array<{ text: string; score: number }>;
  metadata?: Record<string, any>;
}): string {
  // 1. Try full text from metadata (best quality)
  if (result.metadata?.text && typeof result.metadata.text === 'string') {
    return result.metadata.text;
  }

  // 2. Try snippets (relevant excerpts)
  if (result.snippets && result.snippets.length > 0) {
    const sortedSnippets = [...result.snippets]
      .sort((a, b) => b.score - a.score)
      .slice(0, 3);
    return sortedSnippets.map((s) => s.text).join('\n\n');
  }

  // 3. Fall back to content preview
  if (result.content_preview) {
    return result.content_preview;
  }

  // 4. Try other metadata fields
  if (result.metadata?.content_snippet) {
    return result.metadata.content_snippet;
  }

  return '';
}

// ============================================
// RAG CONTEXT RETRIEVAL
// ============================================

/**
 * Retrieve RAG context from backend hybrid search
 *
 * @param query - User's query
 * @param options - Retrieval options
 * @returns RAG context items or null on failure
 */
export async function retrieveRAGContext(
  query: string,
  options: RAGRetrievalOptions = {}
): Promise<RAGRetrievalResult | null> {
  const {
    maxDocs = 3,      // Reduced from 5 for small models
    minScore = 0.05,  // Low threshold to get results
    maxTokens = 1200, // Token budget for small models (leaves room for prompt + response)
  } = options;

  const startTime = performance.now();

  try {
    console.log('[RAG] Calling /search/hybrid with query:', query);

    const response = await apiClient.post<{
      query: string;
      search_id: string;
      total_results: number;
      search_time_ms: number;
      results: Array<{
        document_id: string;
        title: string;
        document_type?: string;
        content_preview: string;
        snippets?: Array<{ text: string; score: number }>;
        relevance_score: number;
        metadata?: Record<string, any>;
      }>;
    }>('/search/hybrid', {
      query,
      limit: maxDocs * 2,
      search_type: 'hybrid',
      include_snippets: true,
    });

    console.log('[RAG] Hybrid search response:', {
      total_results: response.total_results,
      results_count: response.results?.length || 0,
      search_time_ms: response.search_time_ms,
    });

    // Log scores for debugging
    if (response.results?.length > 0) {
      const scores = response.results.map(r => r.relevance_score);
      const passing = scores.filter(s => s >= minScore).length;
      console.log(`[RAG] Scores: ${scores.map(s => s.toFixed(3)).join(', ')}`);
      console.log(`[RAG] Min threshold: ${minScore}, Passing: ${passing}/${scores.length}`);
    }

    // Transform and filter results
    let contexts: RAGContextItem[] = response.results
      .filter((result) => result.relevance_score >= minScore)
      .slice(0, maxDocs)
      .map((result) => ({
        documentId: result.document_id,
        title: result.title,
        content: extractBestContent(result),
        score: result.relevance_score,
        source: result.metadata?.source || undefined,
        documentType: result.document_type,
      }));

    // Trim to token budget
    const { contexts: trimmedContexts, totalTokens } = trimContextsToTokenBudget(contexts, maxTokens);
    contexts = trimmedContexts;

    console.log(`[RAG] Token budget: ${totalTokens}/${maxTokens} tokens used, ${contexts.length} docs included`);

    const endTime = performance.now();

    return {
      contexts,
      query,
      retrievalTimeMs: endTime - startTime,
      totalResults: response.total_results,
      tokenEstimate: totalTokens,
    };
  } catch (error: any) {
    console.error('[RAG] Failed to retrieve context:', error);
    console.error('[RAG] Error details:', {
      message: error?.message,
      status: error?.response?.status,
      data: error?.response?.data,
    });
    return null;
  }
}

// ============================================
// SYSTEM PROMPT BUILDING
// ============================================

/**
 * Few-shot example for citation format
 * Shows the model how to properly cite documents
 */
const FEW_SHOT_CITATION_EXAMPLE = `
Example of correct citation format:
Q: What is retrieval-augmented generation?
A: Retrieval-Augmented Generation (RAG) combines retrieval with generation [Doc 1]. It retrieves relevant documents and uses them to generate more accurate responses [Doc 1]. This approach helps reduce hallucinations [Doc 2].
`;

/**
 * Build a system prompt with RAG context for local models
 *
 * Phase 1 Improvements:
 * - Includes document IDs for proper citations
 * - Shows relevance scores for transparency
 * - Simplified instructions that small models can follow
 *
 * Phase 2 Improvements:
 * - Model-aware prompt construction
 * - Few-shot examples for medium+ models
 * - Optimized token usage per model size
 *
 * @param basePrompt - Base system prompt
 * @param contexts - Retrieved RAG contexts
 * @param modelSize - Model size for adaptive prompting (default: 'medium')
 * @returns Enhanced system prompt with context
 */
export function buildRAGSystemPrompt(
  basePrompt: string,
  contexts: RAGContextItem[],
  modelSize: ModelSize = 'medium'
): string {
  if (!contexts || contexts.length === 0) {
    return basePrompt;
  }

  const config = getRAGConfigForModel(modelSize);

  const contextSection = contexts
    .map((ctx, idx) => {
      const docNum = idx + 1;
      const relevancePercent = Math.round(ctx.score * 100);
      return `=== [Doc ${docNum}] ===
Title: ${ctx.title}
ID: ${ctx.documentId || 'N/A'}
Relevance: ${relevancePercent}%
Type: ${ctx.documentType || 'document'}

${ctx.content}`;
    })
    .join('\n\n');

  // Build instructions based on model capabilities
  let instructions: string;
  let fewShotSection = '';

  if (config.useFewShotExamples) {
    // Medium and large models: Include few-shot example
    fewShotSection = FEW_SHOT_CITATION_EXAMPLE;
  }

  if (config.useSimplePrompt) {
    // Small/medium models: Simple, direct instructions
    instructions = 'IMPORTANT: When answering, write [Doc 1] or [Doc 2] after each fact from the documents.';
  } else {
    // Large models: More detailed instructions
    instructions = `CITATION RULES:
1. Always cite sources using [Doc N] format after each fact
2. Include the document number that contains the information
3. If information comes from multiple documents, cite all of them
4. Example: "The technique improves accuracy [Doc 1] and reduces latency [Doc 2]."`;
  }

  return `${basePrompt}

---
KNOWLEDGE BASE CONTEXT:
${contextSection}
---
${fewShotSection}
${instructions}`;
}

// ============================================
// RAG SERVICE CLASS
// ============================================

/**
 * RAG Service singleton for managing retrieval state
 */
class RAGService {
  private lastRetrievalTime = 0;
  private cachedResult: RAGRetrievalResult | null = null;
  private cachedKey = '';
  private cacheValidityMs = 30000; // Cache valid for 30 seconds

  /**
   * Create a stable cache key from query and options
   */
  private createCacheKey(query: string, options?: RAGRetrievalOptions): string {
    const cacheData = {
      query,
      maxDocs: options?.maxDocs,
      minScore: options?.minScore,
      maxTokens: options?.maxTokens,
    };
    // Create stable JSON string with sorted keys
    return JSON.stringify(cacheData, Object.keys(cacheData).sort());
  }

  /**
   * Retrieve RAG context with caching
   */
  async retrieve(
    query: string,
    options?: RAGRetrievalOptions
  ): Promise<RAGRetrievalResult | null> {
    // Create cache key including query and options
    const cacheKey = this.createCacheKey(query, options);

    // Check cache for same query+options within validity period
    if (
      this.cachedKey === cacheKey &&
      this.cachedResult &&
      Date.now() - this.lastRetrievalTime < this.cacheValidityMs
    ) {
      console.log('[RAG] Using cached context');
      return this.cachedResult;
    }

    // Retrieve fresh context
    const result = await retrieveRAGContext(query, options);

    if (result) {
      this.cachedKey = cacheKey;
      this.cachedResult = result;
      this.lastRetrievalTime = Date.now();
    }

    return result;
  }

  /**
   * Clear the cache
   */
  clearCache(): void {
    this.cachedKey = '';
    this.cachedResult = null;
    this.lastRetrievalTime = 0;
  }

  /**
   * Parse [Doc N] citations from AI response
   * Returns array of unique citation indices (1-based)
   */
  parseCitationIndices(responseText: string): number[] {
    const pattern = /\[Doc\s+(\d+)\]/g;
    const matches = [...responseText.matchAll(pattern)];
    const indices = matches.map(m => parseInt(m[1], 10));
    return Array.from(new Set(indices)).sort((a, b) => a - b);
  }

  /**
   * Persist citations from AI response to backend
   * 
   * @param messageId - Chat message ID containing the AI response
   * @param responseText - AI response text with [Doc N] citations
   * @param retrievedDocuments - Documents that were used for RAG context
   * @returns Array of created citation IDs
   */
  async persistCitations(
    messageId: string,
    responseText: string,
    retrievedDocuments: RAGContextItem[]
  ): Promise<string[]> {
    try {
      const citationIndices = this.parseCitationIndices(responseText);
      
      if (citationIndices.length === 0) {
        console.log('[RAG] No citations found in response');
        return [];
      }

      console.log(`[RAG] Found ${citationIndices.length} unique citations:`, citationIndices);

      const createdIds: string[] = [];

      for (const citationIndex of citationIndices) {
        // [Doc 1] corresponds to retrievedDocuments[0]
        const docIndex = citationIndex - 1;

        if (docIndex < 0 || docIndex >= retrievedDocuments.length) {
          console.warn(`[RAG] Citation index ${citationIndex} out of range (${retrievedDocuments.length} docs)`);
          continue;
        }

        const doc = retrievedDocuments[docIndex];

        const citationData: CitationCreate = {
          messageId,
          documentId: doc.documentId,
          documentTitle: doc.title,
          documentType: doc.documentType || 'document',
          snippet: doc.content.slice(0, 500), // First 500 chars as snippet
          score: doc.score,
          metadataSource: 'rag',
          needsReview: false,
        };

        try {
          const created = await citationService.createCitation(citationData);
          createdIds.push(created.id);
          console.log(`[RAG] Created citation ${citationIndex} -> ${created.id}`);
        } catch (error) {
          console.error(`[RAG] Failed to create citation ${citationIndex}:`, error);
        }
      }

      console.log(`[RAG] Persisted ${createdIds.length}/${citationIndices.length} citations`);
      return createdIds;

    } catch (error) {
      console.error('[RAG] Failed to persist citations:', error);
      return [];
    }
  }
}

// Export singleton instance
export const ragService = new RAGService();

// ============================================
// CONVERSATION HISTORY TRIMMING
// ============================================

/**
 * Trim conversation history to fit within model's context limits
 * Keeps the most recent messages, prioritizing user context
 *
 * @param messages - Full conversation history
 * @param maxMessages - Maximum number of messages to keep
 * @returns Trimmed conversation history
 */
export function trimConversationHistory<T extends { role: string; content: string }>(
  messages: T[],
  maxMessages: number
): T[] {
  if (messages.length <= maxMessages) {
    return messages;
  }

  // Always keep the most recent messages
  const trimmed = messages.slice(-maxMessages);

  console.log(`[RAG] Trimmed conversation history: ${messages.length} -> ${trimmed.length} messages`);

  return trimmed;
}

/**
 * Get model-aware conversation history limit
 * Returns the trimmed history based on model size
 */
export function getModelAwareHistory<T extends { role: string; content: string }>(
  messages: T[],
  modelId: string
): T[] {
  const modelSize = getModelSize(modelId);
  const config = getRAGConfigForModel(modelSize);
  return trimConversationHistory(messages, config.maxHistoryMessages);
}
