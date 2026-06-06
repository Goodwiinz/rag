/**
 * TypeScript types for NOUS thread-centric chat system
 * Based on backend/src/schemas/chat.py
 */

// ============================================================================
// Enums
// ============================================================================

export enum WorkspaceRole {
  OWNER = 'owner',
  ADMIN = 'admin',
  EDITOR = 'editor',
  VIEWER = 'viewer',
}

export enum ThreadStatus {
  ACTIVE = 'active',
  RESOLVED = 'resolved',
  ARCHIVED = 'archived',
}

export enum MessageRole {
  USER = 'user',
  ASSISTANT = 'assistant',
  SYSTEM = 'system',
  TOOL = 'tool',
}

// ============================================================================
// Workspace Types
// ============================================================================

export interface WorkspaceCreate {
  name: string;
  description?: string;
  is_public?: boolean;
  organization_id?: string;
}

export interface WorkspaceUpdate {
  name?: string;
  description?: string;
  is_public?: boolean;
  is_archived?: boolean;
}

export interface WorkspaceMember {
  id: string;
  workspace_id: string;
  user_id: string;
  role: WorkspaceRole;
  joined_at: string;
  invited_by_id?: string;
  user_email?: string;
  user_name?: string;
  created_at: string;
  updated_at: string;
}

export interface Workspace {
  id: string;
  name: string;
  description?: string;
  is_public: boolean;
  owner_id: string;
  organization_id?: string;
  is_archived: boolean;
  member_count?: number;
  conversation_count?: number;
  collection_count?: number;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceDetail extends Workspace {
  members: WorkspaceMember[];
}

// ============================================================================
// Conversation Types
// ============================================================================

export interface ConversationCreate {
  title: string;
  description?: string;
  workspace_id: string;
}

export interface ConversationUpdate {
  title?: string;
  description?: string;
  is_archived?: boolean;
  is_pinned?: boolean;
}

export interface Conversation {
  id: string;
  workspace_id: string;
  created_by_id: string;
  title: string;
  description?: string;
  is_archived: boolean;
  is_pinned: boolean;
  last_activity_at: string;
  thread_count?: number;
  message_count?: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  conversations: Conversation[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}

// ============================================================================
// Thread Types
// ============================================================================

export interface ThreadCreate {
  conversation_id: string;
  title?: string;
  initial_message?: string;
  project_id?: string;
}

export interface ThreadUpdate {
  title?: string;
  summary?: string;
  status?: ThreadStatus;
}

export interface Thread {
  id: string;
  conversation_id: string;
  title?: string;
  summary?: string;
  status: ThreadStatus;
  last_message_at: string;
  message_count: number;
  token_count: number;
  created_by_id?: string;
  created_at: string;
  updated_at: string;
}

export interface ThreadDetail extends Thread {
  messages: ChatMessage[];
}

export interface ThreadListResponse {
  threads: Thread[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}

// ============================================================================
// Bulk Thread Operations
// ============================================================================

export interface BulkThreadRequest {
  thread_ids: string[];
}

export interface BulkThreadResult {
  thread_id: string;
  success: boolean;
  error?: string;
  thread?: Thread;
}

export interface BulkThreadResponse {
  total: number;
  succeeded: number;
  failed: number;
  results: BulkThreadResult[];
}

// ============================================================================
// Chat Message Types
// ============================================================================

export interface Citation {
  id: string;
  document_id?: string; // Optional: may not have a database UUID
  external_reference_id?: string; // For non-database references (e.g., arXiv IDs)
  chunk_index?: number;
  chunk_id?: string;
  snippet?: string;
  snippet_preview?: string;
  page_number?: number;
  score?: number;
  rerank_score?: number;
  document_title?: string;
  document_type?: string;
}

export interface MessageAttachment {
  id: string;
  document_id: string;
  display_name?: string;
  thumbnail_url?: string;
  document_title?: string;
  document_type?: string;
  mime_type?: string;
}

// Citation input for creating messages with RAG sources
export interface CitationCreate {
  document_id?: string; // Optional: may not have a database UUID
  external_reference_id?: string; // For non-database references (e.g., arXiv IDs)
  chunk_index?: number;
  chunk_id?: string;
  snippet?: string;
  snippet_preview?: string;
  page_number?: number;
  score?: number;
  rerank_score?: number;
  document_title?: string;
  document_type?: string;
}

export interface ChatMessageCreate {
  thread_id: string;
  content: string;
  role?: MessageRole;
  attachment_ids?: string[];
  citations?: CitationCreate[]; // Citations from RAG retrieval
  latency_ms?: number; // Client-measured response time (ms)
  stopped?: boolean; // User stopped this response mid-stream
}

export interface ChatMessageUpdate {
  feedback_rating?: number;
  feedback_text?: string;
}

export interface ChatMessage {
  id: string;
  thread_id: string;
  user_id?: string;
  content: string;
  role: MessageRole;
  token_count: number;
  latency_ms?: number;
  stopped?: boolean;
  model_name?: string;
  model_version?: string;
  tool_name?: string;
  tool_call_id?: string;
  feedback_rating?: number;
  feedback_text?: string;
  citations: Citation[];
  attachments: MessageAttachment[];
  created_at: string;
  updated_at: string;
}

export interface ChatMessageListResponse {
  messages: ChatMessage[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}

// ============================================================================
// Collection Types
// ============================================================================

export interface CollectionCreate {
  name: string;
  description?: string;
  color?: string;
  icon?: string;
  workspace_id: string;
  document_ids?: string[];
}

export interface CollectionUpdate {
  name?: string;
  description?: string;
  color?: string;
  icon?: string;
}

export interface Collection {
  id: string;
  workspace_id: string;
  name: string;
  description?: string;
  color?: string;
  icon?: string;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionDetail extends Collection {
  documents: Record<string, any>[];
}

export interface CollectionListResponse {
  collections: Collection[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}

// ============================================================================
// Chat Completion Types
// ============================================================================

export interface ChatCompletionRequest {
  thread_id: string;
  message: string;
  use_rag?: boolean;
  collection_ids?: string[];
  search_type?: string;
  top_k?: number;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  stream?: boolean;
}

export interface ChatCompletionResponse {
  message: ChatMessage;
  usage: Record<string, number>;
  sources_used: number;
  search_latency_ms?: number;
  generation_latency_ms?: number;
}

export interface StreamingChatChunk {
  chunk_type: 'content' | 'citation' | 'done' | 'error';
  content?: string;
  citation?: Citation;
  message_id?: string;
  error?: string;
}

// ============================================================================
// Search Types
// ============================================================================

export interface WorkspaceSearchRequest {
  query: string;
  workspace_id: string;
  collection_ids?: string[];
  conversation_ids?: string[];
  date_from?: string;
  date_to?: string;
  search_type?: string;
  include_messages?: boolean;
  include_documents?: boolean;
  top_k?: number;
}

export interface WorkspaceSearchResult {
  result_type: 'message' | 'document' | 'thread';
  id: string;
  score: number;
  snippet: string;
  thread_id?: string;
  thread_title?: string;
  conversation_id?: string;
  conversation_title?: string;
  document_id?: string;
  document_title?: string;
  created_at: string;
}

export interface WorkspaceSearchResponse {
  results: WorkspaceSearchResult[];
  total: number;
  query: string;
  search_latency_ms: number;
}
