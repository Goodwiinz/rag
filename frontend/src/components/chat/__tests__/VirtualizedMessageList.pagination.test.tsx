/**
 * VirtualizedMessageList Pagination / Auto-scroll Tests
 *
 * Pins the newest-first pagination scroll contract:
 * - appending a message (new tail id) snaps the list to the newest row
 * - prepending an older batch (same tail id, greater length) preserves the
 *   scroll anchor and does NOT snap to the bottom
 * - the "Load older messages" affordance calls onLoadOlder
 *
 * react-window's VariableSizeList is mocked so we can observe scrollToItem /
 * resetAfterIndex imperative calls and exercise the row renderer directly.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import React from 'react';

const scrollToItem = vi.fn();
const resetAfterIndex = vi.fn();

// Mock react-window: render every row via the children render-prop and expose
// the imperative handle the component drives (scrollToItem / resetAfterIndex).
vi.mock('react-window', () => {
  const MockList = React.forwardRef(function MockList(
    props: {
      itemCount: number;
      itemSize: (index: number) => number;
      itemData: unknown;
      children: React.ComponentType<{
        index: number;
        style: React.CSSProperties;
        data: unknown;
      }>;
    },
    ref: React.Ref<unknown>
  ) {
    React.useImperativeHandle(ref, () => ({ scrollToItem, resetAfterIndex }));
    const Row = props.children;
    const rows = [];
    for (let i = 0; i < props.itemCount; i++) {
      // Touch itemSize so getItemSize (height lookup) runs for coverage.
      props.itemSize(i);
      rows.push(<Row key={i} index={i} style={{}} data={props.itemData} />);
    }
    return <div data-testid="mock-list">{rows}</div>;
  });
  return { VariableSizeList: MockList };
});

vi.mock('../shared/ChatBubble', () => ({
  ChatBubble: ({ message }: any) => <div>{message.content}</div>,
}));
vi.mock('../shared/InlineAgentSummary', () => ({
  InlineAgentSummary: () => null,
}));

import { VirtualizedMessageList } from '../VirtualizedMessageList';

const makeMsg = (id: string, content = id) => ({
  id,
  role: 'user' as const,
  content,
  timestamp: 1,
});

const baseProps = {
  activeThreadId: 't1',
  isLoading: false,
  storeIsStreaming: false,
  onRegenerate: () => {},
  onCitationClick: () => {},
};

afterEach(() => {
  cleanup();
  scrollToItem.mockClear();
  resetAfterIndex.mockClear();
});

describe('VirtualizedMessageList auto-scroll', () => {
  it('does not snap to bottom on initial mount', () => {
    render(
      <VirtualizedMessageList
        {...baseProps}
        messages={[makeMsg('m1'), makeMsg('m2')]}
      />
    );
    expect(scrollToItem).not.toHaveBeenCalled();
  });

  it('snaps to the newest row when a message is appended', () => {
    const { rerender } = render(
      <VirtualizedMessageList
        {...baseProps}
        messages={[makeMsg('m1'), makeMsg('m2')]}
      />
    );
    scrollToItem.mockClear();

    rerender(
      <VirtualizedMessageList
        {...baseProps}
        messages={[makeMsg('m1'), makeMsg('m2'), makeMsg('m3')]}
      />
    );

    expect(scrollToItem).toHaveBeenCalledWith(2, 'end');
  });

  it('preserves the scroll anchor when older messages are prepended', () => {
    const { rerender } = render(
      <VirtualizedMessageList
        {...baseProps}
        messages={[makeMsg('m3'), makeMsg('m4'), makeMsg('m5')]}
      />
    );
    scrollToItem.mockClear();

    // Prepend older batch: length grows but the tail id (m5) is unchanged.
    rerender(
      <VirtualizedMessageList
        {...baseProps}
        messages={[
          makeMsg('m1'),
          makeMsg('m2'),
          makeMsg('m3'),
          makeMsg('m4'),
          makeMsg('m5'),
        ]}
      />
    );

    expect(scrollToItem).not.toHaveBeenCalled();
  });
});

describe('VirtualizedMessageList load-older affordance', () => {
  it('renders the load-older button and calls onLoadOlder on click', () => {
    const onLoadOlder = vi.fn();
    render(
      <VirtualizedMessageList
        {...baseProps}
        messages={[makeMsg('m1')]}
        hasMore
        isLoadingOlder={false}
        onLoadOlder={onLoadOlder}
      />
    );

    fireEvent.click(screen.getByText('Load older messages'));
    expect(onLoadOlder).toHaveBeenCalledTimes(1);
  });

  it('shows the loading indicator while fetching older messages', () => {
    render(
      <VirtualizedMessageList
        {...baseProps}
        messages={[makeMsg('m1')]}
        hasMore
        isLoadingOlder
        onLoadOlder={() => {}}
      />
    );

    expect(screen.getByText('Loading older messages...')).toBeTruthy();
    expect(screen.queryByText('Load older messages')).toBeNull();
  });
});
