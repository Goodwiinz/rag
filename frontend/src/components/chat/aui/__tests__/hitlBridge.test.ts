import { describe, expect, it, beforeEach, vi } from 'vitest';
import { useHitlBridge, HITL_APPROVAL_TOOL } from '../hitlBridge';

describe('useHitlBridge', () => {
  beforeEach(() => useHitlBridge.getState().close());

  it('exposes a stable synthetic approval tool name', () => {
    expect(HITL_APPROVAL_TOOL).toBe('__nous_approval__');
  });

  it('opens a gate, routes respond, tracks responding, and closes', () => {
    const respond = vi.fn();
    useHitlBridge
      .getState()
      .open(
        { id: 'thread-1', toolName: 'ingest_arxiv_papers', args: { n: 1 } },
        respond
      );

    const opened = useHitlBridge.getState();
    expect(opened.request).toEqual({
      id: 'thread-1',
      toolName: 'ingest_arxiv_papers',
      args: { n: 1 },
    });
    expect(opened.isResponding).toBe(false);

    useHitlBridge.getState().setResponding(true);
    expect(useHitlBridge.getState().isResponding).toBe(true);

    // The renderer resolves through respond (bound to handleConfirmation).
    useHitlBridge.getState().respond?.(true);
    expect(respond).toHaveBeenCalledWith(true);

    useHitlBridge.getState().close();
    const closed = useHitlBridge.getState();
    expect(closed.request).toBeNull();
    expect(closed.respond).toBeNull();
    expect(closed.isResponding).toBe(false);
  });
});
