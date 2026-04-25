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
      ? { type: 'project', project_id: activeProject.id, project_name: activeProject.name }
      : { type: 'chat' };

    await streamToTerminal(input, ctx, abort.signal);

    const updated = loadConfig();
    if (updated?.thread_id && updated.thread_id !== threadId) {
      threadId = updated.thread_id;
    }
  }
}

export async function runOneShot(
  query: string,
  pageContext: Record<string, unknown> = {},
): Promise<void> {
  await streamToTerminal(query, pageContext);
}

async function streamToTerminal(
  message: string,
  pageContext: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<void> {
  const spinners = new Map<string, ReturnType<typeof p.spinner>>();

  process.stdout.write('\n');

  type EventStream = AsyncGenerator<import('./stream').StreamEvent>;
  let current: EventStream = streamAgent(message, pageContext, { signal });
  let isResumeIteration = false;

  while (true) {
    let pendingConfirmThreadId: string | null = null;
    let renderedThisIteration = false;

    for await (const event of current) {
      if (event.type === 'token') {
        process.stdout.write(event.content);
        renderedThisIteration = true;
      } else if (event.type === 'tool_start') {
        const s = p.spinner();
        s.start(event.tool);
        spinners.set(event.tool, s);
        renderedThisIteration = true;
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
        renderedThisIteration = true;
      } else if (event.type === 'plan') {
        if (event.steps.length > 0) {
          p.log.info(`Plan: ${event.steps.join(' → ')}`);
          renderedThisIteration = true;
        }
      } else if (event.type === 'reflection') {
        if (event.passed) {
          p.log.success(`Reflection #${event.round} passed`);
        } else {
          p.log.warn(
            `Reflection #${event.round}: ${event.issues.length > 0 ? event.issues.join('; ') : 'failed'}`,
          );
        }
        renderedThisIteration = true;
      } else if (event.type === 'rag_context') {
        if (event.contexts.length > 0) {
          p.log.info(`Retrieved ${event.contexts.length} context(s)`);
          renderedThisIteration = true;
        }
      } else if (event.type === 'confirmation') {
        for (const [tool, s] of spinners) {
          s.cancel(`${tool} (paused — awaiting confirmation)`);
        }
        spinners.clear();
        process.stdout.write('\n');
        const ok = await p.confirm({ message: 'Agent wants to proceed. Allow?' });
        if (p.isCancel(ok) || !ok) {
          p.log.warn('Cancelled.');
          return;
        }
        p.log.info('Resuming agent…');
        pendingConfirmThreadId = event.threadId;
        break;
      } else if (event.type === 'done') {
        if (isResumeIteration && !renderedThisIteration) {
          p.log.message('Agent finished (no further output)');
        }
        process.stdout.write('\n\n');
        return;
      } else if (event.type === 'error') {
        process.stdout.write('\n');
        p.log.error(event.message);
        return;
      }
    }

    if (pendingConfirmThreadId === null) break;

    current = streamConfirm(pendingConfirmThreadId, true, { signal });
    isResumeIteration = true;
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
  ctx: SlashContext,
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
    p.log.message('/new  /thread  /context project <id> [name]  /context clear  /quit');
    return true;
  }
  return false;
}
