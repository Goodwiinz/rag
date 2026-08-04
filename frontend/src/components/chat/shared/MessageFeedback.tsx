'use client';

import { useCallback, useState } from 'react';
import toast from 'react-hot-toast';
import { Check, ThumbsDown, ThumbsUp } from 'lucide-react';

import { useChatStore } from '@/store/chat-store';
import { cn } from '@/lib/utils';

export interface MessageFeedbackValue {
  rating: number | null;
  comment: string | null;
}

/** Optional failure categories offered on a negative rating. */
const FAILURE_CATEGORIES = [
  'Not helpful',
  'Incorrect or unsupported',
  'Missing or wrong sources',
  'Too slow',
  'Other',
] as const;

function choiceFromRating(rating: number | null | undefined): 'up' | 'down' | null {
  if (rating == null) return null;
  if (rating >= 4) return 'up';
  if (rating <= 2) return 'down';
  return null;
}

export interface MessageFeedbackProps {
  messageId: string;
  feedback?: MessageFeedbackValue | null;
}

/**
 * Per-response feedback control for committed assistant messages.
 *
 * Thumbs up/down persist immediately to chat_messages.feedback_rating via the
 * store's updateMessageFeedback action (PATCH /messages/{id}). A thumbs-down
 * optionally expands a failure-category + note form (feedback_text) — the
 * category is optional, so a bare down-vote still records. The control is
 * self-contained: it owns its optimistic state and reverts on failure, so it
 * needs no callback threading through the message-render layers (the data
 * rides the existing message prop; only the persisted id is required).
 */
export function MessageFeedback({
  messageId,
  feedback,
}: MessageFeedbackProps): React.JSX.Element {
  const updateMessageFeedback = useChatStore(
    (state) => state.updateMessageFeedback
  );

  const [choice, setChoice] = useState<'up' | 'down' | null>(() =>
    choiceFromRating(feedback?.rating)
  );
  const [showForm, setShowForm] = useState(false);
  const [category, setCategory] = useState<string>('');
  const [note, setNote] = useState<string>(feedback?.comment ?? '');
  const [submitting, setSubmitting] = useState(false);

  const persist = useCallback(
    async (
      next: 'up' | 'down' | null,
      payload: { feedback_rating: number | null; feedback_text?: string | null }
    ) => {
      const prev = choice;
      setSubmitting(true);
      try {
        const updated = await updateMessageFeedback(messageId, payload);
        if (!updated) {
          // The store action logs + sets a generic error; revert the toggle.
          setChoice(prev);
          toast.error('Could not save your feedback.');
        } else {
          setChoice(next);
        }
      } catch {
        setChoice(prev);
        toast.error('Could not save your feedback.');
      } finally {
        setSubmitting(false);
      }
    },
    [choice, messageId, updateMessageFeedback]
  );

  const handleRate = useCallback(
    (next: 'up' | 'down') => {
      if (submitting) return;
      // Toggle off → clear the rating entirely.
      if (choice === next) {
        void persist(null, { feedback_rating: null, feedback_text: null });
        setShowForm(false);
        return;
      }
      if (next === 'up') {
        setShowForm(false);
        void persist('up', { feedback_rating: 5, feedback_text: null });
      } else {
        // Bare down-vote records immediately; the form only enriches the text.
        setShowForm(true);
        void persist('down', { feedback_rating: 1 });
      }
    },
    [choice, persist, submitting]
  );

  const handleSubmitCategory = useCallback(() => {
    const text = [category, note.trim()].filter(Boolean).join(' — ') || null;
    void persist('down', { feedback_rating: 1, feedback_text: text });
    setShowForm(false);
  }, [category, note, persist]);

  return (
    <div
      className="nous-msg-feedback inline-flex flex-col items-start gap-1.5"
      role="group"
      aria-label="Rate this response"
    >
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => handleRate('up')}
          disabled={submitting}
          aria-pressed={choice === 'up'}
          aria-label="Good response"
          title="Good response"
          className={cn(
            'nous-msg-action',
            choice === 'up' && 'text-(--nous-sol) dark:text-(--nous-helios)'
          )}
        >
          {choice === 'up' ? (
            <ThumbsUp className="h-3.5 w-3.5 fill-current" />
          ) : (
            <ThumbsUp className="h-3.5 w-3.5" />
          )}
        </button>
        <button
          type="button"
          onClick={() => handleRate('down')}
          disabled={submitting}
          aria-pressed={choice === 'down'}
          aria-label="Poor response"
          title="Poor response"
          className={cn(
            'nous-msg-action',
            choice === 'down' && 'text-(--nous-mars)'
          )}
        >
          {choice === 'down' ? (
            <ThumbsDown className="h-3.5 w-3.5 fill-current" />
          ) : (
            <ThumbsDown className="h-3.5 w-3.5" />
          )}
        </button>
      </div>

      {showForm && choice === 'down' && (
        <div
          className="mt-1 w-full max-w-sm rounded-lg border border-(--nous-border-1) bg-(--nous-bg-2) p-2 text-left"
          // role/form handled by inner controls; this wrapper is layout only.
        >
          <label
            className="nous-overline mb-1 block text-(--nous-fg-3)"
            htmlFor={`fb-category-${messageId}`}
          >
            What went wrong? (optional)
          </label>
          <select
            id={`fb-category-${messageId}`}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="mb-1.5 w-full rounded-md border border-(--nous-border-1) bg-(--nous-bg-1) px-2 py-1 text-[12px] text-(--nous-fg-1)"
          >
            <option value="">Choose a reason…</option>
            {FAILURE_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            aria-label="Feedback note (optional)"
            placeholder="Add a note (optional)"
            rows={2}
            className="w-full resize-none rounded-md border border-(--nous-border-1) bg-(--nous-bg-1) px-2 py-1 text-[12px] text-(--nous-fg-1)"
          />
          <div className="mt-1.5 flex justify-end">
            <button
              type="button"
              onClick={handleSubmitCategory}
              disabled={submitting}
              className="inline-flex items-center gap-1 rounded-md bg-(--nous-sol) px-2.5 py-1 text-[11px] font-semibold text-(--nous-erebus) hover:opacity-90 disabled:opacity-50 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-(--nous-sol) focus-visible:ring-offset-1"
            >
              <Check className="h-3 w-3" />
              Submit feedback
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
