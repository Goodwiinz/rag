import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatPage from '../../../../app/(dashboard)/chat/page';
import {
  selectDisplayedMessages,
  type ChatPageMessage,
} from '@/components/chat/shared/cloudMessageView';
import type { ChatMessage } from '@/types/workspace';
import { makeChatPageMessage } from '@/test/chatMessageFactory';

const mockUseChatSession = vi.fn();

vi.mock('@/components/chat', () => ({
  ChatInput: () => <div data-testid="chat-input" />,
  CitationPanel: () => null,
  WelcomeState: () => <div data-testid="welcome-state" />,
}));
vi.mock('@/components/chat/ChatDialogs', () => ({ ChatDialogs: () => null }));
vi.mock('@/components/chat/ChatHeader', () => ({ ChatHeader: () => null }));
vi.mock('@/components/chat/ChatMessageList', () => ({
  ChatMessageList: ({
    messages,
    isLoading,
    storeIsStreaming,
    storeStreamingContent,
    isRetrievingRag,
  }: {
    messages: ChatPageMessage[];
    isLoading?: boolean;
    storeIsStreaming?: boolean;
    storeStreamingContent?: string;
    isRetrievingRag?: boolean;
  }) => (
    <div>
      {messages.map((message) => (
        <p key={`${message.role}:${message.content}`}>{message.content}</p>
      ))}
      <span data-testid="is-loading">{String(isLoading ?? false)}</span>
      <span data-testid="store-is-streaming">
        {String(storeIsStreaming ?? false)}
      </span>
      <span data-testid="store-streaming-content">
        {storeStreamingContent ?? ''}
      </span>
      <span data-testid="is-retrieving-rag">
        {String(isRetrievingRag ?? false)}
      </span>
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
const mockUseChatStreaming = vi.fn();
const DEFAULT_STREAMING_STATE = {
  input: '',
  setInput: vi.fn(),
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
};
vi.mock('@/hooks/chat/useChatStreaming', () => ({
  useChatStreaming: () => mockUseChatStreaming(),
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
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));

const QUERY = 'Find recent arXiv papers on retrieval-augmented generation';

function persisted(
  id: string,
  role: 'user' | 'assistant',
  content: string,
  createdAt: string
): ChatMessage {
  return {
    id,
    thread_id: 'thread-A',
    role,
    content,
    created_at: createdAt,
  } as ChatMessage;
}

function session(
  localMessages: ChatPageMessage[],
  storeMessages: ChatMessage[]
) {
  return {
    conversations: [
      { id: 'thread-A', title: 'A', messages: localMessages, updatedAt: 1 },
    ],
    setConversations: vi.fn(),
    activeConversationId: 'thread-A',
    setActiveConversationId: vi.fn(),
    messages: localMessages,
    setMessages: vi.fn(),
    workspace: { id: 'ws-1', name: 'Workspace' },
    dbConversation: { id: 'conv-1', title: 'Default' },
    isInitializing: false,
    initError: null,
    isLoadingMessages: false,
    activeConversationIdRef: { current: 'thread-A' },
    isHydratedRef: { current: true },
    currentThreadIdFromStore: 'thread-A',
    setCurrentThread: vi.fn(),
    storeMessages,
    addMessageToStore: vi.fn(),
    isAuthenticated: true,
    activeThreadId: 'thread-A',
    displayedMessages: selectDisplayedMessages({
      localMessages,
      storeMessages,
    }),
    loadOlderMessages: vi.fn(),
    messagePagination: null,
    hasMoreThreads: false,
    loadMoreThreads: vi.fn(),
    mapDbMessageToUiMessage: vi.fn(),
    loadThreadsFromDb: vi.fn(),
  };
}

describe('ChatPage completed-turn persistence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseChatStreaming.mockReturnValue(DEFAULT_STREAMING_STATE);
  });

  it('keeps a completed turn visible while an equal-length canonical cache is stale', () => {
    const localMessages: ChatPageMessage[] = [
      makeChatPageMessage({
        id: 'old-user',
        role: 'user',
        content: 'Earlier question',
        timestamp: 1,
      }),
      makeChatPageMessage({
        id: 'old-assistant',
        role: 'assistant',
        content: 'Earlier answer',
        timestamp: 2,
      }),
      makeChatPageMessage({ role: 'user', content: QUERY, timestamp: 3 }),
      makeChatPageMessage({
        id: 'new-assistant',
        runtimeId: 'runtime-new-assistant',
        source: 'optimistic',
        role: 'assistant',
        content: 'Five recent papers',
        timestamp: 4,
      }),
    ];
    const staleCanonical = [
      persisted('old-user', 'user', 'Earlier question', '2026-07-15T00:00:00Z'),
      persisted(
        'old-assistant',
        'assistant',
        'Earlier answer',
        '2026-07-15T00:00:01Z'
      ),
      persisted(
        'stale-user',
        'user',
        'A different cached question',
        '2026-07-15T00:00:02Z'
      ),
      persisted(
        'stale-assistant',
        'assistant',
        'A different cached answer',
        '2026-07-15T00:00:03Z'
      ),
    ];
    mockUseChatSession.mockReturnValue(session(localMessages, staleCanonical));

    render(<ChatPage />);

    expect(screen.getByText(QUERY)).toBeVisible();
    expect(screen.getByText('Five recent papers')).toBeVisible();
  });

  it('renders straight from server-canonical history on a fresh reload with no local overlay', () => {
    const canonicalHistory = [
      persisted('m1', 'user', 'Earlier question', '2026-07-15T00:00:00Z'),
      persisted(
        'm2',
        'assistant',
        'Earlier answer',
        '2026-07-15T00:00:01Z'
      ),
      persisted('m3', 'user', QUERY, '2026-07-15T00:00:02Z'),
      persisted(
        'm4',
        'assistant',
        'Five recent papers',
        '2026-07-15T00:00:03Z'
      ),
    ];
    // A fresh page load: the store is the only source, there is no local
    // optimistic overlay to reconcile against.
    mockUseChatSession.mockReturnValue(session([], canonicalHistory));

    render(<ChatPage />);

    expect(screen.getByText('Earlier question')).toBeVisible();
    expect(screen.getByText('Earlier answer')).toBeVisible();
    expect(screen.getByText(QUERY)).toBeVisible();
    expect(screen.getByText('Five recent papers')).toBeVisible();
  });

  it('does not surface another thread’s in-flight stream on the active thread (CX5)', () => {
    mockUseChatSession.mockReturnValue(
      session(
        [
          makeChatPageMessage({
            id: 'u1',
            role: 'user',
            content: 'Hello',
            timestamp: 1,
          }),
        ],
        []
      )
    );
    mockUseChatStreaming.mockReturnValue({
      ...DEFAULT_STREAMING_STATE,
      isLoading: true,
      storeIsStreaming: true,
      storeStreamingContent: 'Partial answer on a different thread…',
      storeIsRetrievingRag: true,
      // session()'s activeThreadId is 'thread-A' — this turn belongs to a
      // background thread, so none of its streaming state may bleed in.
      streamingThreadId: 'thread-B',
    });

    render(<ChatPage />);

    expect(screen.getByTestId('is-loading')).toHaveTextContent('false');
    expect(screen.getByTestId('store-is-streaming')).toHaveTextContent(
      'false'
    );
    expect(screen.getByTestId('store-streaming-content')).toHaveTextContent(
      ''
    );
    expect(screen.getByTestId('is-retrieving-rag')).toHaveTextContent(
      'false'
    );
  });

  it('surfaces the streaming placeholder only while the active thread is the one streaming', () => {
    mockUseChatSession.mockReturnValue(
      session(
        [
          makeChatPageMessage({
            id: 'u1',
            role: 'user',
            content: 'Hello',
            timestamp: 1,
          }),
        ],
        []
      )
    );
    mockUseChatStreaming.mockReturnValue({
      ...DEFAULT_STREAMING_STATE,
      isLoading: true,
      storeIsStreaming: true,
      storeStreamingContent: 'Partial answer…',
      storeIsRetrievingRag: true,
      streamingThreadId: 'thread-A',
    });

    render(<ChatPage />);

    expect(screen.getByTestId('is-loading')).toHaveTextContent('true');
    expect(screen.getByTestId('store-is-streaming')).toHaveTextContent(
      'true'
    );
    expect(screen.getByTestId('store-streaming-content')).toHaveTextContent(
      'Partial answer…'
    );
    expect(screen.getByTestId('is-retrieving-rag')).toHaveTextContent('true');
  });
});
