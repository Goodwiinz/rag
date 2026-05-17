/**
 * Terminal theme — palette, glyphs, and tiny ANSI helpers used by the
 * CLI to give different event classes (thinking, tools, response, system)
 * distinct visual weight. Inspired by Claude Code / opencode output.
 *
 * No external deps; respects NO_COLOR + non-TTY by collapsing to empty
 * escape sequences.
 */

const supportsColor = (): boolean => {
  if (process.env.NO_COLOR) return false;
  if (process.env.FORCE_COLOR && process.env.FORCE_COLOR !== '0') return true;
  return Boolean(process.stdout.isTTY);
};

const ansi = (open: string, close = '\x1b[0m') =>
  supportsColor() ? (s: string) => `${open}${s}${close}` : (s: string) => s;

export const c = {
  reset: supportsColor() ? '\x1b[0m' : '',
  dim: ansi('\x1b[2m'),
  bold: ansi('\x1b[1m'),
  italic: ansi('\x1b[3m'),
  // Foreground
  cyan: ansi('\x1b[36m'),
  yellow: ansi('\x1b[33m'),
  green: ansi('\x1b[32m'),
  red: ansi('\x1b[31m'),
  magenta: ansi('\x1b[35m'),
  blue: ansi('\x1b[34m'),
  gray: ansi('\x1b[90m'),
  // Bright variants
  brightCyan: ansi('\x1b[96m'),
  brightMagenta: ansi('\x1b[95m'),
  // Combined styles
  dimItalic: ansi('\x1b[2;3m'),
  boldCyan: ansi('\x1b[1;36m'),
  boldMagenta: ansi('\x1b[1;35m'),
  boldYellow: ansi('\x1b[1;33m'),
};

/**
 * Glyphs used for the left-bar prefix per role.
 * Heavy `┃` for assistant response (high-attention),
 * light `┊` for thinking (low-attention),
 * solid `▎` accent for tool calls.
 */
export const glyph = {
  responseBar: '┃',
  thinkingBar: '┊',
  toolBar: '▎',
  headerLeft: '╭─',
  headerRight: '─╮',
  footerLeft: '╰─',
  footerRight: '─╯',
  bullet: '•',
  arrow: '→',
  check: '✓',
  cross: '✗',
  warn: '⚠',
  spark: '✦',
};

const cols = (): number =>
  process.stdout.isTTY && process.stdout.columns ? process.stdout.columns : 80;

/**
 * Render a soft block header like:  `╭─ NOUS ──────────────…─╮`
 * Width clamps to terminal columns; falls back to plain when no color.
 */
export function blockHeader(
  label: string,
  color: (s: string) => string
): string {
  const width = Math.min(cols(), 100);
  const left = `${glyph.headerLeft} ${label} `;
  const tailLen = Math.max(2, width - left.length - 1);
  const tail = '─'.repeat(tailLen);
  return color(`${left}${tail}${glyph.headerRight}`);
}

export function blockFooter(color: (s: string) => string): string {
  const width = Math.min(cols(), 100);
  const tail = '─'.repeat(Math.max(2, width - 2));
  return color(`${glyph.footerLeft}${tail}${glyph.footerRight}`);
}

/** Centered tiny divider used between turns. */
export function separator(): string {
  const width = Math.min(cols(), 100);
  const line = '─'.repeat(Math.max(8, width));
  return c.gray(line);
}
