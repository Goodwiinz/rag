/**
 * TypeScript types for Project-Chat Integration
 * Maps to backend schemas in backend/src/shared/research_schemas.py:524-576
 */

// ============================================================================
// Enums
// ============================================================================

export enum ProjectThreadLinkType {
  AUTO = 'AUTO',
  MANUAL = 'MANUAL',
  FROM_CHAT = 'FROM_CHAT',
}

// ============================================================================
// Request Types
// ============================================================================

export interface StartChatFromProjectRequest {
  initial_message: string;
  conversation_id?: string;
  thread_title?: string;
}

export interface LinkThreadRequest {
  thread_id: string;
  context_note?: string;
}

export interface SaveThreadToNoteRequest {
  thread_id: string;
  note_title: string;
  include_citations?: boolean;
}

// ============================================================================
// Response Types
// ============================================================================

export interface StartChatFromProjectResponse {
  thread_id: string;
  conversation_id: string;
  project_thread_id: string;
  document_scope: string[];
}

export interface ProjectThread {
  id: string;
  project_id: string;
  thread_id: string;
  thread_title: string;
  conversation_id: string;
  link_type: ProjectThreadLinkType;
  linked_at: string;
  linked_by_id?: string;
  context_note?: string;
  message_count: number;
  last_message_at?: string;
}

export interface ProjectThreadListResponse {
  threads: ProjectThread[];
  total: number;
}
