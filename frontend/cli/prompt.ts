import * as p from '@clack/prompts';
import * as readline from 'readline';
import { clearDraft, writeDraft } from './services/draft';
import { appendHistory, loadHistory } from './services/promptHistory';

export const CANCEL = Symbol.for('nous.prompt.cancel');
export type Cancel = typeof CANCEL;

export interface PromptOptions {
  message: string;
  completer?: (line: string) => string[];
  initialValue?: string;
}

export function isPromptCancel(value: unknown): value is Cancel {
  return value === CANCEL;
}

/**
 * Read a single line from the user. In a real terminal this uses Node's
 * readline (so we get up/down history and tab-completion). When stdin is
 * not a TTY (tests, piped input, CI) it falls back to @clack/prompts so
 * existing test mocks of `p.text()` keep working.
 */
export async function readPrompt(
  opts: PromptOptions
): Promise<string | Cancel> {
  if (!process.stdin.isTTY) {
    const r = await p.text({
      message: opts.message,
      initialValue: opts.initialValue,
    });
    if (p.isCancel(r)) return CANCEL;
    clearDraft();
    return r as string;
  }

  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      terminal: true,
      // readline expects newest-first
      history: loadHistory().slice().reverse(),
      historySize: 500,
      completer: opts.completer
        ? (line: string) => {
            const all = opts.completer!(line);
            const prefix = currentToken(line);
            const hits = all.filter((c) => c.startsWith(prefix));
            return [hits.length > 0 ? hits : all, prefix];
          }
        : undefined,
    });

    // Debounced draft write on each keypress (TTY only)
    let draftTimer: NodeJS.Timeout | null = null;
    const scheduleDraftWrite = () => {
      if (draftTimer) clearTimeout(draftTimer);
      draftTimer = setTimeout(() => {
        writeDraft((rl as unknown as { line: string }).line ?? '');
      }, 300);
    };
    process.stdin.on('keypress', scheduleDraftWrite);
    rl.on('close', () => {
      if (draftTimer) clearTimeout(draftTimer);
      process.stdin.off('keypress', scheduleDraftWrite);
    });

    // Prefill from initialValue after readline renders the question
    if (opts.initialValue) {
      setImmediate(() => {
        rl.write(opts.initialValue ?? '');
      });
    }

    let done = false;
    const finish = (val: string | Cancel) => {
      if (done) return;
      done = true;
      rl.close();
      resolve(val);
    };

    rl.on('SIGINT', () => finish(CANCEL));
    rl.on('close', () => finish(CANCEL));

    rl.question(`${opts.message} `, (answer) => {
      const trimmed = answer.trim();
      if (trimmed) appendHistory(trimmed);
      clearDraft();
      finish(answer);
    });
  });
}

/**
 * Return the part of the line being completed (the last whitespace-delimited
 * token). readline replaces this prefix with the chosen completion.
 */
function currentToken(line: string): string {
  const lastSpace = line.lastIndexOf(' ');
  return lastSpace === -1 ? line : line.slice(lastSpace + 1);
}

const SLASH_COMMANDS = [
  '/new',
  '/thread',
  '/threads',
  '/history',
  '/forget',
  '/projects',
  '/retry',
  '/context',
  '/settings',
  '/help',
  '/quit',
];

export interface CompletionContext {
  knownThreadIds?: string[];
  knownProjectIds?: string[];
}

/**
 * Build a completer function for the main REPL prompt.
 *
 * Behavior:
 *   - empty / starts with `/`: completes from the slash command list
 *   - `/forget <prefix>`: completes from known thread IDs
 *   - `/context project <prefix>`: completes from known project IDs
 *   - everything else: no completion
 */
export function buildCompleter(
  ctx: CompletionContext
): (line: string) => string[] {
  return (line: string) => {
    const tokens = line.split(/\s+/);
    const head = tokens[0];

    if (line.length === 0 || (head.startsWith('/') && tokens.length === 1)) {
      return SLASH_COMMANDS;
    }
    if (head === '/forget' && tokens.length === 2) {
      return ctx.knownThreadIds ?? [];
    }
    if (head === '/context' && tokens[1] === 'project' && tokens.length === 3) {
      return ctx.knownProjectIds ?? [];
    }
    return [];
  };
}
