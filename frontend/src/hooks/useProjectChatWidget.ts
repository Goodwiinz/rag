'use client';

/**
 * Hook for managing the Project Chat Widget state and actions.
 * Manages panel open/close, messages, context chips, and sending.
 */

import { useState, useCallback, useMemo } from 'react';
import { useProjectStore } from '@/store/projectStore';
import { projectChatService } from '@/services/projectChatService';
import type {
  WidgetMessage,
  ContextChip,
  ContextChipKind,
  ChatWidgetState,
  ChatWidgetActions,
} from '@/types/chat-widget';

type TabType =
  | 'documents'
  | 'notes'
  | 'bibliography'
  | 'drafts'
  | 'chat'
  | 'matrix'
  | 'pipeline';

interface UseProjectChatWidgetOptions {
  projectId: string;
  activeTab: TabType;
}

export function useProjectChatWidget({
  projectId,
  activeTab,
}: UseProjectChatWidgetOptions): ChatWidgetState & ChatWidgetActions {
  // Panel state
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<WidgetMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [hasUnread, setHasUnread] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  // Chip active states
  const [chipStates, setChipStates] = useState<
    Record<ContextChipKind, boolean>
  >({
    documents: true,
    notes: false,
    bibliography: false,
  });

  // Derive context chips from projectStore
  const { projectDocuments, projectNotes, bibliography } = useProjectStore();

  const contextChips: ContextChip[] = useMemo(() => {
    const chips: ContextChip[] = [
      {
        kind: 'documents',
        label: 'Documents',
        count: projectDocuments.length,
        active: chipStates.documents,
        icon: 'file-text',
      },
      {
        kind: 'notes',
        label: 'Notes',
        count: projectNotes.length,
        active: chipStates.notes,
        icon: 'sticky-note',
      },
      {
        kind: 'bibliography',
        label: 'Bibliography',
        count: bibliography?.citation_count ?? 0,
        active: chipStates.bibliography,
        icon: 'book-open',
      },
    ];

    // Auto-activate chip matching the current active tab
    if (
      activeTab === 'documents' ||
      activeTab === 'notes' ||
      activeTab === 'bibliography'
    ) {
      return chips.map((chip) => ({
        ...chip,
        active: chip.kind === activeTab ? true : chip.active,
      }));
    }

    return chips;
  }, [
    projectDocuments.length,
    projectNotes.length,
    bibliography,
    chipStates,
    activeTab,
  ]);

  // Actions
  const open = useCallback(() => {
    setIsOpen(true);
    setHasUnread(false);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
  }, []);

  const toggle = useCallback(() => {
    setIsOpen((prev) => {
      if (!prev) setHasUnread(false);
      return !prev;
    });
  }, []);

  const toggleChip = useCallback((kind: ContextChipKind) => {
    setChipStates((prev) => ({
      ...prev,
      [kind]: !prev[kind],
    }));
  }, []);

  const toggleAllChips = useCallback((enabled: boolean) => {
    setChipStates({
      documents: enabled,
      notes: enabled,
      bibliography: enabled,
    });
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setThreadId(null);
    setConversationId(null);
    setIsStreaming(false);
  }, []);

  const sendMessage = useCallback(async () => {
    const trimmed = inputValue.trim();
    if (!trimmed || isStreaming) return;

    // Add user message
    const userMessage: WidgetMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: trimmed,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsStreaming(true);

    try {
      // TODO: Include `chipStates` as `context_kinds` in the request payload
      // when the backend StartChatFromProjectRequest supports context_kinds filtering.
      const response = await projectChatService.startChatFromProject(
        projectId,
        {
          initial_message: trimmed,
          conversation_id: conversationId ?? undefined,
          thread_title:
            messages.length === 0 ? trimmed.slice(0, 80) : undefined,
        }
      );

      setThreadId(response.thread_id);
      setConversationId(response.conversation_id);

      // Add assistant placeholder response
      const assistantMessage: WidgetMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content:
          "I've started analyzing your project documents. You can view the full conversation in the Chat tab.",
        timestamp: new Date(),
        citations: response.document_scope.map((docId) => ({
          documentId: docId,
          documentTitle: docId,
        })),
      };
      setMessages((prev) => [...prev, assistantMessage]);

      // Mark unread if panel is closed
      if (!isOpen) {
        setHasUnread(true);
      }
    } catch (error) {
      console.error('Failed to send chat message:', error);
      const errorMessage: WidgetMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsStreaming(false);
    }
  }, [
    inputValue,
    isStreaming,
    projectId,
    conversationId,
    messages.length,
    isOpen,
  ]);

  return {
    // State
    isOpen,
    messages,
    contextChips,
    isStreaming,
    inputValue,
    hasUnread,
    threadId,
    conversationId,
    // Actions
    open,
    close,
    toggle,
    toggleChip,
    toggleAllChips,
    setInputValue,
    sendMessage,
    clearMessages,
  };
}
