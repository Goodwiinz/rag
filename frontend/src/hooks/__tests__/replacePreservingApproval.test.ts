/**
 * The transcript-replace guard behind the HITL approval card.
 *
 * Live incident: a `create_project` turn raised a HITL interrupt, the SSE
 * stream ended, and the card the user had to act on was gone — while
 * `pendingConfirmation` stayed set, so `ChatSurface` kept the composer
 * disabled. Unrecoverable without a reload; retyping discarded the interrupt
 * server-side ("Abandoned HITL interrupt silently dropped").
 *
 * Two paths did it, both by replacing the whole array with a snapshot taken
 * *before* the turn: the confirmation exit, and the empty-replay unwind that a
 * spurious auto-resume triggered on every HITL pause.
 */
import { describe, expect, it } from 'vitest';

import { replacePreservingApproval } from '@/hooks/chat/useChatStreaming';
import type { ChatPageMessage } from '@/hooks/chat/chatTypes';

const msg = (id: string, extra: Partial<ChatPageMessage> = {}): ChatPageMessage =>
  ({
    runtimeId: id,
    source: 'local-only',
    role: 'assistant',
    content: '',
    timestamp: 0,
    ...extra,
  }) as ChatPageMessage;

const approval = (id = 'approval:w1:t1'): ChatPageMessage =>
  msg(id, {
    pendingApproval: {
      id: 'gate-1',
      tools: [{ name: 'create_project', args: {} }],
    },
  });

describe('replacePreservingApproval', () => {
  it('carries a pending approval through a whole-array replace', () => {
    const prev = [msg('user-1'), approval()];
    const next = [msg('user-1')]; // the pre-turn snapshot: no approval

    const out = replacePreservingApproval(next)(prev);

    expect(out.filter((m) => m.pendingApproval)).toHaveLength(1);
  });

  it('does not duplicate an approval the replacement already contains', () => {
    const prev = [approval()];
    const next = [msg('user-1'), approval()];

    const out = replacePreservingApproval(next)(prev);

    expect(out.filter((m) => m.pendingApproval)).toHaveLength(1);
  });

  it('is a plain replace when no approval is pending', () => {
    const prev = [msg('stale-placeholder')];
    const next = [msg('user-1'), msg('assistant-1')];

    expect(replacePreservingApproval(next)(prev)).toEqual(next);
  });

  it('keeps the replacement ordering, appending the carried card last', () => {
    const prev = [approval()];
    const next = [msg('user-1'), msg('assistant-1')];

    const out = replacePreservingApproval(next)(prev);

    expect(out.slice(0, 2)).toEqual(next);
    expect(out[2]?.pendingApproval).toBeTruthy();
  });
});
