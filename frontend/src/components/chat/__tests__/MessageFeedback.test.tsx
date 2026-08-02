import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const updateMessageFeedbackMock = vi.fn();
vi.mock('@/store/chat-store', () => ({
  // The component subscribes via a selector; resolve it against our spy.
  useChatStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ updateMessageFeedback: updateMessageFeedbackMock }),
}));

const toastErrorMock = vi.fn();
vi.mock('react-hot-toast', () => ({
  default: { error: (...args: unknown[]) => toastErrorMock(...args) },
}));

import { MessageFeedback } from '../shared/MessageFeedback';

describe('MessageFeedback', () => {
  beforeEach(() => {
    updateMessageFeedbackMock.mockReset();
    // The store action resolves to the updated message on success.
    updateMessageFeedbackMock.mockResolvedValue({ id: 'm1', thread_id: 't1' });
    toastErrorMock.mockReset();
  });

  it('renders thumbs up/down controls', () => {
    render(<MessageFeedback messageId="m1" />);
    expect(screen.getByLabelText('Good response')).toBeInTheDocument();
    expect(screen.getByLabelText('Poor response')).toBeInTheDocument();
  });

  it('thumbs-up persists a positive rating and clears prior text', async () => {
    const user = userEvent.setup();
    render(<MessageFeedback messageId="m1" />);

    await user.click(screen.getByLabelText('Good response'));

    expect(updateMessageFeedbackMock).toHaveBeenCalledWith('m1', {
      feedback_rating: 5,
      feedback_text: null,
    });
    expect(screen.getByLabelText('Good response')).toHaveAttribute(
      'aria-pressed',
      'true'
    );
  });

  it('thumbs-down persists a negative rating and reveals the failure-category form', async () => {
    const user = userEvent.setup();
    render(<MessageFeedback messageId="m1" />);

    await user.click(screen.getByLabelText('Poor response'));

    expect(updateMessageFeedbackMock).toHaveBeenCalledWith('m1', {
      feedback_rating: 1,
    });
    // The optional failure-category disclosure appears.
    expect(screen.getByText(/what went wrong/i)).toBeInTheDocument();
  });

  it('gives the note field an accessible name (placeholder alone is not one)', async () => {
    const user = userEvent.setup();
    render(<MessageFeedback messageId="m1" />);

    await user.click(screen.getByLabelText('Poor response'));

    expect(
      screen.getByLabelText('Feedback note (optional)')
    ).toBeInstanceOf(HTMLTextAreaElement);
  });

  it('toggling the same thumb off clears the rating', async () => {
    const user = userEvent.setup();
    render(<MessageFeedback messageId="m1" feedback={{ rating: 5, comment: null }} />);

    // Initial state reflects the persisted rating.
    expect(screen.getByLabelText('Good response')).toHaveAttribute(
      'aria-pressed',
      'true'
    );

    await user.click(screen.getByLabelText('Good response'));

    expect(updateMessageFeedbackMock).toHaveBeenCalledWith('m1', {
      feedback_rating: null,
      feedback_text: null,
    });
  });

  it('reverts and toasts when the store action reports failure', async () => {
    updateMessageFeedbackMock.mockReset();
    updateMessageFeedbackMock.mockResolvedValue(null); // null => store logged an error
    const user = userEvent.setup();
    render(<MessageFeedback messageId="m1" />);

    await user.click(screen.getByLabelText('Good response'));

    await vi.waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith(
        'Could not save your feedback.'
      );
    });
    // Reverted: not pressed.
    expect(screen.getByLabelText('Good response')).toHaveAttribute(
      'aria-pressed',
      'false'
    );
  });
});
