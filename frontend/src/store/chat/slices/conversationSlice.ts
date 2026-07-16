/**
 * Conversation CRUD actions.
 *
 * Split out of chat-store.ts (Task 5.4) with no behavior change.
 */
import {
  Conversation,
  ConversationCreate,
  ConversationUpdate,
} from '@/types/workspace';
import { workspaceService } from '@/services/workspaceService';
import type { ChatSliceCreator } from '../types';
import { removeItemFromRecord } from '../recordIndex';
import { handleStaleDataRecovery } from './workspaceSlice';

export interface ConversationSlice {
  loadConversations: (workspaceId: string) => Promise<void>;
  createConversation: (
    data: ConversationCreate
  ) => Promise<Conversation | null>;
  updateConversation: (
    id: string,
    data: ConversationUpdate
  ) => Promise<Conversation | null>;
  deleteConversation: (id: string) => Promise<boolean>;
}

export const createConversationSlice: ChatSliceCreator<ConversationSlice> = (
  set,
  get
) => ({
  loadConversations: async (workspaceId) => {
    set((state) => {
      state.isLoadingConversations = true;
      state.error = null;
    });

    try {
      const response = await workspaceService.listConversations(workspaceId);
      set((state) => {
        state.conversations[workspaceId] = response.conversations;
        // Populate reverse index for O(1) lookup (GOO-86)
        for (const conv of response.conversations) {
          state.conversationToWorkspace[conv.id] = workspaceId;
        }
        state.isLoadingConversations = false;
      });
    } catch (error: any) {
      console.error('[ChatStore] Error loading conversations:', error);

      // Handle 404 - workspace not found (stale data)
      if (error?.response?.status === 404) {
        console.warn(
          '[ChatStore] Workspace not found (404) - clearing stale data'
        );
        const result = handleStaleDataRecovery(get, set, 'loadConversations', {
          clearWorkspaces: true,
          loadingKey: 'isLoadingConversations',
        });
        if (result.shouldProceed) {
          result.triggerReinit();
        }
        return;
      }

      set((state) => {
        state.error = 'Failed to load conversations';
        state.isLoadingConversations = false;
      });
    }
  },

  createConversation: async (data) => {
    try {
      const conversation = await workspaceService.createConversation(data);
      set((state) => {
        const workspaceId = data.workspace_id;
        if (!state.conversations[workspaceId]) {
          state.conversations[workspaceId] = [];
        }
        state.conversations[workspaceId].unshift(conversation);
        // Populate reverse index (GOO-86)
        state.conversationToWorkspace[conversation.id] = workspaceId;
      });
      return conversation;
    } catch (error: any) {
      console.error('[ChatStore] Error creating conversation:', error);

      // Handle 404 - workspace not found (stale data)
      if (error?.response?.status === 404) {
        console.warn(
          '[ChatStore] Workspace not found (404) while creating conversation - clearing stale data'
        );
        const result = handleStaleDataRecovery(get, set, 'createConversation', {
          clearWorkspaces: true,
        });
        if (result.shouldProceed) {
          result.triggerReinit();
        }
        return null;
      }

      set((state) => {
        state.error = 'Failed to create conversation';
      });
      return null;
    }
  },

  updateConversation: async (id, data) => {
    try {
      const conversation = await workspaceService.updateConversation(
        id,
        data
      );
      set((state) => {
        const workspaceId = conversation.workspace_id;
        const convs = state.conversations[workspaceId] || [];
        const index = convs.findIndex((c) => c.id === id);
        if (index !== -1) {
          state.conversations[workspaceId][index] = conversation;
        }
      });
      return conversation;
    } catch (error) {
      console.error('[ChatStore] Error updating conversation:', error);
      set((state) => {
        state.error = 'Failed to update conversation';
      });
      return null;
    }
  },

  deleteConversation: async (id) => {
    try {
      await workspaceService.deleteConversation(id);
      set((state) => {
        // Use O(1) reverse index lookup (GOO-86)
        removeItemFromRecord(
          state.conversations,
          id,
          state.conversationToWorkspace
        );
        if (state.currentConversationId === id) {
          state.currentConversationId = null;
          state.currentThreadId = null;
        }
      });
      return true;
    } catch (error) {
      console.error('[ChatStore] Error deleting conversation:', error);
      set((state) => {
        state.error = 'Failed to delete conversation';
      });
      return false;
    }
  },
});
