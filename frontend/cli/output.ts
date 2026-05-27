/**
 * Streaming output renderers.
 *
 * ResponseWriter — writes assistant tokens prefixed with a left bar so
 * the response visually reads as a single block (Claude Code / opencode
 * style). On done it can repaint the block as rendered markdown.
 *
 * thinkingBlock / toolBadge — small helpers for sibling event types that
 * should NOT share the response styling.
 */

import { c, glyph, blockHeader, blockFooter } from './theme';
import {
  countVisualRows,
  hasMarkdown,
  renderMarkdown,
  stripAnsi,
} from './markdown';

const ASSISTANT_LABEL = 'NOUS';
const MD_DISABLED = process.env.NOUS_MD === '0';
const MD_INPLACE_MAX_ROWS = 200;

function write(s: string): void {
  process.stdout.write(s);
}

function barLine(s: string): string {
  return `${c.brightCyan(glyph.responseBar)}  ${s}`;
}

function thinkingLine(s: string): string {
  return `${c.gray(glyph.thinkingBar)}  ${c.dimItalic(s)}`;
}

/**
 * Streams assistant tokens with a left-bar prefix per visual line.
 * Buffers the raw text so the final repaint can render markdown in
 * place, preserving the bar prefix on every line.
 */
export class ResponseWriter {
  private buffer = '';
  private headerWritten = false;
  private atLineStart = true;

  ensureHeader(): void {
    if (this.headerWritten) return;
    this.headerWritten = true;
    write(blockHeader(ASSISTANT_LABEL, c.boldCyan) + '\n');
    write(barLine('') + '\n');
    this.atLineStart = true;
  }

  writeToken(chunk: string): void {
    if (!chunk) return;
    this.ensureHeader();
    this.buffer += chunk;
    // Emit char-by-char so newlines inside a chunk get re-prefixed.
    for (let i = 0; i < chunk.length; i++) {
      const ch = chunk[i];
      if (this.atLineStart) {
        write(`${c.brightCyan(glyph.responseBar)}  `);
        this.atLineStart = false;
      }
      write(ch);
      if (ch === '\n') this.atLineStart = true;
    }
  }

  get rawBuffer(): string {
    return this.buffer;
  }

  /**
   * On a successful stream end, optionally repaint the response as
   * rendered markdown (so headings, bullets, code spans get ANSI styles)
   * with the bar prefix re-applied per line. Always writes the footer.
   */
  finish(): void {
    if (!this.headerWritten) return;
    // Ensure we end on a newline before closing the block.
    if (!this.atLineStart) {
      write('\n');
      this.atLineStart = true;
    }
    this.repaintMarkdown();
    write(blockFooter(c.boldCyan) + '\n');
  }

  /** Cancel without repainting — used on abort / early error. */
  abort(): void {
    if (!this.headerWritten) return;
    if (!this.atLineStart) write('\n');
    write(blockFooter(c.gray) + '\n');
  }

  private repaintMarkdown(): void {
    if (MD_DISABLED) return;
    if (!this.buffer || !hasMarkdown(this.buffer)) return;
    if (!process.stdout.isTTY) return;

    const cols = process.stdout.columns ?? 80;
    // Effective width inside the bar prefix is cols - 3.
    const inner = Math.max(20, cols - 3);
    const rendered = renderMarkdown(this.buffer);
    // Re-prefix each rendered line with the bar.
    const lines = rendered.split('\n');
    const writtenRows =
      lines.reduce(
        (acc, line) =>
          acc + Math.max(1, Math.ceil(stripAnsi(line).length / inner)),
        0
      ) + 1;

    if (writtenRows > MD_INPLACE_MAX_ROWS) return;

    // Move cursor up by the number of rows we wrote (raw buffer with bar
    // prefix, plus the trailing newline). The header line is left intact.
    const rawRows = countVisualRows(this.buffer, inner) + 1;
    write(`\x1b[${rawRows}F\x1b[J`);
    for (const line of lines) {
      write(barLine(line) + '\n');
    }
  }
}

/**
 * Render a "thinking" panel — plan / reflection / context retrieval.
 * Dim italic, light vertical bar, distinct from the response block.
 */
export function thinkingBlock(label: string, lines: string[]): void {
  if (lines.length === 0) return;
  write(`${c.gray(glyph.thinkingBar)} ${c.dim(c.italic(label))}\n`);
  for (const line of lines) {
    write(thinkingLine(line) + '\n');
  }
}

/** One-liner thinking marker. */
export function thinkingLineOut(label: string, body?: string): void {
  const text = body ? `${label} ${c.dim('·')} ${body}` : label;
  write(thinkingLine(text) + '\n');
}

/** Banner shown before a turn's first tool/event. */
export function userEcho(message: string): void {
  const trimmed = message.replace(/\s+/g, ' ').trim();
  if (!trimmed) return;
  write(
    `${c.brightMagenta('▌')} ${c.bold(c.brightMagenta('you'))}  ${trimmed}\n`
  );
}

/** Mini ruler between turns (sub-divider for readability). */
export function turnSeparator(): void {
  write('\n');
}

export function toolBadgePrefix(): string {
  return c.yellow(glyph.toolBar);
}

// Re-export for callers that mix theme + output.
export { c, glyph };
