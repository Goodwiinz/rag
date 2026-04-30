import { Mock, MockedFunction, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, act } from '@/test/test-utils';
import { useProjectStore } from '@/store/projectStore';
import { projectChatService } from '@/services/projectChatService';
import { useProjectChatWidget } from '../useProjectChatWidget';

vi.mock('@/services/projectChatService', () => ({
  projectChatService: {
    startChatFromProject: vi.fn(),
  },
}));

vi.mock('@/store/projectStore', () => ({
  useProjectStore: vi.fn(),
}));

const mockUseProjectStore = useProjectStore as unknown as Mock;
const mockStartChat =
  projectChatService.startChatFromProject as MockedFunction<
    typeof projectChatService.startChatFromProject
  >;

const defaultStoreData = {
  projectDocuments: [
    {
      document_id: 'doc1',
      document: { title: 'Paper A', filename: 'paper-a.pdf' },
    },
    {
      document_id: 'doc2',
      document: { title: 'Paper B', filename: 'paper-b.pdf' },
    },
  ],
  projectNotes: [{ id: 'note1', title: 'Note 1' }],
  bibliography: null,
};

const defaultProps = { projectId: 'proj-1', activeTab: 'documents' as const };

describe('useProjectChatWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProjectStore.mockReturnValue(defaultStoreData);
  });

  it('returns initial state with panel closed', () => {
    const { result } = renderHook(() => useProjectChatWidget(defaultProps));

    expect(result.current.isOpen).toBe(false);
    expect(result.current.messages).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.hasUnread).toBe(false);
  });

  it('toggle opens and closes the panel', () => {
    const { result } = renderHook(() => useProjectChatWidget(defaultProps));

    expect(result.current.isOpen).toBe(false);

    act(() => {
      result.current.toggle();
    });
    expect(result.current.isOpen).toBe(true);

    act(() => {
      result.current.toggle();
    });
    expect(result.current.isOpen).toBe(false);
  });

  it('open() and close() work independently', () => {
    const { result } = renderHook(() => useProjectChatWidget(defaultProps));

    act(() => {
      result.current.open();
    });
    expect(result.current.isOpen).toBe(true);

    act(() => {
      result.current.close();
    });
    expect(result.current.isOpen).toBe(false);
  });

  it('builds context chips from projectDocuments', () => {
    const { result } = renderHook(() => useProjectChatWidget(defaultProps));

    const chips = result.current.contextChips;
    expect(chips).toHaveLength(3);

    const docsChip = chips.find((c) => c.kind === 'documents');
    const notesChip = chips.find((c) => c.kind === 'notes');
    const bibChip = chips.find((c) => c.kind === 'bibliography');

    expect(docsChip).toBeDefined();
    expect(docsChip!.count).toBe(2);

    expect(notesChip).toBeDefined();
    expect(notesChip!.count).toBe(1);

    expect(bibChip).toBeDefined();
    expect(bibChip!.count).toBe(0);
  });

  it('auto-activates chip matching activeTab', () => {
    const { result } = renderHook(() =>
      useProjectChatWidget({ projectId: 'proj-1', activeTab: 'notes' })
    );

    const notesChip = result.current.contextChips.find(
      (c) => c.kind === 'notes'
    );
    expect(notesChip!.active).toBe(true);
  });

  it('toggleChip toggles a specific chip', () => {
    const { result } = renderHook(() =>
      useProjectChatWidget({ projectId: 'proj-1', activeTab: 'chat' })
    );

    // Notes chip starts inactive (default chipStates.notes = false, and activeTab is 'chat')
    expect(
      result.current.contextChips.find((c) => c.kind === 'notes')!.active
    ).toBe(false);

    act(() => {
      result.current.toggleChip('notes');
    });

    expect(
      result.current.contextChips.find((c) => c.kind === 'notes')!.active
    ).toBe(true);

    act(() => {
      result.current.toggleChip('notes');
    });

    expect(
      result.current.contextChips.find((c) => c.kind === 'notes')!.active
    ).toBe(false);
  });

  it('toggleAllChips enables all chips', () => {
    const { result } = renderHook(() =>
      useProjectChatWidget({ projectId: 'proj-1', activeTab: 'chat' })
    );

    act(() => {
      result.current.toggleAllChips(true);
    });

    for (const chip of result.current.contextChips) {
      expect(chip.active).toBe(true);
    }
  });

  it('toggleAllChips disables all chips', () => {
    const { result } = renderHook(() =>
      useProjectChatWidget({ projectId: 'proj-1', activeTab: 'chat' })
    );

    act(() => {
      result.current.toggleAllChips(false);
    });

    for (const chip of result.current.contextChips) {
      expect(chip.active).toBe(false);
    }
  });

  it('sendMessage adds user message and calls API', async () => {
    mockStartChat.mockResolvedValue({
      thread_id: 'thread-1',
      conversation_id: 'conv-1',
      project_thread_id: 'pt-1',
      document_scope: ['doc1'],
    });

    const { result } = renderHook(() => useProjectChatWidget(defaultProps));

    // Set input value
    act(() => {
      result.current.setInputValue('Hello AI');
    });

    // Open the panel so hasUnread is not set
    act(() => {
      result.current.open();
    });

    // Send message
    await act(async () => {
      await result.current.sendMessage();
    });

    // User message should be first
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].role).toBe('user');
    expect(result.current.messages[0].content).toBe('Hello AI');

    // Assistant response should be second
    expect(result.current.messages[1].role).toBe('assistant');

    // API should have been called
    expect(mockStartChat).toHaveBeenCalledWith('proj-1', {
      initial_message: 'Hello AI',
      conversation_id: undefined,
      thread_title: 'Hello AI',
    });

    // Input should be cleared
    expect(result.current.inputValue).toBe('');
    expect(result.current.isStreaming).toBe(false);
  });

  it('sendMessage handles API error gracefully', async () => {
    mockStartChat.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useProjectChatWidget(defaultProps));

    act(() => {
      result.current.setInputValue('Hello AI');
    });

    await act(async () => {
      await result.current.sendMessage();
    });

    // Should have user message + error message
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].role).toBe('user');
    expect(result.current.messages[1].role).toBe('assistant');
    expect(result.current.messages[1].content).toBe(
      'Sorry, something went wrong. Please try again.'
    );
    expect(result.current.isStreaming).toBe(false);
  });

  it('sendMessage does nothing when input is empty', async () => {
    const { result } = renderHook(() => useProjectChatWidget(defaultProps));

    // Input is empty by default
    await act(async () => {
      await result.current.sendMessage();
    });

    expect(result.current.messages).toHaveLength(0);
    expect(mockStartChat).not.toHaveBeenCalled();
  });

  it('clearMessages resets messages and thread', async () => {
    mockStartChat.mockResolvedValue({
      thread_id: 'thread-1',
      conversation_id: 'conv-1',
      project_thread_id: 'pt-1',
      document_scope: ['doc1'],
    });

    const { result } = renderHook(() => useProjectChatWidget(defaultProps));

    // Add a message first
    act(() => {
      result.current.setInputValue('Hello');
    });

    await act(async () => {
      await result.current.sendMessage();
    });

    expect(result.current.messages.length).toBeGreaterThan(0);
    expect(result.current.threadId).toBe('thread-1');
    expect(result.current.conversationId).toBe('conv-1');

    // Clear messages
    act(() => {
      result.current.clearMessages();
    });

    expect(result.current.messages).toEqual([]);
    expect(result.current.threadId).toBeNull();
    expect(result.current.conversationId).toBeNull();
  });

  it('hasUnread is set when panel is closed and message arrives', async () => {
    mockStartChat.mockResolvedValue({
      thread_id: 'thread-1',
      conversation_id: 'conv-1',
      project_thread_id: 'pt-1',
      document_scope: ['doc1'],
    });

    const { result } = renderHook(() => useProjectChatWidget(defaultProps));

    // Panel is closed by default
    expect(result.current.isOpen).toBe(false);

    act(() => {
      result.current.setInputValue('Hello');
    });

    await act(async () => {
      await result.current.sendMessage();
    });

    expect(result.current.hasUnread).toBe(true);
  });

  it('opening panel clears hasUnread', async () => {
    mockStartChat.mockResolvedValue({
      thread_id: 'thread-1',
      conversation_id: 'conv-1',
      project_thread_id: 'pt-1',
      document_scope: ['doc1'],
    });

    const { result } = renderHook(() => useProjectChatWidget(defaultProps));

    // Generate unread state: panel closed + message
    act(() => {
      result.current.setInputValue('Hello');
    });

    await act(async () => {
      await result.current.sendMessage();
    });

    expect(result.current.hasUnread).toBe(true);

    // Opening the panel should clear hasUnread
    act(() => {
      result.current.open();
    });

    expect(result.current.hasUnread).toBe(false);
  });
});
