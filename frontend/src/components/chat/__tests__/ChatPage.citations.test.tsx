/**
 * ChatPage citation wiring: transcript citation clicks focus the sources in
 * the split-view artifact panel (store-backed — the panel itself renders in
 * the chat layout, not this page), plus the project-context command action.
 */
import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatPage from '../../../../app/(dashboard)/chat/page';
import { useArtifactPanelStore } from '@/store/artifactPanelStore';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import type { CommandAction } from '@/components/chat/commandOutput';
import type { Citation } from '@/utils/citationParser';

const mockUseChatSession = vi.fn();
const mockRouterPush = vi.fn();
const mockRouterReplace = vi.fn();
const mockSetInput = vi.fn();

vi.mock('@/components/chat', () => ({
  ChatInput: () => <div data-testid="chat-input" />,
  WelcomeState: () => <div data-testid="welcome-state" />,
}));
vi.mock('@/components/chat/ChatDialogs', () => ({ ChatDialogs: () => null }));
vi.mock('@/components/chat/ChatHeader', () => ({ ChatHeader: () => null }));
vi.mock('@/components/chat/ChatMessageList', () => ({
  ChatMessageList: (props: {
    messages: ChatPageMessage[];
    onCitationClick: (
      citations: Citation[],
      clicked: Citation,
      traceId?: string
    ) => void;
    onCommandItemAction?: (action: CommandAction) => void;
  }) => (
    <div>
      {props.messages.map((message) => (
        <p key={`${message.role}:${message.content}`}>{message.content}</p>
      ))}
      <button
        type="button"
        data-testid="cite-trigger"
        onClick={() =>
          props.onCitationClick(
            [{ title: 'Paper A', documentId: 'doc-1' } as Citation],
            { title: 'Paper A', documentId: 'doc-1' } as Citation,
            'trace-1'
          )
        }
      >
        Cite
      </button>
      <button
        type="button"
        data-testid="set-project-action"
        onClick={() =>
          props.onCommandItemAction?.({
            type: 'set-project',
            id: 'proj-1',
            name: 'My Project',
          })
        }
      >
        Set project
      </button>
    </div>
  ),
}));
vi.mock('@/components/chat/aui/ChatRuntimeProvider', () => ({
  ChatRuntimeProvider: ({ children }: { children: React.ReactNode }) =>
    children,
}));
vi.mock('@/components/chat/ChatSidebar', () => ({ ChatSidebar: () => null }));
vi.mock('@/hooks/chat/useChatSession', () => ({
  useChatSession: () => mockUseChatSession(),
}));
vi.mock('@/hooks/chat/useChatStreaming', () => ({
  useChatStreaming: () => ({
    input: '',
    setInput: mockSetInput,
    isLoading: false,
    handleSubmit: vi.fn(),
    handleStop: vi.fn(),
    pendingConfirmation: null,
    handleConfirmation: vi.fn(),
    chatInputRef: { current: null },
    storeIsStreaming: false,
    storeStreamingContent: '',
    storeIsRetrievingRag: false,
    streamingThreadId: null,
  }),
  confirmationBelongsToThread: () => false,
}));
vi.mock('@/hooks/chat/useChatThreadActions', () => ({
  useChatThreadActions: () => ({
    renameDialog: { open: false },
    setRenameDialog: vi.fn(),
    deleteDialog: { open: false },
    setDeleteDialog: vi.fn(),
    bulkDeleteDialog: { open: false },
    setBulkDeleteDialog: vi.fn(),
    handleRenameThread: vi.fn(),
    commitRename: vi.fn(),
    handleDeleteThread: vi.fn(),
    commitDeleteThread: vi.fn(),
    handleBulkDeleteThreads: vi.fn(),
    commitBulkDelete: vi.fn(),
  }),
}));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockRouterPush, replace: mockRouterReplace }),
}));

describe('ChatPage citation panel and project-context actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    act(() => {
      useArtifactPanelStore.setState({
        artifact: null,
        isOpen: false,
        pinned: false,
      });
    });
    mockUseChatSession.mockReturnValue({
      conversations: [{ id: 'thread-1', title: 'Thread 1', updatedAt: 1 }],
      setConversations: vi.fn(),
      activeConversationId: 'thread-1',
      setActiveConversationId: vi.fn(),
      messages: [],
      setMessages: vi.fn(),
      workspace: { id: 'ws-1', name: 'Workspace' },
      dbConversation: { id: 'conv-1', title: 'Default' },
      isInitializing: false,
      initError: null,
      isLoadingMessages: false,
      isHydratedRef: { current: true },
      currentThreadIdFromStore: 'thread-1',
      setCurrentThread: vi.fn(),
      storeMessages: null,
      isAuthenticated: true,
      activeThreadId: 'thread-1',
      displayedMessages: [
        {
          role: 'assistant',
          content: 'Cited answer',
          timestamp: 1,
          runtimeId: 'a1',
          source: 'canonical',
        } as ChatPageMessage,
      ],
      loadOlderMessages: vi.fn(),
      messagePagination: null,
      hasMoreThreads: false,
      loadMoreThreads: vi.fn(),
      mapDbMessageToUiMessage: vi.fn(),
      loadThreadsFromDb: vi.fn(),
    });
  });

  it('focuses clicked citations in the artifact panel with the trace id', () => {
    render(<ChatPage />);

    expect(useArtifactPanelStore.getState().isOpen).toBe(false);

    fireEvent.click(screen.getByTestId('cite-trigger'));

    const s = useArtifactPanelStore.getState();
    expect(s.isOpen).toBe(true);
    expect(s.artifact).toEqual({
      kind: 'citations',
      citations: [{ title: 'Paper A', documentId: 'doc-1' }],
      activeCitationId: 'doc-1',
      traceId: 'trace-1',
    });
    // The page never navigates away — the panel renders in the chat layout.
    expect(mockRouterPush).not.toHaveBeenCalled();
  });

  it('appends a cited source to the composer via the populate-chat-input append bridge', () => {
    render(<ChatPage />);

    fireEvent(
      window,
      new CustomEvent('populate-chat-input', {
        detail: { text: '"Paper A"', mode: 'append' },
      })
    );

    expect(mockSetInput).toHaveBeenCalledTimes(1);
    const updater = mockSetInput.mock.calls[0][0] as (cur: string) => string;
    expect(updater('')).toBe('"Paper A" ');
    expect(updater('existing text')).toBe('existing text "Paper A"');
  });

  it('still replaces the composer for plain-string populate events (follow-up suggestions)', () => {
    render(<ChatPage />);

    fireEvent(
      window,
      new CustomEvent('populate-chat-input', { detail: 'Tell me more' })
    );

    expect(mockSetInput).toHaveBeenCalledWith('Tell me more');
  });

  it('binds the chat to a project via the set-project command action', () => {
    render(<ChatPage />);

    fireEvent.click(screen.getByTestId('set-project-action'));

    expect(mockRouterReplace).toHaveBeenCalledTimes(1);
    const url = mockRouterReplace.mock.calls[0][0] as string;
    expect(url).toContain('/chat?');
    expect(url).toContain('projectId=proj-1');
  });
});
