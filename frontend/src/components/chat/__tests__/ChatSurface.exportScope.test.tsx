/**
 * ChatSurface export/copy scoping.
 *
 * The header's export + copy-all controls are gated on `isStreaming`, which
 * must mean "the DISPLAYED thread's transcript is still growing". The surface
 * used to pass `isStreamingThisThread || isLoading`; `isLoading` is
 * session-scoped (one streaming hook per surface) and stays true for the whole
 * turn, so a background thread's turn disabled export on an unrelated,
 * already-complete thread. These tests FAIL against that behavior.
 */

import { render } from '@testing-library/react';
import type { ComponentProps, ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { ChatSurface } from '@/components/chat/ChatSurface';
import type { UseChatSessionReturn } from '@/hooks/chat/useChatSession';
import type { UseChatStreamingReturn } from '@/hooks/chat/useChatStreaming';
import type { UseChatThreadActionsReturn } from '@/hooks/chat/useChatThreadActions';
import type { UseChatDrawerReturn } from '@/hooks/chat/useChatDrawer';
import type { UseCitationPanelReturn } from '@/hooks/chat/useCitationPanel';
import type { UseChatComposerActionsReturn } from '@/hooks/chat/useChatComposerActions';
import type { UseSlashCommandsReturn } from '@/hooks/chat/useSlashCommands';

let headerProps: { isStreaming?: boolean };

vi.mock('@/components/chat', () => ({
  ChatInput: () => <div data-testid="chat-input" />,
  CitationPanel: () => <div data-testid="citation-panel" />,
}));

vi.mock('@/components/chat/aui/ChatRuntimeProvider', () => ({
  ChatRuntimeProvider: (props: { children?: ReactNode }) => (
    <div data-testid="runtime">{props.children}</div>
  ),
}));

vi.mock('@/components/chat/ChatTranscriptState', () => ({
  ChatTranscriptState: () => <div data-testid="transcript" />,
}));

vi.mock('@/components/chat/ChatDialogs', () => ({
  ChatDialogs: () => <div data-testid="chat-dialogs" />,
}));

vi.mock('@/components/chat/ChatHeader', () => ({
  ChatHeader: (props: { isStreaming?: boolean }) => {
    headerProps = props;
    return <div data-testid="chat-header" />;
  },
}));

vi.mock('@/components/chat/ChatSidebar', () => ({
  ChatSidebar: () => <div data-testid="chat-sidebar" />,
}));

vi.mock('@/hooks/chat/useChatStreaming', () => ({
  confirmationBelongsToThread: () => false,
}));

const makeSession = (
  overrides: Partial<UseChatSessionReturn> = {}
): UseChatSessionReturn =>
  ({
    conversations: [],
    workspace: null,
    activeThreadId: 'thread-B',
    displayedMessages: [],
    isAuthenticated: true,
    isInitializing: false,
    initError: null,
    isLoadingMessages: false,
    hasMoreThreads: false,
    loadMoreThreads: vi.fn(),
    loadOlderMessages: vi.fn(),
    messagePagination: {},
    ...overrides,
  }) as unknown as UseChatSessionReturn;

const makeProps = (
  session: UseChatSessionReturn,
  streamingOverrides: Partial<UseChatStreamingReturn> = {}
): ComponentProps<typeof ChatSurface> => ({
  session,
  streaming: {
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
    ...streamingOverrides,
  } as unknown as UseChatStreamingReturn,
  threadActions: {
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
  } as unknown as UseChatThreadActionsReturn,
  drawer: {
    isOpen: false,
    closeDrawer: vi.fn(),
    toggleDrawer: vi.fn(),
    drawerRef: { current: null },
    handleDrawerKeyDown: vi.fn(),
  } as unknown as UseChatDrawerReturn,
  citationPanel: {
    isCitationPanelOpen: false,
    setIsCitationPanelOpen: vi.fn(),
    citationPanelCitations: [],
    activeCitationId: null,
    citationTraceId: null,
    handleCitationClick: vi.fn(),
    handleCiteSource: vi.fn(),
  } as unknown as UseCitationPanelReturn,
  composerActions: {
    handleAttach: vi.fn(),
    handleRegenerate: vi.fn(),
    handleEditUserMessage: vi.fn(),
  } as unknown as UseChatComposerActionsReturn,
  slashCommands: {
    commandOutputs: [],
    handleSlashCommand: vi.fn(),
    handleCommandItemAction: vi.fn(),
    submitMessage: vi.fn(),
    startNewChat: vi.fn(),
  } as unknown as UseSlashCommandsReturn,
  enableRAG: true,
  setEnableRAG: vi.fn(),
  onSelectThread: vi.fn(),
});

describe('ChatSurface export gating is scoped to the displayed thread', () => {
  it('keeps export enabled while a BACKGROUND thread streams', () => {
    render(
      <ChatSurface
        {...makeProps(makeSession({ activeThreadId: 'thread-B' }), {
          // Thread A owns the live turn; isLoading is the same session-level
          // flag that used to leak across threads.
          isLoading: true,
          storeIsStreaming: true,
          streamingThreadId: 'thread-A',
        })}
      />
    );

    expect(headerProps.isStreaming).toBe(false);
  });

  it('keeps export enabled during a background thread pre-first-token window', () => {
    // isLoading is already true but no SSE turn has stamped
    // streamingThreadId yet. The send was initiated on thread A (which was
    // displayed at the false->true edge), so thread B must stay exportable.
    const { rerender } = render(
      <ChatSurface
        {...makeProps(makeSession({ activeThreadId: 'thread-A' }))}
      />
    );
    expect(headerProps.isStreaming).toBe(false);

    // Thread A submits: pre-first-token, still displayed -> blocked.
    rerender(
      <ChatSurface
        {...makeProps(makeSession({ activeThreadId: 'thread-A' }), {
          isLoading: true,
        })}
      />
    );
    expect(headerProps.isStreaming).toBe(true);

    // User switches to the complete thread B while A is still pre-token.
    rerender(
      <ChatSurface
        {...makeProps(makeSession({ activeThreadId: 'thread-B' }), {
          isLoading: true,
        })}
      />
    );
    expect(headerProps.isStreaming).toBe(false);
  });

  it('disables export while the DISPLAYED thread streams', () => {
    render(
      <ChatSurface
        {...makeProps(makeSession({ activeThreadId: 'thread-A' }), {
          isLoading: true,
          storeIsStreaming: true,
          streamingThreadId: 'thread-A',
        })}
      />
    );

    expect(headerProps.isStreaming).toBe(true);
  });

  it('leaves export enabled on an idle thread with nothing in flight', () => {
    render(<ChatSurface {...makeProps(makeSession())} />);

    expect(headerProps.isStreaming).toBe(false);
  });
});
