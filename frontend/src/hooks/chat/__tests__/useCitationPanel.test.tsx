import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  useCitationPanel,
  type UseCitationPanelReturn,
} from '@/hooks/chat/useCitationPanel';
import type { Citation } from '@/utils/citationParser';

function setup(): {
  result: { current: UseCitationPanelReturn };
  setInput: ReturnType<typeof vi.fn>;
  focus: ReturnType<typeof vi.fn>;
} {
  const setInput = vi.fn();
  const focus = vi.fn();
  const chatInputRef = { current: { focus } as unknown as HTMLTextAreaElement };
  const { result } = renderHook(() =>
    useCitationPanel({ setInput, chatInputRef })
  );
  return { result, setInput, focus };
}

describe('useCitationPanel', () => {
  it('opens the panel with the clicked citation and trace id', () => {
    const { result } = setup();
    const citations: Citation[] = [
      { title: 'Paper A', documentId: 'doc-1' } as Citation,
    ];

    act(() => {
      result.current.handleCitationClick(citations, citations[0], 'trace-1');
    });

    expect(result.current.isCitationPanelOpen).toBe(true);
    expect(result.current.citationPanelCitations).toEqual(citations);
    expect(result.current.activeCitationId).toBe('doc-1');
    expect(result.current.citationTraceId).toBe('trace-1');
  });

  it('inserts the cited source into the composer, focuses it, and closes the panel', () => {
    const { result, setInput, focus } = setup();
    const citation = { title: 'Paper A', documentId: 'doc-1' } as Citation;

    act(() => {
      result.current.handleCitationClick([citation], citation);
    });
    act(() => {
      result.current.handleCiteSource(citation);
    });

    expect(setInput).toHaveBeenCalledTimes(1);
    const updater = setInput.mock.calls[0][0] as (cur: string) => string;
    expect(updater('')).toBe('"Paper A" ');
    expect(updater('existing text')).toBe('existing text "Paper A"');
    expect(focus).toHaveBeenCalled();
    expect(result.current.isCitationPanelOpen).toBe(false);
  });

  it('opens the panel for a synthetic citation from the open-citation-panel window event', () => {
    const { result } = setup();

    act(() => {
      window.dispatchEvent(
        new CustomEvent('open-citation-panel', {
          detail: { title: 'Doc B', documentId: 'doc-2' } as Citation,
        })
      );
    });

    expect(result.current.isCitationPanelOpen).toBe(true);
    expect(result.current.activeCitationId).toBe('doc-2');
    expect(result.current.citationPanelCitations).toHaveLength(1);
  });

  it('ignores a synthetic citation event with no title', () => {
    const { result } = setup();

    act(() => {
      window.dispatchEvent(
        new CustomEvent('open-citation-panel', {
          detail: { documentId: 'doc-3' } as Citation,
        })
      );
    });

    expect(result.current.isCitationPanelOpen).toBe(false);
  });
});
