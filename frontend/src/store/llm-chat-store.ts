import { create } from 'zustand';

interface LLMChatStore {
  shortcutsDialogOpen: boolean;
  setShortcutsDialogOpen: (open: boolean) => void;
  copiedMessageId: string | null;
  setCopiedMessageId: (id: string | null) => void;
}

export const useLLMChatStore = create<LLMChatStore>((set) => ({
  shortcutsDialogOpen: false,
  setShortcutsDialogOpen: (open) => set({ shortcutsDialogOpen: open }),
  copiedMessageId: null,
  setCopiedMessageId: (id) => set({ copiedMessageId: id }),
}));
