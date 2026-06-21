/**
 * Markdown Utilities
 *
 * Simple utilities for markdown text processing.
 * Used by chat components for message rendering.
 */

/**
 * Make a partial markdown string from a live token stream safe to render.
 *
 * While an assistant message streams token-by-token, markdown syntax arrives
 * incomplete: a fenced code block opens (```) before its closing fence has
 * been emitted, so a markdown renderer leaks the raw fence + treats the rest of
 * the answer as a code block until the close arrives — the body visibly breaks
 * mid-stream. This closes the dangling syntax so each intermediate frame renders
 * cleanly; the real closing token simply replaces the temporary one next frame.
 *
 * Deterministic, allocation-light, and intended for the STREAMING render only —
 * committed content already has balanced syntax and must not be altered.
 *
 * Handles:
 * - Unterminated fenced code block (odd number of ``` fences) -> append a close.
 * - A trailing unterminated inline code span (odd ` on the last line) -> close it.
 */
export function completeStreamingMarkdown(text: string): string {
  if (!text) return text;

  let out = text;

  // 1. Fenced code blocks: an odd count of ``` fences means one is still open.
  //    Append a newline + closing fence so the open block renders as code, not
  //    as raw text bleeding into the rest of the message.
  const fenceCount = (out.match(/^```/gm) || []).length;
  if (fenceCount % 2 === 1) {
    out += (out.endsWith('\n') ? '' : '\n') + '```';
    return out; // inside a code fence, inline backticks below don't apply
  }

  // 2. Trailing inline code: an odd number of single backticks on the final
  //    line is an unterminated inline span — close it so it doesn't swallow the
  //    cursor / following tokens. Skip a fence line (its ``` backticks are not
  //    an inline span and the fence count above already balanced it).
  const lastLine = out.slice(out.lastIndexOf('\n') + 1);
  if (!lastLine.trimStart().startsWith('```')) {
    const inlineTicks = (lastLine.match(/`/g) || []).length;
    if (inlineTicks % 2 === 1) {
      out += '`';
    }
  }

  return out;
}

/**
 * Escape markdown special characters
 */
export function escapeMarkdown(text: string): string {
  return text.replace(/([\\`*_{}[\]()#+\-.!])/g, '\\$1');
}

/**
 * Convert markdown to plain text (strip formatting)
 */
export function stripMarkdown(markdown: string): string {
  return markdown
    .replace(/#{1,6}\s/g, '') // Headers
    .replace(/\*\*(.+?)\*\*/g, '$1') // Bold
    .replace(/\*(.+?)\*/g, '$1') // Italic
    .replace(/`(.+?)`/g, '$1') // Inline code
    .replace(/~~(.+?)~~/g, '$1') // Strikethrough
    .replace(/\[(.+?)\]\(.+?\)/g, '$1') // Links
    .replace(/!\[.*?\]\(.+?\)/g, '') // Images
    .replace(/^\s*[-*+]\s/gm, '') // Unordered lists
    .replace(/^\s*\d+\.\s/gm, '') // Ordered lists
    .replace(/^\s*>\s/gm, '') // Blockquotes
    .replace(/```[\s\S]*?```/g, '') // Code blocks
    .trim();
}

/**
 * Format code block with language
 */
export function formatCodeBlock(code: string, language: string = ''): string {
  return `\`\`\`${language}\n${code}\n\`\`\``;
}

/**
 * Parse keyboard shortcuts from markdown-like format
 * Example: "Ctrl+K" -> { key: 'K', modifiers: ['Ctrl'] }
 */
export interface KeyboardShortcut {
  key: string;
  modifiers: string[];
  description?: string;
}

export function parseKeyboardShortcut(shortcut: string): KeyboardShortcut {
  const parts = shortcut.split('+');
  const key = parts.pop() || '';
  const modifiers = parts;

  return { key, modifiers };
}

/**
 * Format keyboard shortcut for display
 */
export function formatKeyboardShortcut(shortcut: KeyboardShortcut): string {
  const isMac =
    typeof navigator !== 'undefined' &&
    /Mac|iPod|iPhone|iPad/.test(navigator.platform);

  const modifierMap: Record<string, string> = isMac
    ? { Ctrl: '⌃', Alt: '⌥', Shift: '⇧', Meta: '⌘', Cmd: '⌘' }
    : { Ctrl: 'Ctrl', Alt: 'Alt', Shift: 'Shift', Meta: 'Win', Cmd: 'Ctrl' };

  const formattedModifiers = shortcut.modifiers.map(
    (mod) => modifierMap[mod] || mod
  );
  return [...formattedModifiers, shortcut.key].join(isMac ? '' : '+');
}

/**
 * Truncate text with ellipsis
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + '...';
}

/**
 * Get platform-specific modifier key
 * Returns ⌘ on Mac, Ctrl on Windows/Linux
 */
export function getModifierKey(): string {
  if (
    typeof navigator !== 'undefined' &&
    /Mac|iPod|iPhone|iPad/.test(navigator.platform)
  ) {
    return '⌘';
  }
  return 'Ctrl';
}

/**
 * Format a timestamp for display
 */
export function formatTimestamp(timestamp: Date | string | number): string {
  const date = timestamp instanceof Date ? timestamp : new Date(timestamp);

  if (isNaN(date.getTime())) {
    return '';
  }

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  // Within last minute
  if (diffMins < 1) {
    return 'Just now';
  }

  // Within last hour
  if (diffMins < 60) {
    return `${diffMins}m ago`;
  }

  // Within last 24 hours
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }

  // Within last 7 days
  if (diffDays < 7) {
    return `${diffDays}d ago`;
  }

  // Older - show date
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}
