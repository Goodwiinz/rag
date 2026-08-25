import { describe, expect, it } from 'vitest';
import { confirmationBelongsToThread } from '@/hooks/chat/useChatStreaming';
import type { PendingConfirmation } from '@/hooks/chat/useChatStreaming';

const pending = (workspaceThreadId: string): PendingConfirmation => ({
  threadId: 'agent-thread-1',
  workspaceThreadId,
  approvalId: 'approval-1',
  confirmation: {},
});

describe('confirmationBelongsToThread', () => {
  it('matches when the displayed thread owns the confirmation', () => {
    expect(confirmationBelongsToThread(pending('t-1'), 't-1')).toBe(true);
  });
  it('rejects a different displayed thread', () => {
    expect(confirmationBelongsToThread(pending('t-1'), 't-2')).toBe(false);
  });
  it('handles the new-chat (null thread) case', () => {
    expect(confirmationBelongsToThread(pending(''), null)).toBe(true);
    expect(confirmationBelongsToThread(pending('t-1'), null)).toBe(false);
  });
  it('rejects null confirmations', () => {
    expect(confirmationBelongsToThread(null, 't-1')).toBe(false);
  });
});
