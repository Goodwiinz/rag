import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  filterCommands,
  isSlashTrigger,
  type SlashCommand,
} from './slashCommands';

export interface SlashCommandMenuState {
  /** Whether the menu should be shown for the current input value. */
  isOpen: boolean;
  /** Commands matching the current "/query". */
  filtered: SlashCommand[];
  /** Index into `filtered` of the keyboard-highlighted row. */
  highlightedIndex: number;
  setHighlightedIndex: (index: number) => void;
  /** Move the highlight by `delta`, wrapping around the list. */
  move: (delta: number) => void;
  /** Hide the menu without clearing the typed token; re-arms on next keystroke. */
  dismiss: () => void;
}

/**
 * Derives the slash-command menu state from the composer's textarea value.
 *
 * The menu opens only while the entire value is a bare "/word" token
 * (`isSlashTrigger`), and the highlight resets to the top whenever the query
 * changes so it can never point past the filtered list.
 */
export function useSlashCommandMenu(value: string): SlashCommandMenuState {
  // Escape sets `dismissed` to hide the menu without erasing the typed token;
  // any new keystroke (value change) re-arms it below.
  const [dismissed, setDismissed] = useState(false);
  const isOpen = isSlashTrigger(value) && !dismissed;

  const filtered = useMemo(
    () => (isOpen ? filterCommands(value) : []),
    [isOpen, value]
  );

  const [highlightedIndex, setHighlightedIndex] = useState(0);

  useEffect(() => {
    setHighlightedIndex(0);
    setDismissed(false);
  }, [value]);

  const move = useCallback(
    (delta: number) => {
      setHighlightedIndex((current) => {
        const n = filtered.length;
        if (n === 0) return 0;
        return (current + delta + n) % n;
      });
    },
    [filtered.length]
  );

  const dismiss = useCallback(() => setDismissed(true), []);

  return {
    isOpen,
    filtered,
    highlightedIndex,
    setHighlightedIndex,
    move,
    dismiss,
  };
}
