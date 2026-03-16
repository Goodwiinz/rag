/**
 * Unit tests for useKeyboardShortcuts hook
 *
 * Tests keyboard event registration, modifier key handling,
 * input element filtering, and cleanup on unmount.
 */

import { renderHook } from '@testing-library/react';
import { useKeyboardShortcuts } from '../useKeyboardShortcuts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Fire a keyboard event on `window` with the given options. */
function fireKey(options: Partial<KeyboardEvent> & { key: string }) {
  const event = new KeyboardEvent('keydown', {
    bubbles: true,
    cancelable: true,
    key: options.key,
    ctrlKey: options.ctrlKey ?? false,
    shiftKey: options.shiftKey ?? false,
    altKey: options.altKey ?? false,
    metaKey: options.metaKey ?? false,
  });
  window.dispatchEvent(event);
  return event;
}

/** Fire a keyboard event that appears to originate from a specific element. */
function fireKeyFromElement(
  tagName: string,
  key: string,
  extra: Partial<KeyboardEvent> = {}
) {
  const event = new KeyboardEvent('keydown', {
    bubbles: true,
    cancelable: true,
    key,
    ...extra,
  });

  // Override event.target to simulate the event coming from an input/textarea
  const fakeTarget = document.createElement(tagName);
  Object.defineProperty(event, 'target', {
    value: fakeTarget,
    writable: false,
  });

  window.dispatchEvent(event);
  return event;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useKeyboardShortcuts', () => {
  // =========================================================================
  // Basic registration & callback invocation
  // =========================================================================

  describe('basic shortcut registration', () => {
    it('fires callback when the matching key is pressed', () => {
      const action = jest.fn();
      const shortcuts = [
        { key: 'g', action, description: 'Toggle graph view' },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      fireKey({ key: 'g' });

      expect(action).toHaveBeenCalledTimes(1);
    });

    it('does not fire callback for non-matching keys', () => {
      const action = jest.fn();
      const shortcuts = [
        { key: 'g', action, description: 'Toggle graph view' },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      fireKey({ key: 'x' });

      expect(action).not.toHaveBeenCalled();
    });

    it('matches keys case-insensitively', () => {
      const action = jest.fn();
      const shortcuts = [
        { key: 'G', action, description: 'Toggle graph view' },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      fireKey({ key: 'g' });

      expect(action).toHaveBeenCalledTimes(1);
    });

    it('supports multiple shortcuts simultaneously', () => {
      const actionA = jest.fn();
      const actionB = jest.fn();
      const shortcuts = [
        { key: 'a', action: actionA, description: 'Action A' },
        { key: 'b', action: actionB, description: 'Action B' },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      fireKey({ key: 'a' });
      fireKey({ key: 'b' });

      expect(actionA).toHaveBeenCalledTimes(1);
      expect(actionB).toHaveBeenCalledTimes(1);
    });

    it('calls preventDefault on matching shortcut events', () => {
      const action = jest.fn();
      const shortcuts = [
        { key: 'k', ctrl: true, action, description: 'Focus search' },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      const event = new KeyboardEvent('keydown', {
        bubbles: true,
        cancelable: true,
        key: 'k',
        ctrlKey: true,
      });
      const spy = jest.spyOn(event, 'preventDefault');
      window.dispatchEvent(event);

      expect(spy).toHaveBeenCalled();
    });
  });

  // =========================================================================
  // Modifier key handling
  // =========================================================================

  describe('modifier keys', () => {
    it('matches Ctrl modifier when ctrl: true is specified', () => {
      const action = jest.fn();
      const shortcuts = [
        { key: 'n', ctrl: true, action, description: 'Create new entity' },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      // Without ctrl => should NOT fire
      fireKey({ key: 'n' });
      expect(action).not.toHaveBeenCalled();

      // With ctrl => should fire
      fireKey({ key: 'n', ctrlKey: true });
      expect(action).toHaveBeenCalledTimes(1);
    });

    it('matches Meta key as alternative to Ctrl (macOS Cmd)', () => {
      const action = jest.fn();
      const shortcuts = [
        { key: 'k', ctrl: true, action, description: 'Focus search' },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      fireKey({ key: 'k', metaKey: true });

      expect(action).toHaveBeenCalledTimes(1);
    });

    it('matches Shift modifier when shift: true is specified', () => {
      const action = jest.fn();
      const shortcuts = [
        {
          key: 'e',
          ctrl: true,
          shift: true,
          action,
          description: 'Export data',
        },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      // Ctrl only (no shift) => should NOT fire
      fireKey({ key: 'e', ctrlKey: true });
      expect(action).not.toHaveBeenCalled();

      // Ctrl + Shift => should fire
      fireKey({ key: 'e', ctrlKey: true, shiftKey: true });
      expect(action).toHaveBeenCalledTimes(1);
    });

    it('rejects Shift when shift is not specified (defaults to requiring no-shift)', () => {
      const action = jest.fn();
      const shortcuts = [{ key: 'g', action, description: 'Toggle graph' }];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      // Pressing 'g' with Shift held should NOT fire (shift not specified means !shiftKey required)
      fireKey({ key: 'g', shiftKey: true });
      expect(action).not.toHaveBeenCalled();

      // Pressing 'g' without Shift should fire
      fireKey({ key: 'g' });
      expect(action).toHaveBeenCalledTimes(1);
    });

    it('matches Alt modifier when alt: true is specified', () => {
      const action = jest.fn();
      const shortcuts = [
        { key: 'a', alt: true, action, description: 'Alt action' },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      // Without alt => should NOT fire
      fireKey({ key: 'a' });
      expect(action).not.toHaveBeenCalled();

      // With alt => should fire
      fireKey({ key: 'a', altKey: true });
      expect(action).toHaveBeenCalledTimes(1);
    });

    it('rejects Alt when alt is not specified (defaults to requiring no-alt)', () => {
      const action = jest.fn();
      const shortcuts = [{ key: 'p', action, description: 'Open path finder' }];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      fireKey({ key: 'p', altKey: true });
      expect(action).not.toHaveBeenCalled();

      fireKey({ key: 'p' });
      expect(action).toHaveBeenCalledTimes(1);
    });
  });

  // =========================================================================
  // Input/Textarea filtering
  // =========================================================================

  describe('input element filtering', () => {
    it('ignores shortcuts when event target is an INPUT element', () => {
      const action = jest.fn();
      const shortcuts = [
        { key: 'g', action, description: 'Toggle graph view' },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      fireKeyFromElement('INPUT', 'g');

      expect(action).not.toHaveBeenCalled();
    });

    it('ignores shortcuts when event target is a TEXTAREA element', () => {
      const action = jest.fn();
      const shortcuts = [
        { key: 'g', action, description: 'Toggle graph view' },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      fireKeyFromElement('TEXTAREA', 'g');

      expect(action).not.toHaveBeenCalled();
    });

    it('ignores shortcuts when event target is contentEditable', () => {
      const action = jest.fn();
      const shortcuts = [
        { key: 'g', action, description: 'Toggle graph view' },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts));

      const event = new KeyboardEvent('keydown', {
        bubbles: true,
        cancelable: true,
        key: 'g',
      });
      const editableDiv = document.createElement('div');
      editableDiv.contentEditable = 'true';
      // jsdom may not derive isContentEditable when the element is detached,
      // so we explicitly set it to match what browsers return.
      Object.defineProperty(editableDiv, 'isContentEditable', { value: true });
      Object.defineProperty(event, 'target', {
        value: editableDiv,
        writable: false,
      });
      window.dispatchEvent(event);

      expect(action).not.toHaveBeenCalled();
    });
  });

  // =========================================================================
  // Enabled / Disabled
  // =========================================================================

  describe('enabled parameter', () => {
    it('does not fire callbacks when enabled is false', () => {
      const action = jest.fn();
      const shortcuts = [
        { key: 'g', action, description: 'Toggle graph view' },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts, false));

      fireKey({ key: 'g' });

      expect(action).not.toHaveBeenCalled();
    });

    it('fires callbacks when enabled is true (default)', () => {
      const action = jest.fn();
      const shortcuts = [
        { key: 'g', action, description: 'Toggle graph view' },
      ];

      renderHook(() => useKeyboardShortcuts(shortcuts, true));

      fireKey({ key: 'g' });

      expect(action).toHaveBeenCalledTimes(1);
    });
  });

  // =========================================================================
  // Cleanup on unmount
  // =========================================================================

  describe('cleanup on unmount', () => {
    it('removes the event listener when the hook unmounts', () => {
      const action = jest.fn();
      const shortcuts = [
        { key: 'g', action, description: 'Toggle graph view' },
      ];

      const { unmount } = renderHook(() => useKeyboardShortcuts(shortcuts));

      // Before unmount – should fire
      fireKey({ key: 'g' });
      expect(action).toHaveBeenCalledTimes(1);

      unmount();

      // After unmount – should NOT fire
      fireKey({ key: 'g' });
      expect(action).toHaveBeenCalledTimes(1); // still 1, not 2
    });
  });
});
