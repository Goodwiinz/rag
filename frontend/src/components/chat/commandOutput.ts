/**
 * Client-only "command output" rendered into the chat transcript when a slash
 * command runs (CLI-style). These objects live in ephemeral page state, never
 * in the message arrays, so they are never sent to the agent or persisted; they
 * clear when the thread changes or a real message is sent.
 */

export type CommandAction =
  | { type: 'open-thread'; id: string }
  | { type: 'set-project'; id: string; name: string }
  | { type: 'cite-paper'; id: string; title: string }
  | { type: 'delete-memory'; id: string; projectId: string };

export interface CommandOutputItem {
  key: string;
  /** Primary text (thread title, project name, paper title). */
  label: string;
  /** Secondary text (relative time, type, status). */
  meta?: string;
  /** Marks the current thread/project. */
  active?: boolean;
  /** What happens when the row is tapped. Omit for non-interactive rows. */
  action?: CommandAction;
}

export interface CommandOutput {
  id: string;
  /** The echoed command line, e.g. "/help". */
  command: string;
  timestamp: number;
  status?: 'loading' | 'ready';
  /** Pre-formatted monospace lines (used by /help, /thread, errors). */
  lines?: string[];
  /** Clickable rows (used by /threads, /projects, /papers). */
  items?: CommandOutputItem[];
  /** Shown when `items` is present but empty. */
  emptyText?: string;
  /** Muted footer hint. */
  note?: string;
}
