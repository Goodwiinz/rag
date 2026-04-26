import * as p from '@clack/prompts';
import { loadConfig, saveConfig } from './auth/store';
import { parseSlashCommand } from './hooks/useSlashCommands';
import { streamAgent, streamConfirm } from './stream';
import {
  fetchThreadMessages,
  fetchThreads,
  type RemoteThreadSummary,
} from './services/threads';
import {
  derivePreview,
  deriveTitle,
  getThread,
  listThreads,
  reconcileThreads,
  removeThread,
  touchThread,
  upsertThread,
  type ThreadEntry,
} from './services/threadStore';
import { fetchProjects, type RemoteProjectSummary } from './services/projects';
import { countVisualRows, hasMarkdown, renderMarkdown } from './markdown';
import { buildCompleter, isPromptCancel, readPrompt } from './prompt';
import { classifyError } from './errors';

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

  p.intro(`NOUS  ·  ${formatStatus(threadId, activeProject)}`);

  const abort = new AbortController();
  process.once('SIGINT', () => {
    abort.abort();
    p.outro('Bye.');
    process.exit(0);
  });

  while (true) {
    const completer = buildCompleter({
      knownThreadIds: listThreads().map((t) => t.id),
    });
    const raw = await readPrompt({ message: '>', completer });
    if (isPromptCancel(raw) || p.isCancel(raw)) {
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

    const previousThreadId = threadId;
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

    if (threadId) {
      recordThreadUse(threadId, previousThreadId, input, activeProject);
    }
  }
}

export async function runOneShot(
  query: string,
  pageContext: Record<string, unknown> = {}
): Promise<void> {
  await streamToTerminal(query, pageContext);
}

function formatStatus(
  threadId: string | null,
  activeProject: ActiveProject | null
): string {
  if (!threadId) {
    const parts = ['no thread'];
    if (activeProject) parts.push(`project: ${activeProject.name}`);
    return parts.join('  ·  ');
  }
  const entry = getThread(threadId);
  const short = threadId.slice(0, 8);
  const label = entry
    ? `thread: ${short} · "${entry.title}"`
    : `thread: ${short}`;
  const parts = [label];
  if (activeProject) parts.push(`project: ${activeProject.name}`);
  return parts.join('  ·  ');
}

function recordThreadUse(
  threadId: string,
  previousThreadId: string | null,
  userInput: string,
  activeProject: ActiveProject | null
): void {
  const isNewThread = previousThreadId !== threadId;
  const existing = getThread(threadId);
  if (isNewThread || !existing) {
    upsertThread({
      id: threadId,
      title: deriveTitle(userInput),
      preview: derivePreview(userInput),
      project_id: activeProject?.id ?? null,
      project_name: activeProject?.name ?? null,
    });
  } else {
    upsertThread({
      id: threadId,
      preview: derivePreview(userInput),
    });
  }
}

async function streamToTerminal(
  message: string,
  pageContext: Record<string, unknown>,
  signal?: AbortSignal
): Promise<void> {
  const spinners = new Map<string, ReturnType<typeof p.spinner>>();
  const collectedContexts: Array<Record<string, unknown>> = [];
  let lastUsage: {
    inputTokens: number;
    outputTokens: number;
    costUsd: number | null;
  } | null = null;
  let tokenBuffer = '';
  let retriedAfterMissingThread = false;
  let inConfirmFlow = false;
  let postConfirmTokens = false;

  process.stdout.write('\n');

  type EventStream = AsyncGenerator<import('./stream').StreamEvent>;
  let current: EventStream = streamAgent(message, pageContext, { signal });

  while (true) {
    let pendingConfirmThreadId: string | null = null;
    let retryFreshThread = false;

    for await (const event of current) {
      if (event.type === 'token') {
        process.stdout.write(event.content);
        tokenBuffer += event.content;
        if (inConfirmFlow) postConfirmTokens = true;
      } else if (event.type === 'tool_start') {
        const s = p.spinner();
        s.start(formatToolLine(event.tool, event.args));
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
          collectedContexts.push(...event.contexts);
          p.log.info(`Retrieved ${event.contexts.length} context(s)`);
        }
      } else if (event.type === 'usage') {
        lastUsage = {
          inputTokens: event.inputTokens,
          outputTokens: event.outputTokens,
          costUsd: event.costUsd,
        };
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
        process.stdout.write('\n');
        maybeReformatMarkdown(tokenBuffer);
        renderCitationsFooter(collectedContexts);
        renderUsageLine(lastUsage);
        if (inConfirmFlow && !postConfirmTokens) {
          p.log.success('Actions completed.');
        }
        process.stdout.write('\n');
        return;
      } else if (event.type === 'error') {
        process.stdout.write('\n');
        const classified = classifyError(event.message);
        if (
          classified.kind === 'not_found_thread' &&
          !retriedAfterMissingThread
        ) {
          clearCachedThreadId();
          retriedAfterMissingThread = true;
          retryFreshThread = true;
          p.log.warn(
            `${classified.userMessage} ${classified.hint ?? ''}`.trim()
          );
          break;
        }
        p.log.error(classified.userMessage);
        if (classified.hint) p.log.message(`  ${classified.hint}`);
        return;
      }
    }

    if (retryFreshThread) {
      current = streamAgent(message, pageContext, { signal });
      continue;
    }

    if (pendingConfirmThreadId === null) break;

    inConfirmFlow = true;
    postConfirmTokens = false;
    current = streamConfirm(pendingConfirmThreadId, true, { signal });
  }
}

function clearCachedThreadId(): void {
  const cfg = loadConfig();
  if (cfg && cfg.thread_id !== null) {
    saveConfig({ ...cfg, thread_id: null });
  }
}

function formatToolLine(tool: string, args: string): string {
  const compact = compactArgs(args);
  return compact ? `${tool} ${compact}` : tool;
}

const MD_INPLACE_MAX_ROWS = 200;
const MD_DISABLED = process.env.NOUS_MD === '0';

export function maybeReformatMarkdown(buffer: string): void {
  if (MD_DISABLED) return;
  if (!buffer || !hasMarkdown(buffer)) return;
  const cols = process.stdout.columns ?? 80;
  // We already wrote a trailing '\n' on done, so the cursor is one row
  // below the last visible line of the buffer. Account for that.
  const rows = countVisualRows(buffer, cols) + 1;
  if (rows > MD_INPLACE_MAX_ROWS) return;
  if (!process.stdout.isTTY) return;
  process.stdout.write(`\x1b[${rows}F\x1b[J`);
  process.stdout.write(renderMarkdown(buffer));
  if (!buffer.endsWith('\n')) process.stdout.write('\n');
}

function compactArgs(raw: string): string {
  if (!raw) return '';
  const cleaned = raw.replace(/\s+/g, ' ').trim();
  if (cleaned.length === 0) return '';
  const max = 80;
  return cleaned.length > max ? `${cleaned.slice(0, max - 1)}…` : cleaned;
}

export function renderCitationsFooter(
  contexts: Array<Record<string, unknown>>
): void {
  if (contexts.length === 0) return;
  const seen = new Set<string>();
  const unique: Array<Record<string, unknown>> = [];
  for (const ctx of contexts) {
    const key = `${ctx.document_id ?? ''}::${ctx.title ?? ''}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(ctx);
    if (unique.length >= 5) break;
  }
  if (unique.length === 0) return;

  p.log.message('— Citations —');
  unique.forEach((ctx, idx) => {
    const title =
      typeof ctx.title === 'string' && ctx.title ? ctx.title : 'Untitled';
    const docId =
      typeof ctx.document_id === 'string' ? ctx.document_id.slice(0, 8) : null;
    const score = typeof ctx.score === 'number' ? ctx.score.toFixed(2) : null;
    const meta = [
      docId ? `doc ${docId}` : null,
      score ? `score ${score}` : null,
    ]
      .filter(Boolean)
      .join(' · ');
    const suffix = meta ? `  (${meta})` : '';
    p.log.message(`  [${idx + 1}] ${title}${suffix}`);
  });
}

export function renderUsageLine(
  usage: {
    inputTokens: number;
    outputTokens: number;
    costUsd: number | null;
  } | null
): void {
  if (!usage) return;
  if (usage.inputTokens === 0 && usage.outputTokens === 0) return;
  const cost =
    usage.costUsd !== null && usage.costUsd > 0
      ? ` · $${usage.costUsd.toFixed(4)}`
      : '';
  p.log.message(`→ ${usage.inputTokens} in / ${usage.outputTokens} out${cost}`);
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
    if (!ctx.threadId) {
      p.log.info('Thread: none');
      return true;
    }
    const entry = getThread(ctx.threadId);
    if (entry) {
      p.log.info(`Thread: ${ctx.threadId}`);
      p.log.message(`  title: ${entry.title}`);
      if (entry.project_name) p.log.message(`  project: ${entry.project_name}`);
      p.log.message(`  last used: ${formatRelative(entry.last_used_at)}`);
    } else {
      p.log.info(`Thread: ${ctx.threadId}`);
    }
    return true;
  }
  if (command === 'threads') {
    await handleThreadsCommand(ctx);
    return true;
  }
  if (command === 'history') {
    await handleHistoryCommand(ctx, args);
    return true;
  }
  if (command === 'forget') {
    handleForgetCommand(ctx, args);
    return true;
  }
  if (command === 'projects') {
    await handleProjectsCommand(ctx);
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
  if (command === 'settings') {
    await handleSettingsCommand(args);
    return true;
  }
  if (command === 'help') {
    p.log.message(
      '/new  /thread  /threads  /history [n]  /forget [id]  /projects  /context project <id> [name]  /context clear  /settings [set api_url <url>]  /quit'
    );
    return true;
  }
  return false;
}

async function handleProjectsCommand(ctx: SlashContext): Promise<void> {
  const spinner = p.spinner();
  spinner.start('Loading projects');
  let projects: RemoteProjectSummary[] = [];
  try {
    projects = await fetchProjects();
    spinner.stop(`Loaded ${projects.length} project(s)`);
  } catch (err) {
    spinner.stop('Failed to load projects');
    p.log.error((err as Error).message);
    return;
  }

  if (projects.length === 0) {
    p.log.info('No projects yet. Create one in the web app first.');
    return;
  }

  const sorted = [...projects].sort((a, b) =>
    (b.updated_at || '').localeCompare(a.updated_at || '')
  );

  const choice = await p.select({
    message: 'Pick a project (esc to cancel)',
    options: [
      { value: '__clear__', label: '× Clear project context' },
      ...sorted.map((proj) => ({
        value: proj.id,
        label: formatProjectLabel(proj, ctx.activeProject?.id ?? null),
        hint: projectHint(proj),
      })),
      { value: '__cancel__', label: '(cancel)' },
    ],
  });

  if (p.isCancel(choice) || choice === '__cancel__') return;

  if (choice === '__clear__') {
    ctx.onProjectChange(null);
    p.log.success('Project context cleared.');
    return;
  }

  const picked = sorted.find((p) => p.id === choice);
  if (!picked) return;
  ctx.onProjectChange({ id: picked.id, name: picked.name });
  p.log.success(`Project set: ${picked.name}`);
}

function formatProjectLabel(
  proj: RemoteProjectSummary,
  activeId: string | null
): string {
  const marker = proj.id === activeId ? '● ' : '  ';
  const when = proj.updated_at ? formatRelative(proj.updated_at) : '';
  return `${marker}${proj.name}  ·  ${proj.id.slice(0, 8)}${when ? `  ·  ${when}` : ''}`;
}

function projectHint(proj: RemoteProjectSummary): string | undefined {
  const parts: string[] = [];
  if (proj.document_count > 0) parts.push(`${proj.document_count} docs`);
  if (proj.note_count > 0) parts.push(`${proj.note_count} notes`);
  if (proj.draft_count > 0) parts.push(`${proj.draft_count} drafts`);
  return parts.length > 0 ? parts.join(' · ') : undefined;
}

async function handleThreadsCommand(ctx: SlashContext): Promise<void> {
  const spinner = p.spinner();
  spinner.start('Loading threads');
  let remote: RemoteThreadSummary[] = [];
  try {
    remote = await fetchThreads();
    spinner.stop(`Loaded ${remote.length} thread(s)`);
  } catch (err) {
    spinner.stop('Failed to load threads from server');
    p.log.warn((err as Error).message);
  }

  const local = listThreads();
  const merged = mergeThreads(local, remote);

  if (remote.length > 0) {
    reconcileThreads(remote.map((t) => t.id));
  }

  if (merged.length === 0) {
    p.log.info('No threads yet. Send a message to start one.');
    return;
  }

  const choice = await p.select({
    message: 'Pick a thread (esc to cancel)',
    options: [
      ...merged.map((entry) => ({
        value: entry.id,
        label: formatThreadLabel(entry, ctx.threadId),
        hint: entry.preview ? entry.preview : undefined,
      })),
      { value: '__cancel__', label: '(cancel)' },
    ],
  });

  if (p.isCancel(choice) || choice === '__cancel__') return;

  const picked = merged.find((e) => e.id === choice);
  if (!picked) return;

  const cfg = loadConfig();
  if (cfg) saveConfig({ ...cfg, thread_id: picked.id });
  touchThread(picked.id);
  ctx.onThreadChange(picked.id);
  p.log.success(`Switched to "${picked.title}" (${picked.id.slice(0, 8)})`);
}

async function handleHistoryCommand(
  ctx: SlashContext,
  args: string[]
): Promise<void> {
  if (!ctx.threadId) {
    p.log.warn('No active thread. Use /threads to pick one.');
    return;
  }
  const limit = parseLimit(args[0], 10);

  const spinner = p.spinner();
  spinner.start('Loading history');
  try {
    const messages = await fetchThreadMessages(ctx.threadId);
    spinner.stop(`${messages.length} message(s)`);

    if (messages.length === 0) {
      p.log.info('No messages in this thread.');
      return;
    }
    const tail = messages.slice(-limit);
    for (const msg of tail) {
      renderHistoryMessage(msg);
    }
  } catch (err) {
    spinner.stop('Failed to load history');
    p.log.error((err as Error).message);
  }
}

function handleForgetCommand(ctx: SlashContext, args: string[]): void {
  const target = args[0] ?? ctx.threadId;
  if (!target) {
    p.log.warn('No thread to forget. Pass an id or have an active thread.');
    return;
  }
  const removed = removeThread(target);
  if (!removed) {
    p.log.warn(`No local entry for ${target.slice(0, 8)}.`);
  } else {
    p.log.success(`Forgot ${target.slice(0, 8)} (server copy untouched).`);
  }
  if (ctx.threadId === target) {
    const cfg = loadConfig();
    if (cfg) saveConfig({ ...cfg, thread_id: null });
    ctx.onThreadChange(null);
  }
}

const EDITABLE_SETTINGS = ['api_url', 'model'] as const;
type EditableSetting = (typeof EDITABLE_SETTINGS)[number];

const SUPPORTED_MODELS = [
  { value: '', label: '(server default)' },
  { value: 'model-router', label: 'model-router  — auto-route' },
  { value: 'gpt-4o', label: 'gpt-4o' },
  { value: 'gpt-4o-mini', label: 'gpt-4o-mini' },
  { value: 'gpt-5', label: 'gpt-5' },
  { value: 'gpt-5-mini', label: 'gpt-5-mini' },
  { value: 'gpt-5-nano', label: 'gpt-5-nano' },
  { value: 'gpt-5-chat', label: 'gpt-5-chat' },
  { value: 'gpt-5.2', label: 'gpt-5.2' },
  { value: 'gpt-5.2-chat', label: 'gpt-5.2-chat' },
  { value: 'o4-mini', label: 'o4-mini' },
  { value: 'claude-sonnet-4-5', label: 'claude-sonnet-4-5' },
  { value: 'claude-haiku-4-5', label: 'claude-haiku-4-5' },
];

async function handleSettingsCommand(args: string[]): Promise<void> {
  const cfg = loadConfig();
  if (!cfg) {
    p.log.error('Not logged in.');
    return;
  }

  if (args[0] === 'set') {
    const key = args[1] as EditableSetting | undefined;
    const value = args[2];
    if (!key || value === undefined) {
      p.log.warn('Usage: /settings set <api_url|model> <value>');
      return;
    }
    if (!EDITABLE_SETTINGS.includes(key)) {
      p.log.warn(
        `Unknown setting "${key}". Editable: ${EDITABLE_SETTINGS.join(', ')}`
      );
      return;
    }
    if (key === 'model') {
      const valid = SUPPORTED_MODELS.map((m) => m.value);
      if (!valid.includes(value)) {
        p.log.warn(
          `Unknown model "${value}". Supported: ${valid.filter(Boolean).join(', ')}`
        );
        return;
      }
    }
    saveConfig({ ...cfg, [key]: value });
    p.log.success(`${key} → ${value || '(server default)'}`);
    return;
  }

  const modelLabel =
    SUPPORTED_MODELS.find((m) => m.value === (cfg.model ?? ''))?.label ??
    cfg.model ??
    '(server default)';
  p.log.message('Current settings:');
  p.log.message(`  email      ${cfg.user_email}`);
  p.log.message(`  org        ${cfg.organization_id}`);
  p.log.message(`  api_url    ${cfg.api_url ?? '(default)'}`);
  p.log.message(`  model      ${modelLabel}`);
  const expiry = formatRelative(cfg.expires_at);
  p.log.message(`  token      expires ${expiry}`);
  p.log.message(`  config     ~/.nous/config.json`);

  if (args[0] === undefined) {
    const action = await p.select({
      message: 'Edit a setting?',
      options: [
        { value: 'model', label: 'model — deployment to use' },
        { value: 'api_url', label: 'api_url — backend URL' },
        { value: '__done__', label: '(done)' },
      ],
    });
    if (p.isCancel(action) || action === '__done__') return;

    if (action === 'model') {
      const next = await p.select({
        message: 'Select model',
        options: SUPPORTED_MODELS.map((m) => ({
          ...m,
          label:
            m.value === (cfg.model ?? '') ? `● ${m.label}` : `  ${m.label}`,
        })),
      });
      if (p.isCancel(next)) return;
      saveConfig({ ...cfg, model: next as string });
      const label =
        SUPPORTED_MODELS.find((m) => m.value === next)?.label ?? String(next);
      p.log.success(`model → ${label}`);
      return;
    }

    const current = cfg[action as EditableSetting] ?? '';
    const next = await p.text({
      message: `New value for ${action as string}`,
      initialValue: current,
      placeholder: 'https://api.example.com',
    });
    if (p.isCancel(next) || !next) return;
    saveConfig({ ...cfg, [action as string]: next as string });
    p.log.success(`${action as string} → ${next as string}`);
  }
}

function mergeThreads(
  local: ThreadEntry[],
  remote: RemoteThreadSummary[]
): ThreadEntry[] {
  const byId = new Map<string, ThreadEntry>();
  for (const entry of local) byId.set(entry.id, entry);

  for (const r of remote) {
    const existing = byId.get(r.id);
    const titleCandidate = r.title ?? existing?.title ?? '(untitled)';
    const lastUsed =
      r.last_message_at ?? r.updated_at ?? existing?.last_used_at ?? '';
    byId.set(r.id, {
      id: r.id,
      title: titleCandidate || '(untitled)',
      project_id: r.source_project_id ?? existing?.project_id ?? null,
      project_name: existing?.project_name ?? null,
      last_used_at: lastUsed,
      preview: existing?.preview ?? '',
    });
  }

  return Array.from(byId.values()).sort((a, b) =>
    b.last_used_at.localeCompare(a.last_used_at)
  );
}

function formatThreadLabel(
  entry: ThreadEntry,
  activeId: string | null
): string {
  const marker = entry.id === activeId ? '● ' : '  ';
  const when = formatRelative(entry.last_used_at);
  return `${marker}${entry.title}  ·  ${entry.id.slice(0, 8)}  ·  ${when}`;
}

function formatRelative(iso: string): string {
  if (!iso) return 'unknown';
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return iso;
  const diffMs = Date.now() - then;
  const sec = Math.round(diffMs / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 30) return `${day}d ago`;
  return new Date(then).toISOString().slice(0, 10);
}

function parseLimit(arg: string | undefined, fallback: number): number {
  if (!arg) return fallback;
  const n = Number.parseInt(arg, 10);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return Math.min(n, 100);
}

function renderHistoryMessage(msg: {
  role: string;
  content: string;
  tool_name: string | null;
  created_at: string;
}): void {
  const when = formatRelative(msg.created_at);
  const role = msg.role.toLowerCase();
  if (role === 'tool') {
    const label = msg.tool_name ?? 'tool';
    p.log.message(`[${when}] ⚙ ${label}: ${truncate(msg.content, 200)}`);
    return;
  }
  if (role === 'user') {
    p.log.message(`[${when}] ▸ you: ${truncate(msg.content, 400)}`);
    return;
  }
  p.log.message(`[${when}] ◂ agent: ${truncate(msg.content, 400)}`);
}

function truncate(text: string, max: number): string {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, max - 1)}…`;
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
