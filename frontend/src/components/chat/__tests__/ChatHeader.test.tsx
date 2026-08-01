import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('@/components/ui/sidebar', () => ({
  SidebarTrigger: ({ className }: { className?: string }) => (
    <button data-testid="sidebar-trigger" className={className}>
      Toggle
    </button>
  ),
}));

const exportThreadMock = vi.fn();
vi.mock('@/services/export-service', () => ({
  exportThread: (...args: unknown[]) => exportThreadMock(...args),
}));

const toastErrorMock = vi.fn();
vi.mock('react-hot-toast', () => ({
  default: { error: (...args: unknown[]) => toastErrorMock(...args) },
}));

import { ChatHeader } from '../ChatHeader';

describe('ChatHeader', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders the conversation title', () => {
    render(<ChatHeader />);
    const chatElements = screen.getAllByText('Chat');
    expect(chatElements.length).toBeGreaterThanOrEqual(1);
  });

  it('renders a custom chat title when provided', () => {
    render(<ChatHeader chatTitle="ArXiv Literature Review" />);
    expect(screen.getByText('ArXiv Literature Review')).toBeInTheDocument();
  });

  it('does not include a workspace selector (moved to ChatSidebar)', () => {
    render(<ChatHeader />);
    expect(screen.queryByLabelText('Select workspace')).not.toBeInTheDocument();
  });

  it('does not render the command palette affordance (unwired no-op)', () => {
    render(<ChatHeader />);
    expect(screen.queryByLabelText('Search')).not.toBeInTheDocument();
  });

  it('no longer renders a connected-status clock', () => {
    vi.setSystemTime(new Date('2026-03-08T14:30:00'));
    render(<ChatHeader />);
    expect(screen.queryByTitle('Connected')).not.toBeInTheDocument();
  });

  it('does not render the model picker (moved to the composer)', () => {
    render(<ChatHeader />);
    expect(screen.queryByText('GPT-4o')).not.toBeInTheDocument();
  });

  it('shows copy-all and export only when messages exist', () => {
    const { rerender } = render(
      <ChatHeader messages={[]} onCopyAll={() => {}} />
    );
    expect(
      screen.queryByLabelText('Copy all messages')
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Export chat')).not.toBeInTheDocument();

    rerender(
      <ChatHeader
        messages={[{ role: 'user', content: 'hi', timestamp: Date.now() }]}
        onCopyAll={() => {}}
      />
    );
    expect(screen.getByLabelText('Copy all messages')).toBeInTheDocument();
    expect(screen.getByLabelText('Export chat')).toBeInTheDocument();
  });

  describe('export wiring', () => {
    const messages = [
      { role: 'user', content: 'hi', timestamp: 1 },
    ];

    beforeEach(() => {
      // userEvent awaits internal timers; the file-level fake timers hang it.
      exportThreadMock.mockReset();
      exportThreadMock.mockResolvedValue(undefined);
      vi.useRealTimers();
      // downloadFile (the no-thread local fallback) touches URL.createObjectURL.
      (
        URL as unknown as { createObjectURL: () => string }
      ).createObjectURL = () => 'blob:mock';
      (
        URL as unknown as { revokeObjectURL: () => void }
      ).revokeObjectURL = () => {};
    });

    it('uses the backend export (with citations+metadata) when a thread is persisted', async () => {
      const user = userEvent.setup();
      render(<ChatHeader messages={messages} threadId="thread-123" />);

      await user.click(screen.getByLabelText('Export chat'));
      await user.click(screen.getByText('Export as Markdown'));

      expect(exportThreadMock).toHaveBeenCalledTimes(1);
      expect(exportThreadMock).toHaveBeenCalledWith(
        'thread-123',
        'markdown',
        { includeCitations: true, includeMetadata: true }
      );
    });

    it('does not call the backend export for a brand-new chat (no thread)', async () => {
      const user = userEvent.setup();
      render(<ChatHeader messages={messages} threadId={null} />);

      await user.click(screen.getByLabelText('Export chat'));
      await user.click(screen.getByText('Export as Markdown'));

      expect(exportThreadMock).not.toHaveBeenCalled();
    });

    it('disables PDF export when no thread is persisted', async () => {
      const user = userEvent.setup();
      render(<ChatHeader messages={messages} threadId={null} />);

      await user.click(screen.getByLabelText('Export chat'));
      const pdfButton = screen.getByText('Export as PDF').closest('button');
      expect(pdfButton).toBeDisabled();
    });

    it('surfaces a toast on export failure', async () => {
      exportThreadMock.mockReset();
      exportThreadMock.mockRejectedValue(new Error('boom'));

      const user = userEvent.setup();
      render(<ChatHeader messages={messages} threadId="thread-123" />);
      await user.click(screen.getByLabelText('Export chat'));
      await user.click(screen.getByText('Export as Markdown'));

      await vi.waitFor(() => {
        expect(exportThreadMock).toHaveBeenCalled();
      });
      await vi.waitFor(() => {
        expect(toastErrorMock).toHaveBeenCalledWith(
          'Export failed. Please try again.'
        );
      });
    });
  });
});
