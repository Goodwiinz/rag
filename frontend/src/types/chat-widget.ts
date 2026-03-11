/**
 * Types for the Project Chat Widget (floating panel)
 * Used by useProjectChatWidget hook and chat-widget components
 */

// ============================================================================
// Message Types
// ============================================================================

export interface WidgetCitation {
  /** Document ID referenced */
  documentId: string;
  /** Display title of the cited document */
  documentTitle: string;
  /** Relevant snippet from the document */
  snippet?: string;
  /** Page number if applicable */
  page?: number;
}

export interface WidgetMessage {
  /** Unique message identifier */
  id: string;
  /** Who sent the message */
  role: 'user' | 'assistant';
  /** Message text content */
  content: string;
  /** When the message was created */
  timestamp: Date;
  /** Citations referenced in assistant replies */
  citations?: WidgetCitation[];
  /** Whether the message is still being streamed */
  isStreaming?: boolean;
}

// ============================================================================
// Context Chip Types
// ============================================================================

export type ContextChipKind = 'documents' | 'notes' | 'bibliography';

export interface ContextChip {
  /** Unique chip key (same as kind) */
  kind: ContextChipKind;
  /** Display label */
  label: string;
  /** Item count shown in chip */
  count: number;
  /** Whether this chip is active (included in context) */
  active: boolean;
  /** Icon name hint for rendering */
  icon: 'file-text' | 'sticky-note' | 'book-open';
}

// ============================================================================
// Hook State Types
// ============================================================================

export interface ChatWidgetState {
  /** Whether the chat panel is open */
  isOpen: boolean;
  /** Chat messages in current session */
  messages: WidgetMessage[];
  /** Available context chips */
  contextChips: ContextChip[];
  /** Whether assistant is currently streaming a response */
  isStreaming: boolean;
  /** Current input value */
  inputValue: string;
  /** Whether there are unread assistant messages (panel closed) */
  hasUnread: boolean;
  /** Active thread ID from backend */
  threadId: string | null;
  /** Active conversation ID from backend */
  conversationId: string | null;
}

export interface ChatWidgetActions {
  /** Open the chat panel */
  open: () => void;
  /** Close the chat panel */
  close: () => void;
  /** Toggle the chat panel */
  toggle: () => void;
  /** Toggle a context chip on/off */
  toggleChip: (kind: ContextChipKind) => void;
  /** Set the input value */
  setInputValue: (value: string) => void;
  /** Send the current input as a message */
  sendMessage: () => Promise<void>;
  /** Clear all messages and reset the session */
  clearMessages: () => void;
}
