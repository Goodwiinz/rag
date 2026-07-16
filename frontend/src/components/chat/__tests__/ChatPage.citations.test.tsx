/**
 * Characterization tests for ChatPage's citation panel wiring and the
 * project-context command action (Task 5.1) — currently orchestrated
 * directly inside page.tsx, ahead of Task 5.2's extraction into
 * useCitationPanel / useSlashCommands.
 */
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatPage from '../../../../app/(dashboard)/chat/page';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import type { CommandAction } from '@/components/chat/commandOutput';
import type { Citation } from '@/utils/citationParser';

const mockUseChatSession = vi.fn();
const mockRouterPush = vi.fn();
const mockRouterReplace = vi.fn();
const mockSetInput = vi.fn();

vi.mock('@/components/chat', () => ({
  ChatInput: () => <div data-testid="chat-input" />,
  CitationPanel: (props: {
    citations: Citation[];
    isOpen: boolean;
    activeCitationId?: string;
    diagnosticsTraceId?: string;
    onClose: () => void;
    onCite: (citation: Citation) => void;
  }) => (
    <div data-testid="citation-panel" data-open={String(props.isOpen)}>
      <span data-testid="citation-panel-trace">
        {props.diagnosticsTraceId ?? ''}
      </span>
      <span data-testid="citation-panel-active">
        {props.activeCitationId ?? ''}
      </span>
      <span data-testid="citation-panel-count">{props.citations.length}</span>
      <button
        type="button"
        data-testid="citation-panel-close"
        onClick={props.onClose}
      >
        Close
      </button>
      <button
        type="button"
        data-testid="citation-panel-cite"
        onClick={() => props.citations[0] && props.onCite(props.citations[0])}
      >
        Cite
      </button>
    </div>
  ),
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

  it('opens the citation panel with the clicked citation and trace id', () => {
    render(<ChatPage />);

    expect(screen.getByTestId('citation-panel')).toHaveAttribute(
      'data-open',
      'false'
    );

    fireEvent.click(screen.getByTestId('cite-trigger'));

    expect(screen.getByTestId('citation-panel')).toHaveAttribute(
      'data-open',
      'true'
    );
    expect(screen.getByTestId('citation-panel-trace')).toHaveTextContent(
      'trace-1'
    );
    expect(screen.getByTestId('citation-panel-active')).toHaveTextContent(
      'doc-1'
    );
    expect(screen.getByTestId('citation-panel-count')).toHaveTextContent('1');
  });

  it('closes the citation panel via onClose', () => {
    render(<ChatPage />);

    fireEvent.click(screen.getByTestId('cite-trigger'));
    expect(screen.getByTestId('citation-panel')).toHaveAttribute(
      'data-open',
      'true'
    );

    fireEvent.click(screen.getByTestId('citation-panel-close'));
    expect(screen.getByTestId('citation-panel')).toHaveAttribute(
      'data-open',
      'false'
    );
  });

  it('inserts the cited source into the composer and closes the panel', () => {
    render(<ChatPage />);

    fireEvent.click(screen.getByTestId('cite-trigger'));
    fireEvent.click(screen.getByTestId('citation-panel-cite'));

    expect(mockSetInput).toHaveBeenCalledTimes(1);
    const updater = mockSetInput.mock.calls[0][0] as (cur: string) => string;
    expect(updater('')).toBe('"Paper A" ');
    expect(updater('existing text')).toBe('existing text "Paper A"');

    expect(screen.getByTestId('citation-panel')).toHaveAttribute(
      'data-open',
      'false'
    );
  });

  it('opens the panel for a synthetic citation from the layout context-rail bridge event', () => {
    render(<ChatPage />);

    fireEvent(
      window,
      new CustomEvent('open-citation-panel', {
        detail: { title: 'Doc B', documentId: 'doc-2' } as Citation,
      })
    );

    expect(screen.getByTestId('citation-panel')).toHaveAttribute(
      'data-open',
      'true'
    );
    expect(screen.getByTestId('citation-panel-active')).toHaveTextContent(
      'doc-2'
    );
    expect(screen.getByTestId('citation-panel-count')).toHaveTextContent('1');
  });

  it('ignores a synthetic citation event with no title', () => {
    render(<ChatPage />);

    fireEvent(
      window,
      new CustomEvent('open-citation-panel', {
        detail: { documentId: 'doc-3' } as Citation,
      })
    );

    expect(screen.getByTestId('citation-panel')).toHaveAttribute(
      'data-open',
      'false'
    );
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
