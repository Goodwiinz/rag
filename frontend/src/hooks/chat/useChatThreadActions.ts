import toast from 'react-hot-toast';

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
  activeThreadId: string | null;
  setCurrentThread: (threadId: string | null) => void;
}

// ============================================
// HOOK
// ============================================

export function useChatThreadActions({
  conversations,
  setConversations,
  activeThreadId,
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
      // The dialog already closed optimistically, so without this the title
      // silently stays the old value and the rename looks like it worked.
      console.error('[Chat] Rename failed', err);
      toast.error('Could not rename the conversation. Please try again.');
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
      if (activeThreadId === threadId) {
        setCurrentThread(null);
        router.push(getNewChatUrl());
      }
    } catch (err) {
      console.error('[Chat] Delete failed', err);
      toast.error('Could not delete the conversation. Please try again.');
    }
  }, [
    deleteDialog,
    activeThreadId,
    router,
    setCurrentThread,
    setConversations,
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
      if (activeThreadId && ids.includes(activeThreadId)) {
        setCurrentThread(null);
        router.push(getNewChatUrl());
      }
    } catch (err) {
      console.error('[Chat] Bulk delete failed', err);
      toast.error(
        'Could not delete the selected conversations. Please try again.'
      );
    }
  }, [
    bulkDeleteDialog,
    activeThreadId,
    router,
    setCurrentThread,
    setConversations,
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
