import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react';

// ============================================
// HOOK RETURN
// ============================================

export interface UseChatDrawerReturn {
  isOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
  toggleDrawer: () => void;
  drawerRef: React.RefObject<HTMLDivElement>;
  /** Trap Tab focus inside the open drawer — wire onto the dialog element. */
  handleDrawerKeyDown: (e: ReactKeyboardEvent) => void;
}

// ============================================
// HOOK
// ============================================

/**
 * Mobile sidebar drawer: open/close state plus its WCAG behavior — focus
 * moves into the drawer on open, returns to the opener on close, Escape
 * closes it, and Tab is trapped inside while it's open (role=dialog
 * aria-modal). Purely presentational coordination; no service calls.
 */
export function useChatDrawer(): UseChatDrawerReturn {
  const [isOpen, setIsOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);
  const drawerOpenerRef = useRef<HTMLElement | null>(null);

  const openDrawer = useCallback(() => setIsOpen(true), []);
  const closeDrawer = useCallback(() => setIsOpen(false), []);
  const toggleDrawer = useCallback(() => setIsOpen((v) => !v), []);

  // Focus in on open, return focus to the opener on close, Escape to close.
  useEffect(() => {
    if (isOpen) {
      drawerOpenerRef.current = document.activeElement as HTMLElement | null;
      drawerRef.current?.focus();
      const onKey = (e: KeyboardEvent): void => {
        if (e.key === 'Escape') setIsOpen(false);
      };
      window.addEventListener('keydown', onKey);
      return () => window.removeEventListener('keydown', onKey);
    }
    drawerOpenerRef.current?.focus?.();
  }, [isOpen]);

  // Trap Tab focus inside the open mobile drawer (role=dialog aria-modal) so
  // keyboard focus can't wander behind it. Wraps at the focusable boundaries.
  // ponytail: Tab-wrap alone satisfies WCAG 2.4.3/4.1.2; the fuller fix is
  // `inert` on the main content for screen-reader virtual-cursor escape — add
  // that only if SR escape is reported.
  const handleDrawerKeyDown = useCallback((e: ReactKeyboardEvent) => {
    if (e.key !== 'Tab') return;
    const root = drawerRef.current;
    if (!root) return;
    const focusables = root.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'
    );
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }, []);

  return {
    isOpen,
    openDrawer,
    closeDrawer,
    toggleDrawer,
    drawerRef,
    handleDrawerKeyDown,
  };
}
