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

      // Don't trigger shortcuts when typing in inputs
      const target = event.target as HTMLElement;
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      ) {
        return;
      }

      const matchingShortcut = shortcuts.find((shortcut) => {
        const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase();
        const ctrlMatch = shortcut.ctrl ? event.ctrlKey || event.metaKey : true;
        const shiftMatch = shortcut.shift ? event.shiftKey : !event.shiftKey;
        const altMatch = shortcut.alt ? event.altKey : !event.altKey;

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
