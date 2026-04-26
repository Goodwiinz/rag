import * as p from '@clack/prompts';
import { loadConfig, saveConfig } from './auth/store';
import { parseSlashCommand } from './hooks/useSlashCommands';
import { streamAgent, streamConfirm } from './stream';

interface ActiveProject {
  id: string;
  name: string;
}

interface ReplOptions {
  projectId?: string;
  projectName?: string;
}

export async function runRepl(options: ReplOptions = {}): Promise<void> {
  const config = loadConfig();
  if (!config) throw new Error('Not logged in');

  let threadId = config.thread_id ?? null;
  let activeProject: ActiveProject | null =
    options.projectId && options.projectName
      ? { id: options.projectId, name: options.projectName }
      : null;

  const statusParts = [
    threadId ? `thread: ${threadId.slice(0, 8)}` : 'no thread',
    activeProject ? `project: ${activeProject.name}` : null,
  ].filter(Boolean);

  p.intro(`NOUS  ·  ${statusParts.join('  ·  ')}`);

  const abort = new AbortController();
  process.once('SIGINT', () => {
    abort.abort();
    p.outro('Bye.');
    process.exit(0);
  });

  while (true) {
    const raw = await p.text({ message: '>' });
    if (p.isCancel(raw)) {
      p.outro('Bye.');
      break;
    }

    const input = (raw as string).trim();
    if (!input) continue;

    const parsed = parseSlashCommand(input);
    if (parsed) {
      const done = await handleSlashCommand(parsed.command, parsed.args, {
        threadId,
        activeProject,
        onThreadChange: (t) => {
          threadId = t;
        },
        onProjectChange: (proj) => {
          activeProject = proj;
        },
        onExit: () => {
          p.outro('Bye.');
          process.exit(0);
        },
      });
      if (done) continue;
    }

    const ctx = activeProject
      ? {
          type: 'project',
          project_id: activeProject.id,
          project_name: activeProject.name,
        }
      : { type: 'chat' };

    await streamToTerminal(input, ctx, abort.signal);

    const updated = loadConfig();
    if (updated && updated.thread_id !== threadId) {
      threadId = updated.thread_id ?? null;
    }
  }
}

export async function runOneShot(
  query: string,
  pageContext: Record<string, unknown> = {}
): Promise<void> {
  await streamToTerminal(query, pageContext);
}

async function streamToTerminal(
  message: string,
  pageContext: Record<string, unknown>,
  signal?: AbortSignal
): Promise<void> {
  const spinners = new Map<string, ReturnType<typeof p.spinner>>();
  let retriedAfterMissingThread = false;
  let inConfirmFlow = false;

  process.stdout.write('\n');

  type EventStream = AsyncGenerator<import('./stream').StreamEvent>;
  let current: EventStream = streamAgent(message, pageContext, { signal });

  while (true) {
    let pendingConfirmThreadId: string | null = null;
    let retryFreshThread = false;

    for await (const event of current) {
      if (event.type === 'token') {
        process.stdout.write(event.content);
      } else if (event.type === 'tool_start') {
        const s = p.spinner();
        s.start(event.tool);
        spinners.set(event.tool, s);
      } else if (event.type === 'tool_end') {
        const s = spinners.get(event.tool);
        if (s) {
          if (event.isError) {
            s.error(event.tool);
          } else {
            s.stop(event.tool);
          }
          spinners.delete(event.tool);
        } else if (event.isError) {
          p.log.error(`✗ ${event.tool}`);
        } else {
          p.log.success(`✓ ${event.tool}`);
        }
      } else if (event.type === 'plan') {
        if (event.steps.length > 0) {
          p.log.info(`Plan: ${event.steps.join(' → ')}`);
        }
      } else if (event.type === 'reflection') {
        if (event.passed) {
          p.log.success(`Reflection #${event.round} passed`);
        } else {
          p.log.warn(
            `Reflection #${event.round}: ${event.issues.length > 0 ? event.issues.join('; ') : 'failed'}`
          );
        }
      } else if (event.type === 'rag_context') {
        if (event.contexts.length > 0) {
          p.log.info(`Retrieved ${event.contexts.length} context(s)`);
        }
      } else if (event.type === 'confirmation') {
        for (const [tool, s] of spinners) {
          s.cancel(`${tool} (paused — awaiting confirmation)`);
        }
        spinners.clear();
        process.stdout.write('\n');
        renderConfirmationDetails(event.details);
        const ok = await p.confirm({
          message: confirmationPromptMessage(event.details),
        });
        if (p.isCancel(ok) || !ok) {
          p.log.warn('Cancelled.');
          return;
        }
        p.log.info('Resuming agent…');
        pendingConfirmThreadId = event.threadId;
        break;
      } else if (event.type === 'done') {
        process.stdout.write('\n\n');
        return;
      } else if (event.type === 'error') {
        process.stdout.write('\n');
        if (
          isMissingThreadError(event.message) &&
          !retriedAfterMissingThread &&
          !inConfirmFlow
        ) {
          clearCachedThreadId();
          retriedAfterMissingThread = true;
          retryFreshThread = true;
          p.log.warn(
            'Cached thread expired. Starting a new thread and retrying…'
          );
          break;
        }
        p.log.error(event.message);
        return;
      }
    }

    if (retryFreshThread) {
      current = streamAgent(message, pageContext, { signal });
      continue;
    }

    if (pendingConfirmThreadId === null) break;

    inConfirmFlow = true;
    current = streamConfirm(pendingConfirmThreadId, true, { signal });
  }
}

function isMissingThreadError(message: string): boolean {
  return /thread not found/i.test(message);
}

function clearCachedThreadId(): void {
  const cfg = loadConfig();
  if (cfg && cfg.thread_id !== null) {
    saveConfig({ ...cfg, thread_id: null });
  }
}

interface SlashContext {
  threadId: string | null;
  activeProject: ActiveProject | null;
  onThreadChange: (t: string | null) => void;
  onProjectChange: (proj: ActiveProject | null) => void;
  onExit: () => void;
}

async function handleSlashCommand(
  command: string,
  args: string[],
  ctx: SlashContext
): Promise<boolean> {
  if (command === 'quit') {
    ctx.onExit();
    return true;
  }
  if (command === 'new') {
    const cfg = loadConfig();
    if (cfg) saveConfig({ ...cfg, thread_id: null });
    ctx.onThreadChange(null);
    p.log.success('New thread started.');
    return true;
  }
  if (command === 'thread') {
    p.log.info(`Thread: ${ctx.threadId ?? 'none'}`);
    return true;
  }
  if (command === 'context') {
    if (args[0] === 'clear') {
      ctx.onProjectChange(null);
      p.log.success('Project context cleared.');
      return true;
    }
    if (args[0] === 'project' && args[1]) {
      ctx.onProjectChange({ id: args[1], name: args[2] ?? args[1] });
      p.log.success(`Project set: ${args[2] ?? args[1]}`);
      return true;
    }
  }
  if (command === 'help') {
    p.log.message(
      '/new  /thread  /context project <id> [name]  /context clear  /quit'
    );
    return true;
  }
  return false;
}

const TOOL_LABELS: Record<string, string> = {
  ingest_arxiv_papers: 'Download & index arXiv paper(s)',
  add_document_to_project: 'Add document to project',
  create_project: 'Create new project',
  create_project_note: 'Save note to project',
  create_draft: 'Generate draft document',
  execute_code: 'Execute code',
};

interface PendingTool {
  name: string;
  args: Record<string, unknown>;
}

function extractPendingTools(details: Record<string, unknown>): PendingTool[] {
  const raw = details.tools;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(
      (t): t is PendingTool =>
        typeof t === 'object' && t !== null && 'name' in t
    )
    .map((t) => ({
      name: String((t as { name: unknown }).name ?? ''),
      args:
        typeof (t as { args?: unknown }).args === 'object' &&
        (t as { args?: unknown }).args !== null
          ? (t as { args: Record<string, unknown> }).args
          : {},
    }));
}

function summarizeArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args);
  if (entries.length === 0) return '';
  return entries
    .map(([k, v]) => {
      let val: string;
      if (Array.isArray(v)) {
        val = v.length <= 3 ? `[${v.join(', ')}]` : `[${v.length} items]`;
      } else if (typeof v === 'object' && v !== null) {
        val = '{…}';
      } else {
        const s = String(v);
        val = s.length > 60 ? `${s.slice(0, 57)}…` : s;
      }
      return `${k}=${val}`;
    })
    .join('  ');
}

export function renderConfirmationDetails(
  details: Record<string, unknown>
): void {
  const tools = extractPendingTools(details);
  const message = typeof details.message === 'string' ? details.message : '';

  p.log.warn('⚠  Confirmation required');
  if (tools.length === 0) {
    if (message) p.log.message(message);
    else
      p.log.message('The agent is paused and needs your approval to continue.');
    p.log.message('Reply  y  to allow,  n  to cancel.');
    return;
  }

  p.log.message(
    `The agent wants to run ${tools.length} action${tools.length === 1 ? '' : 's'} that will modify your data:`
  );
  for (const t of tools) {
    const label = TOOL_LABELS[t.name] ?? t.name;
    const argSummary = summarizeArgs(t.args);
    p.log.message(
      `  • ${label}  (${t.name})${argSummary ? `\n      ${argSummary}` : ''}`
    );
  }
  p.log.message('Reply  y  to allow,  n  to cancel.');
}

export function confirmationPromptMessage(
  details: Record<string, unknown>
): string {
  const tools = extractPendingTools(details);
  if (tools.length === 0) return 'Allow the agent to continue?';
  if (tools.length === 1) {
    const label = TOOL_LABELS[tools[0].name] ?? tools[0].name;
    return `Allow: ${label}?`;
  }
  return `Allow these ${tools.length} actions?`;
}
