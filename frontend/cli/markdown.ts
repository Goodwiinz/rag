/**
 * Minimal terminal markdown renderer.
 *
 * Goal: take a streamed agent reply and re-render headings, lists,
 * inline emphasis, inline code, and fenced code blocks with ANSI styles.
 * No external dependencies — keeps the CLI bundle small.
 */

const ANSI = {
  reset: '\x1b[0m',
  bold: ['\x1b[1m', '\x1b[22m'] as const,
  italic: ['\x1b[3m', '\x1b[23m'] as const,
  dim: ['\x1b[2m', '\x1b[22m'] as const,
  cyan: ['\x1b[36m', '\x1b[39m'] as const,
  yellow: ['\x1b[33m', '\x1b[39m'] as const,
};

const MD_DETECT_RE =
  /(^|\n)(#{1,6}\s|[-*]\s|\d+\.\s|```)|`[^`\n]+`|\*\*[^*\n]+\*\*|(?<!\*)\*[^*\n]+\*(?!\*)|_[^_\n]+_/;

export function hasMarkdown(src: string): boolean {
  return MD_DETECT_RE.test(src);
}

export function renderMarkdown(src: string): string {
  const lines = src.split('\n');
  const out: string[] = [];
  let inFence = false;
  for (const line of lines) {
    if (/^```/.test(line)) {
      inFence = !inFence;
      out.push(wrap(line, ANSI.dim));
      continue;
    }
    if (inFence) {
      out.push(wrap(line, ANSI.cyan));
      continue;
    }
    out.push(renderLine(line));
  }
  return out.join('\n');
}

function renderLine(line: string): string {
  const heading = line.match(/^(#{1,6})\s+(.*)$/);
  if (heading) {
    const text = renderInline(heading[2]);
    return wrap(text, ANSI.bold);
  }
  const bullet = line.match(/^(\s*)([-*])\s+(.*)$/);
  if (bullet) {
    return `${bullet[1]}• ${renderInline(bullet[3])}`;
  }
  const numbered = line.match(/^(\s*)(\d+\.)\s+(.*)$/);
  if (numbered) {
    return `${numbered[1]}${numbered[2]} ${renderInline(numbered[3])}`;
  }
  return renderInline(line);
}

function renderInline(s: string): string {
  let out = s;
  out = out.replace(/\*\*([^*\n]+)\*\*/g, (_m, body) => wrap(body, ANSI.bold));
  out = out.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, (_m, body) =>
    wrap(body, ANSI.italic)
  );
  out = out.replace(/_([^_\n]+)_/g, (_m, body) => wrap(body, ANSI.italic));
  out = out.replace(/`([^`\n]+)`/g, (_m, body) => wrap(body, ANSI.cyan));
  return out;
}

function wrap(text: string, codes: readonly [string, string]): string {
  return `${codes[0]}${text}${codes[1]}`;
}

const ANSI_RE = /\x1b\[[0-9;]*m/g;
export function stripAnsi(s: string): string {
  return s.replace(ANSI_RE, '');
}

/**
 * Approximate the number of visual rows a stream of tokens occupied
 * in the terminal. Used to decide whether in-place re-render is safe.
 */
export function countVisualRows(text: string, columns: number): number {
  if (!text) return 0;
  const cols = Math.max(1, columns);
  let rows = 0;
  for (const line of text.split('\n')) {
    const w = stripAnsi(line).length;
    rows += Math.max(1, Math.ceil(w / cols));
  }
  return rows;
}
