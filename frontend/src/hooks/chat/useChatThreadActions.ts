import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { getNewChatUrl } from '@/components/chat/shared/chatNavigation';
import { ChatConversation } from '@/hooks/chat/chatTypes';
import { workspaceService } from '@/services/workspaceService';
import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';

// ============================================
// DIALOG STATE TYPES (exported for ChatDialogs)
// ============================================

export interface RenameDialogState {
  open: boolean;
  threadId: string;
  currentTitle: string;
  value: string;
}

export interface DeleteDialogState {
  open: boolean;
  threadId: string;
}

export interface BulkDeleteDialogState {
  open: boolean;
  ids: string[];
}

// ============================================
// HOOK PARAMS
// ============================================

export interface UseChatThreadActionsParams {
  conversations: ChatConversation[];
  setConversations: React.Dispatch<React.SetStateAction<ChatConversation[]>>;
  activeConversationId: string | null;
  setActiveConversationId: React.Dispatch<React.SetStateAction<string | null>>;
  activeConversationIdRef: React.MutableRefObject<string | null>;
  setMessages: React.Dispatch<React.SetStateAction<ChatPageMessage[]>>;
  setCurrentThread: (threadId: string | null) => void;
}

// ============================================
// HOOK
// ============================================

export function useChatThreadActions({
  conversations,
  setConversations,
  activeConversationId,
  setActiveConversationId,
  activeConversationIdRef,
  setMessages,
  setCurrentThread,
}: UseChatThreadActionsParams) {
  const router = useRouter();

  // Dialog state for rename/delete — replaces window.prompt/confirm
  const [renameDialog, setRenameDialog] = useState<RenameDialogState>({
    open: false,
    threadId: '',
    currentTitle: '',
    value: '',
  });
  const [deleteDialog, setDeleteDialog] = useState<DeleteDialogState>({
    open: false,
    threadId: '',
  });
  const [bulkDeleteDialog, setBulkDeleteDialog] =
    useState<BulkDeleteDialogState>({ open: false, ids: [] });

  const handleRenameThread = useCallback(
    async (threadId: string) => {
      const target = conversations.find((c) => c.id === threadId);
      setRenameDialog({
        open: true,
        threadId,
        currentTitle: target?.title ?? '',
        value: target?.title ?? '',
      });
    },
    [conversations]
  );

  const commitRename = useCallback(async () => {
    const { threadId, value, currentTitle } = renameDialog;
    const trimmed = value.trim();
    setRenameDialog((d) => ({ ...d, open: false }));
    if (!trimmed || trimmed === currentTitle) return;
    try {
      const updated = await workspaceService.updateThread(threadId, {
        title: trimmed,
      });
      const nextTitleValue = updated.title ?? trimmed;
      setConversations((prev) =>
        prev.map((c) =>
          c.id === threadId ? { ...c, title: nextTitleValue } : c
        )
      );
    } catch (err) {
      console.error('[Chat] Rename failed', err);
    }
  }, [renameDialog, setConversations]);

  const handleDeleteThread = useCallback((threadId: string) => {
    setDeleteDialog({ open: true, threadId });
  }, []);

  const commitDeleteThread = useCallback(async () => {
    const { threadId } = deleteDialog;
    setDeleteDialog({ open: false, threadId: '' });
    try {
      await workspaceService.deleteThread(threadId);
      setConversations((prev) => prev.filter((c) => c.id !== threadId));
      if (activeConversationId === threadId) {
        setActiveConversationId(null);
        activeConversationIdRef.current = null;
        setMessages([]);
        setCurrentThread(null);
        router.push(getNewChatUrl());
      }
    } catch (err) {
      console.error('[Chat] Delete failed', err);
    }
  }, [
    deleteDialog,
    activeConversationId,
    router,
    setCurrentThread,
    setConversations,
    setActiveConversationId,
    activeConversationIdRef,
    setMessages,
  ]);

  const handleBulkDeleteThreads = useCallback((ids: string[]) => {
    setBulkDeleteDialog({ open: true, ids });
  }, []);

  const commitBulkDelete = useCallback(async () => {
    const { ids } = bulkDeleteDialog;
    setBulkDeleteDialog({ open: false, ids: [] });
    try {
      await workspaceService.bulkDeleteThreads(ids);
      setConversations((prev) => prev.filter((c) => !ids.includes(c.id)));
      if (activeConversationId && ids.includes(activeConversationId)) {
        setActiveConversationId(null);
        activeConversationIdRef.current = null;
        setMessages([]);
        setCurrentThread(null);
        router.push(getNewChatUrl());
      }
    } catch (err) {
      console.error('[Chat] Bulk delete failed', err);
    }
  }, [
    bulkDeleteDialog,
    activeConversationId,
    router,
    setCurrentThread,
    setConversations,
    setActiveConversationId,
    activeConversationIdRef,
    setMessages,
  ]);

  return {
    // Dialog state
    renameDialog,
    setRenameDialog,
    deleteDialog,
    setDeleteDialog,
    bulkDeleteDialog,
    setBulkDeleteDialog,
    // Handlers
    handleRenameThread,
    commitRename,
    handleDeleteThread,
    commitDeleteThread,
    handleBulkDeleteThreads,
    commitBulkDelete,
  };
}
