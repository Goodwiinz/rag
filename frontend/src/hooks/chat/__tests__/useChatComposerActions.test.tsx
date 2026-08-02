import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  useChatComposerActions,
  type UseChatComposerActionsReturn,
} from '@/hooks/chat/useChatComposerActions';
import { makeChatPageMessage } from '@/test/chatMessageFactory';
import type { Workspace } from '@/types/workspace';

const toastErrorMock = vi.fn();
vi.mock('react-hot-toast', () => ({
  default: { error: (...args: unknown[]) => toastErrorMock(...args) },
}));

const uploadDocumentMock = vi.fn();
vi.mock('@/services/enhancedDocumentService', () => ({
  enhancedDocumentService: {
    uploadDocument: (...args: unknown[]) => uploadDocumentMock(...args),
  },
}));

const WORKSPACE = { id: 'ws-1' } as unknown as Workspace;

function setup(overrides: Record<string, unknown> = {}): {
  result: { current: UseChatComposerActionsReturn };
  setInput: ReturnType<typeof vi.fn>;
  handleSubmit: ReturnType<typeof vi.fn>;
} {
  const setInput = vi.fn();
  const handleSubmit = vi.fn();
  const params = {
    workspace: WORKSPACE,
    setInput,
    handleSubmit,
    isLoading: false,
    storeIsStreaming: false,
    displayedMessages: [
      makeChatPageMessage({ id: 'u1', role: 'user', content: 'first turn', timestamp: 1 }),
      makeChatPageMessage({ id: 'a1', role: 'assistant', content: 'first reply', timestamp: 2 }),
    ],
    ...overrides,
  };
  const { result } = renderHook(() => useChatComposerActions(params));
  return { result, setInput, handleSubmit };
}

describe('useChatComposerActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('handleRegenerate is a no-op while a turn is streaming', () => {
    const { result, handleSubmit } = setup({ storeIsStreaming: true });

    act(() => {
      result.current.handleRegenerate(1);
    });

    expect(handleSubmit).not.toHaveBeenCalled();
  });

  it('handleRegenerate re-sends the prior user turn', async () => {
    const { result, handleSubmit, setInput } = setup();

    act(() => {
      result.current.handleRegenerate(1);
    });
    // handleSubmit is deferred via setTimeout(0) to dodge the stale-closure bug.
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(setInput).toHaveBeenCalledWith('first turn');
    expect(handleSubmit).toHaveBeenCalledWith('first turn', []);
  });

  it('retryLast regenerates the most recent assistant turn', async () => {
    const { result, handleSubmit } = setup();

    act(() => {
      result.current.retryLast();
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(handleSubmit).toHaveBeenCalledWith('first turn', []);
  });

  describe('handleEditUserMessage', () => {
    function setupFour(): ReturnType<typeof setup> {
      return setup({
        displayedMessages: [
          makeChatPageMessage({ id: 'u1', role: 'user', content: 'first', timestamp: 1 }),
          makeChatPageMessage({ id: 'a1', role: 'assistant', content: 'reply 1', timestamp: 2 }),
          makeChatPageMessage({ id: 'u2', role: 'user', content: 'second', timestamp: 3 }),
          makeChatPageMessage({ id: 'a2', role: 'assistant', content: 'reply 2', timestamp: 4 }),
        ],
      });
    }

    it('is a no-op while a turn is streaming', () => {
      const { result, handleSubmit } = setup({
        storeIsStreaming: true,
        displayedMessages: [
          makeChatPageMessage({ id: 'u1', role: 'user', content: 'first', timestamp: 1 }),
          makeChatPageMessage({ id: 'a1', role: 'assistant', content: 'reply 1', timestamp: 2 }),
          makeChatPageMessage({ id: 'u2', role: 'user', content: 'second', timestamp: 3 }),
          makeChatPageMessage({ id: 'a2', role: 'assistant', content: 'reply 2', timestamp: 4 }),
        ],
      });
      act(() => {
        result.current.handleEditUserMessage(2, 'edited');
      });
      expect(handleSubmit).not.toHaveBeenCalled();
    });

    it('is a no-op when the new content is blank', () => {
      const { result, handleSubmit } = setupFour();
      act(() => {
        result.current.handleEditUserMessage(2, '   ');
      });
      expect(handleSubmit).not.toHaveBeenCalled();
    });

    it('re-sends the edited text with history truncated before the edited message', async () => {
      const { result, handleSubmit, setInput } = setupFour();

      act(() => {
        result.current.handleEditUserMessage(2, 'edited second turn');
      });
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      expect(setInput).toHaveBeenCalledWith('edited second turn');
      // History passed to handleSubmit is everything BEFORE index 2 (u1, a1).
      expect(handleSubmit).toHaveBeenCalledTimes(1);
      const [, historyOverride] = handleSubmit.mock.calls[0];
      expect(historyOverride).toHaveLength(2);
      expect(historyOverride.map((m: { content: string }) => m.content)).toEqual([
        'first',
        'reply 1',
      ]);
    });
  });

  it('submit forwards to handleSubmit without arguments', () => {
    const { result, handleSubmit } = setup();

    act(() => {
      result.current.submit();
    });

    expect(handleSubmit).toHaveBeenCalledWith();
  });

  it('handleAttach uploads every file and reports partial failure', async () => {
    uploadDocumentMock
      .mockResolvedValueOnce({ response: { document_id: 'doc-1' } })
      .mockRejectedValueOnce(new Error('boom'));
    const { result } = setup();
    const files = [
      new File(['a'], 'a.pdf'),
      new File(['b'], 'b.pdf'),
    ] as unknown as FileList;

    await act(async () => {
      await result.current.handleAttach(files);
    });

    expect(uploadDocumentMock).toHaveBeenCalledTimes(2);
    expect(toastErrorMock).toHaveBeenCalledWith('Upload failed for b.pdf.');
  });

  it('handleAttach refuses to upload without a workspace', async () => {
    const { result } = setup({ workspace: null });

    await act(async () => {
      await result.current.handleAttach([
        new File(['a'], 'a.pdf'),
      ] as unknown as FileList);
    });

    expect(uploadDocumentMock).not.toHaveBeenCalled();
    expect(toastErrorMock).toHaveBeenCalledWith(
      'No workspace available — attachment was not uploaded.'
    );
  });
});
