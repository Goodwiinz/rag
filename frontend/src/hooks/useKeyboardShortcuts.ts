/**
 * useKeyboardShortcuts Hook
 * Global keyboard shortcuts for entity management
 */

import { useEffect, useCallback } from 'react';

interface ShortcutConfig {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  action: () => void;
  description: string;
}

export const useKeyboardShortcuts = (shortcuts: ShortcutConfig[], enabled: boolean = true) => {
  const handleKeyPress = useCallback(
    (event: KeyboardEvent) => {
      if (!enabled) return;

      // Don't trigger shortcuts when typing in inputs or pressing keys on
      // interactive elements — a bare 'g' on a focused <select>/<button>/<a>
      // would hijack the element's own keyboard behavior (R6-L17).
      const target = event.target as HTMLElement | null;
      if (!target) return;
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.tagName === 'BUTTON' ||
        target.tagName === 'A' ||
        target.isContentEditable
      ) {
        return;
      }

      // Don't fire while a modal is open — typing inside a dialog would
      // silently trigger page navigation behind it. Window/document targets
      // have no closest(); skip the check for them.
      if (
        typeof target.closest === 'function' &&
        target.closest('[role="dialog"], dialog')
      ) {
        return;
      }

      const matchingShortcut = shortcuts.find((shortcut) => {
        const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase();
        const ctrlMatch = shortcut.ctrl ? event.ctrlKey || event.metaKey : true;
        const shiftMatch = shortcut.shift ? event.shiftKey : !event.shiftKey;
        const altMatch = shortcut.alt ? event.altKey : !event.altKey;

        // Modifier-declared shortcuts must see their modifier; modifier-free
        // shortcuts must not fire when ctrl/meta/alt is held, so e.g. Ctrl+G
        // can never match a plain 'g' shortcut (R6-L17).
        if (
          !shortcut.ctrl &&
          !shortcut.alt &&
          (event.ctrlKey || event.metaKey || event.altKey)
        ) {
          return false;
        }

        return keyMatch && ctrlMatch && shiftMatch && altMatch;
      });

      if (matchingShortcut) {
        event.preventDefault();
        matchingShortcut.action();
      }
    },
    [shortcuts, enabled]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [handleKeyPress]);
};

// Default entity management shortcuts
export const defaultEntityShortcuts = {
  CREATE_ENTITY: { key: 'n', ctrl: true, description: 'Create new entity' },
  SEARCH: { key: 'k', ctrl: true, description: 'Focus search' },
  REFRESH: { key: 'r', ctrl: true, description: 'Refresh data' },
  EXPORT: { key: 'e', ctrl: true, shift: true, description: 'Export data' },
  TOGGLE_GRAPH: { key: 'g', description: 'Toggle graph view' },
  TOGGLE_ANALYTICS: { key: 'a', description: 'Toggle analytics' },
  PATH_FINDER: { key: 'p', description: 'Open path finder' },
  BULK_OPS: { key: 'b', description: 'Open bulk operations' },
  HELP: { key: '?', description: 'Show keyboard shortcuts' },
};
