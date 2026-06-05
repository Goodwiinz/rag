/**
 * Slash-command registry for the chat composer.
 *
 * Mirrors the command names the user already has in the CLI
 * (`cli/repl.ts` `handleSlashCommand`) so the web chat and the terminal share
 * one vocabulary. Only the subset that maps cleanly to existing web actions is
 * shipped; the CLI's `/thread /history /forget /context /settings /quit` are
 * intentionally omitted.
 *
 * Kept JSX- and dependency-free so it can be imported anywhere (component,
 * hook, test) without pulling in React.
 */

export type SlashCommandId =
  | 'new'
  | 'retry'
  | 'clear'
  | 'threads'
  | 'projects'
  | 'papers'
  | 'help';

export interface SlashCommand {
  id: SlashCommandId;
  /** The "/name" rendered in the menu. */
  label: string;
  /** One-line description shown beside the label. */
  title: string;
  /**
   * `action` runs immediately via `onCommand(id)`.
   * `picker` opens an in-menu picker (currently only `/projects`).
   */
  kind: 'action' | 'picker';
}

export const SLASH_COMMANDS: SlashCommand[] = [
  { id: 'new', label: '/new', title: 'Start a new chat', kind: 'action' },
  {
    id: 'retry',
    label: '/retry',
    title: 'Regenerate the last response',
    kind: 'action',
  },
  { id: 'clear', label: '/clear', title: 'Clear the input', kind: 'action' },
  { id: 'threads', label: '/threads', title: 'Browse threads', kind: 'action' },
  {
    id: 'projects',
    label: '/projects',
    title: 'Set project context',
    kind: 'picker',
  },
  { id: 'papers', label: '/papers', title: 'Browse papers', kind: 'action' },
  { id: 'help', label: '/help', title: 'List commands', kind: 'action' },
];

/**
 * True when the whole input is a bare slash-command token — `/`, `/n`,
 * `/proj` — i.e. a single "/word" with no spaces. The menu opens only in this
 * state, which is never a sendable message, so it can never interfere with
 * normal send-on-Enter.
 */
export function isSlashTrigger(value: string): boolean {
  return /^\/[a-z]*$/i.test(value);
}

/** Commands matching the current "/query" (by id prefix or label substring). */
export function filterCommands(value: string): SlashCommand[] {
  const q = value.replace(/^\//, '').toLowerCase();
  if (!q) return SLASH_COMMANDS;
  return SLASH_COMMANDS.filter(
    (c) => c.id.startsWith(q) || c.label.toLowerCase().includes(q)
  );
}
