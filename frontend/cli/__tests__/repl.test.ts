/**
 * @jest-environment node
 */
import { mkdtempSync, rmSync } from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as prompts from '@clack/prompts';
import {
  confirmationPromptMessage,
  renderCitationsFooter,
  renderConfirmationDetails,
  renderUsageLine,
  runRepl,
} from '../repl';
import * as store from '../auth/store';
import * as stream from '../stream';

jest.mock('@clack/prompts', () => ({
  text: jest.fn(),
  confirm: jest.fn(),
  select: jest.fn(),
  isCancel: jest.fn((value) => value === '__CANCEL__'),
  intro: jest.fn(),
  outro: jest.fn(),
  spinner: jest.fn(() => ({
    start: jest.fn(),
    stop: jest.fn(),
    error: jest.fn(),
    cancel: jest.fn(),
  })),
  log: {
    error: jest.fn(),
    info: jest.fn(),
    message: jest.fn(),
    success: jest.fn(),
    warn: jest.fn(),
  },
}));

jest.mock('../auth/store');
jest.mock('../stream');
jest.mock('../services/threads', () => ({
  fetchThreads: jest.fn(),
  fetchThreadMessages: jest.fn(),
}));
jest.mock('../services/projects', () => ({
  fetchProjects: jest.fn(),
}));

let tmpConfigDir: string;

const mockedText = prompts.text as jest.MockedFunction<typeof prompts.text>;
const mockedConfirm = prompts.confirm as jest.MockedFunction<
  typeof prompts.confirm
>;
const mockedLog = prompts.log as jest.Mocked<typeof prompts.log>;
const mockedLoadConfig = store.loadConfig as jest.MockedFunction<
  typeof store.loadConfig
>;
const mockedSaveConfig = store.saveConfig as jest.MockedFunction<
  typeof store.saveConfig
>;
const mockedStreamAgent = stream.streamAgent as jest.MockedFunction<
  typeof stream.streamAgent
>;
const mockedStreamConfirm = stream.streamConfirm as jest.MockedFunction<
  typeof stream.streamConfirm
>;

const CONFIG: store.NousConfig = {
  token: 'tok_test',
  user_email: 'a@b.com',
  organization_id: 'org_1',
  expires_at: '2099-01-01T00:00:00Z',
  thread_id: 'stale-thread',
};

async function* events(items: stream.StreamEvent[]) {
  for (const item of items) yield item;
}

beforeEach(() => {
  tmpConfigDir = mkdtempSync(path.join(os.tmpdir(), 'nous-repl-test-'));
  process.env.NOUS_CONFIG_DIR = tmpConfigDir;
  let config = { ...CONFIG };
  mockedLoadConfig.mockReset();
  mockedSaveConfig.mockReset();
  mockedText.mockReset();
  mockedConfirm.mockReset();
  mockedStreamAgent.mockReset();
  mockedStreamConfirm.mockReset();
  mockedLog.error.mockReset();
  mockedLog.info.mockReset();
  mockedLog.message.mockReset();
  mockedLog.success.mockReset();
  mockedLog.warn.mockReset();
  mockedLoadConfig.mockImplementation(() => config);
  mockedSaveConfig.mockImplementation((next) => {
    config = next;
  });
  mockedText
    .mockResolvedValueOnce('hi' as never)
    .mockResolvedValueOnce('__CANCEL__' as never);
  mockedConfirm.mockResolvedValue(true as never);
  jest.spyOn(process.stdout, 'write').mockImplementation(() => true);
});

afterEach(() => {
  jest.restoreAllMocks();
  rmSync(tmpConfigDir, { recursive: true, force: true });
  delete process.env.NOUS_CONFIG_DIR;
});

test('clears a missing confirmation thread and retries the message once', async () => {
  mockedStreamAgent
    .mockReturnValueOnce(
      events([
        {
          type: 'confirmation',
          threadId: 'stale-thread',
          details: { message: 'Confirm?' },
        },
      ])
    )
    .mockReturnValueOnce(
      events([{ type: 'token', content: 'fresh response' }, { type: 'done' }])
    );
  mockedStreamConfirm.mockReturnValue(
    events([{ type: 'error', message: 'Thread not found' }])
  );

  await runRepl();

  expect(mockedStreamConfirm).toHaveBeenCalledWith(
    'stale-thread',
    true,
    expect.any(Object)
  );
  expect(mockedSaveConfig).toHaveBeenCalledWith(
    expect.objectContaining({ thread_id: null })
  );
  expect(mockedStreamAgent).toHaveBeenCalledTimes(2);
  expect(mockedStreamAgent).toHaveBeenNthCalledWith(
    2,
    'hi',
    { type: 'chat' },
    expect.any(Object)
  );
  expect(mockedLog.warn).toHaveBeenCalledWith(
    expect.stringContaining('Cached thread expired')
  );
});

describe('confirmation rendering', () => {
  test('lists each pending destructive tool with a friendly label', () => {
    renderConfirmationDetails({
      tools: [
        {
          name: 'ingest_arxiv_papers',
          args: { arxiv_ids: ['2310.11522'] },
        },
        {
          name: 'create_draft',
          args: {
            title: 'My draft',
            source_document_ids: ['a', 'b', 'c', 'd'],
          },
        },
      ],
      message: 'Confirm?',
    });

    expect(mockedLog.warn).toHaveBeenCalledWith('⚠  Confirmation required');
    const messages = mockedLog.message.mock.calls.map((c) => c[0]);
    expect(
      messages.some((m) => /will modify your data/.test(m as string))
    ).toBe(true);
    expect(
      messages.some((m) => /Download & index arXiv/.test(m as string))
    ).toBe(true);
    expect(
      messages.some((m) => /Generate draft document/.test(m as string))
    ).toBe(true);
    expect(messages.some((m) => /\[4 items\]/.test(m as string))).toBe(true);
    expect(messages.some((m) => /Reply  y  to allow/.test(m as string))).toBe(
      true
    );
  });

  test('falls back to backend message when no tools are sent', () => {
    renderConfirmationDetails({ message: 'Confirm: ingest_arxiv_papers?' });
    const messages = mockedLog.message.mock.calls.map((c) => c[0]);
    expect(messages).toContain('Confirm: ingest_arxiv_papers?');
  });

  test('prompt summarizes single vs multi tool', () => {
    expect(
      confirmationPromptMessage({
        tools: [{ name: 'create_project', args: {} }],
      })
    ).toBe('Allow: Create new project?');
    expect(
      confirmationPromptMessage({
        tools: [
          { name: 'create_project', args: {} },
          { name: 'create_draft', args: {} },
        ],
      })
    ).toBe('Allow these 2 actions?');
    expect(confirmationPromptMessage({})).toBe('Allow the agent to continue?');
  });
});

describe('thread registry side effects', () => {
  test('records the user prompt as a thread title in the local registry', async () => {
    mockedText.mockReset();
    mockedText
      .mockResolvedValueOnce('Summarise the latest arXiv on RAG' as never)
      .mockResolvedValueOnce('__CANCEL__' as never);
    mockedStreamAgent.mockReturnValueOnce(
      events([{ type: 'token', content: 'ok' }, { type: 'done' }])
    );

    await runRepl();

    const reg = require('../services/threadStore').loadRegistry();
    expect(reg.entries).toHaveLength(1);
    expect(reg.entries[0].id).toBe('stale-thread');
    expect(reg.entries[0].title).toBe('Summarise the latest arXiv on RAG');
  });
});

describe('slash commands: threads/history/forget', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const threadsModule = require('../services/threads') as {
    fetchThreads: jest.Mock;
    fetchThreadMessages: jest.Mock;
  };
  const fetchThreadsMock = threadsModule.fetchThreads;
  const fetchMessagesMock = threadsModule.fetchThreadMessages;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mockedSelect = (prompts as any).select as jest.Mock;

  beforeEach(() => {
    fetchThreadsMock.mockReset();
    fetchMessagesMock.mockReset();
    mockedSelect.mockReset();
  });

  test('/threads switches to the picked thread', async () => {
    const store = require('../services/threadStore');
    store.upsertThread({ id: 'thread-A', title: 'Older' });
    store.upsertThread({ id: 'thread-B', title: 'Newer' });

    fetchThreadsMock.mockResolvedValueOnce([]);
    mockedText.mockReset();
    mockedText
      .mockResolvedValueOnce('/threads' as never)
      .mockResolvedValueOnce('__CANCEL__' as never);
    mockedSelect.mockResolvedValueOnce('thread-A' as never);

    await runRepl();

    expect(fetchThreadsMock).toHaveBeenCalled();
    expect(mockedSaveConfig).toHaveBeenCalledWith(
      expect.objectContaining({ thread_id: 'thread-A' })
    );
  });

  test('/history prints fetched messages', async () => {
    fetchMessagesMock.mockResolvedValueOnce([
      {
        id: 'm1',
        role: 'user',
        content: 'first ask',
        created_at: new Date().toISOString(),
        tool_name: null,
        tool_call_id: null,
        citations: null,
        tool_executions: null,
      },
      {
        id: 'm2',
        role: 'assistant',
        content: 'first reply',
        created_at: new Date().toISOString(),
        tool_name: null,
        tool_call_id: null,
        citations: null,
        tool_executions: null,
      },
    ]);
    mockedText.mockReset();
    mockedText
      .mockResolvedValueOnce('/history 5' as never)
      .mockResolvedValueOnce('__CANCEL__' as never);

    await runRepl();

    expect(fetchMessagesMock).toHaveBeenCalledWith('stale-thread');
    const messages = mockedLog.message.mock.calls.map((c) => c[0] as string);
    expect(messages.some((m) => m.includes('you: first ask'))).toBe(true);
    expect(messages.some((m) => m.includes('agent: first reply'))).toBe(true);
  });

  test('/forget removes from registry and clears the active thread', async () => {
    const store = require('../services/threadStore');
    store.upsertThread({ id: 'stale-thread', title: 'To remove' });

    mockedText.mockReset();
    mockedText
      .mockResolvedValueOnce('/forget' as never)
      .mockResolvedValueOnce('__CANCEL__' as never);

    await runRepl();

    expect(store.getThread('stale-thread')).toBeNull();
    expect(mockedSaveConfig).toHaveBeenCalledWith(
      expect.objectContaining({ thread_id: null })
    );
  });
});

describe('streamToTerminal: tool args, citations footer, usage', () => {
  test('passes tool args into the spinner label', async () => {
    const startSpy = jest.fn();
    const stopSpy = jest.fn();
    const spinnerFactory = prompts.spinner as unknown as jest.Mock;
    spinnerFactory.mockImplementation(() => ({
      start: startSpy,
      stop: stopSpy,
      error: jest.fn(),
      cancel: jest.fn(),
    }));

    mockedStreamAgent.mockReturnValueOnce(
      events([
        { type: 'tool_start', tool: 'search_documents', args: 'query=foo' },
        { type: 'tool_end', tool: 'search_documents', isError: false },
        { type: 'done' },
      ])
    );

    await runRepl();

    expect(startSpy).toHaveBeenCalledWith(
      expect.stringContaining('search_documents')
    );
    expect(startSpy).toHaveBeenCalledWith(expect.stringContaining('query=foo'));
  });

  test('renders a citations footer on done when rag_context arrived', async () => {
    mockedStreamAgent.mockReturnValueOnce(
      events([
        {
          type: 'rag_context',
          contexts: [
            {
              document_id: 'doc-aaaaaaaa-1',
              title: 'Paper One',
              score: 0.91,
            },
            {
              document_id: 'doc-bbbbbbbb-2',
              title: 'Paper Two',
              score: 0.42,
            },
            // duplicate of the first — should dedupe
            {
              document_id: 'doc-aaaaaaaa-1',
              title: 'Paper One',
              score: 0.91,
            },
          ],
        },
        { type: 'token', content: 'reply' },
        { type: 'done' },
      ])
    );

    await runRepl();

    const messages = mockedLog.message.mock.calls.map((c) => c[0] as string);
    expect(messages.some((m) => /— Citations —/.test(m))).toBe(true);
    expect(messages.some((m) => /\[1\] Paper One/.test(m))).toBe(true);
    expect(messages.some((m) => /\[2\] Paper Two/.test(m))).toBe(true);
    // The duplicate (doc-aaaaaaaa-1) must not yield a [3] line
    expect(messages.some((m) => /\[3\]/.test(m))).toBe(false);
  });

  test('prints a usage line when a usage event is received', async () => {
    mockedStreamAgent.mockReturnValueOnce(
      events([
        { type: 'token', content: 'hi' },
        {
          type: 'usage',
          inputTokens: 312,
          outputTokens: 540,
          costUsd: 0.0042,
        },
        { type: 'done' },
      ])
    );

    await runRepl();

    const messages = mockedLog.message.mock.calls.map((c) => c[0] as string);
    expect(
      messages.some((m) => /→ 312 in \/ 540 out · \$0\.0042/.test(m))
    ).toBe(true);
  });
});

describe('renderCitationsFooter / renderUsageLine (pure helpers)', () => {
  test('renderCitationsFooter is a no-op when no contexts', () => {
    renderCitationsFooter([]);
    const messages = mockedLog.message.mock.calls.map((c) => c[0] as string);
    expect(messages.some((m) => /Citations/.test(m))).toBe(false);
  });

  test('renderUsageLine skips when both counts are zero', () => {
    renderUsageLine({ inputTokens: 0, outputTokens: 0, costUsd: null });
    const messages = mockedLog.message.mock.calls.map((c) => c[0] as string);
    expect(messages.some((m) => /in \/ /.test(m))).toBe(false);
  });

  test('renderUsageLine omits cost when null or zero', () => {
    renderUsageLine({ inputTokens: 5, outputTokens: 10, costUsd: null });
    const messages = mockedLog.message.mock.calls.map((c) => c[0] as string);
    expect(messages.some((m) => /→ 5 in \/ 10 out$/.test(m))).toBe(true);
  });
});

describe('slash commands: /projects', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const projectsModule = require('../services/projects') as {
    fetchProjects: jest.Mock;
  };
  const fetchProjectsMock = projectsModule.fetchProjects;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mockedSelect = (prompts as any).select as jest.Mock;

  beforeEach(() => {
    fetchProjectsMock.mockReset();
    mockedSelect.mockReset();
  });

  test('/projects sets the active project from the picker', async () => {
    fetchProjectsMock.mockResolvedValueOnce([
      {
        id: 'proj_1',
        name: 'Alpha',
        description: null,
        project_type: 'research',
        research_status: 'active',
        document_count: 3,
        note_count: 1,
        draft_count: 0,
        updated_at: '2026-04-25T00:00:00Z',
      },
      {
        id: 'proj_2',
        name: 'Beta',
        description: null,
        project_type: 'research',
        research_status: 'active',
        document_count: 0,
        note_count: 0,
        draft_count: 0,
        updated_at: '2026-04-20T00:00:00Z',
      },
    ]);
    mockedText.mockReset();
    mockedText
      .mockResolvedValueOnce('/projects' as never)
      .mockResolvedValueOnce('__CANCEL__' as never);
    mockedSelect.mockResolvedValueOnce('proj_2' as never);

    await runRepl();

    expect(fetchProjectsMock).toHaveBeenCalled();
    // After picking, future streams must include project context — assert that
    // the success log was printed with the project name.
    const successCalls = mockedLog.success.mock.calls.map(
      (c) => c[0] as string
    );
    expect(successCalls.some((m) => /Project set: Beta/.test(m))).toBe(true);
  });

  test('/projects can clear the project context', async () => {
    fetchProjectsMock.mockResolvedValueOnce([
      {
        id: 'proj_1',
        name: 'Alpha',
        description: null,
        project_type: 'research',
        research_status: 'active',
        document_count: 0,
        note_count: 0,
        draft_count: 0,
        updated_at: '2026-04-25T00:00:00Z',
      },
    ]);
    mockedText.mockReset();
    mockedText
      .mockResolvedValueOnce('/projects' as never)
      .mockResolvedValueOnce('__CANCEL__' as never);
    mockedSelect.mockResolvedValueOnce('__clear__' as never);

    await runRepl();

    const successCalls = mockedLog.success.mock.calls.map(
      (c) => c[0] as string
    );
    expect(successCalls.some((m) => /Project context cleared/.test(m))).toBe(
      true
    );
  });
});

describe('streamToTerminal: withRetry on initial call', () => {
  test('retries once on network error then succeeds', async () => {
    const netErr = Object.assign(new Error('fetch failed'), {
      code: 'ECONNREFUSED',
    });
    mockedStreamAgent.mockImplementationOnce(() => {
      throw netErr;
    });
    mockedStreamAgent.mockReturnValueOnce(
      events([{ type: 'token', content: 'hi' }, { type: 'done' }])
    );
    await runRepl();
    expect(mockedStreamAgent).toHaveBeenCalledTimes(2);
  });

  test('does NOT retry on auth error', async () => {
    mockedStreamAgent.mockImplementationOnce(() => {
      throw new Error('Stream failed: 401');
    });
    await runRepl();
    expect(mockedStreamAgent).toHaveBeenCalledTimes(1);
    expect(mockedLog.error).toHaveBeenCalledWith(
      expect.stringMatching(/expired or unauthorized/i)
    );
  });
});

describe('SIGINT scoping', () => {
  test('SIGINT mid-stream aborts the stream and returns to prompt (does not exit)', async () => {
    const exitSpy = jest
      .spyOn(process, 'exit')
      .mockImplementation((() => undefined) as never);

    let abortRef: AbortSignal | undefined;
    mockedStreamAgent.mockImplementationOnce((_msg, _ctx, opts) => {
      abortRef = opts?.signal;
      return (async function* () {
        // wait until aborted
        await new Promise<void>((resolve) => {
          abortRef?.addEventListener('abort', () => resolve(), { once: true });
        });
        const e = new Error('aborted');
        e.name = 'AbortError';
        throw e;
      })();
    });
    mockedStreamAgent.mockReturnValueOnce(
      events([{ type: 'token', content: 'second' }, { type: 'done' }])
    );

    // After first prompt, send SIGINT during stream
    setTimeout(() => process.emit('SIGINT' as never), 20);

    await runRepl();

    expect(exitSpy).not.toHaveBeenCalled();
    expect(abortRef?.aborted).toBe(true);
    exitSpy.mockRestore();
  });
});

describe('confirmKey', () => {
  test('non-TTY path delegates to p.confirm and existing mocks still work', async () => {
    // Existing tests already mock p.confirm to return true. Just assert
    // the confirmation flow still completes without raw-mode interaction.
    mockedStreamAgent.mockReturnValueOnce(
      events([
        {
          type: 'confirmation',
          threadId: 'thread-x',
          details: { tools: [{ name: 'create_project', args: {} }] },
        },
      ])
    );
    mockedStreamConfirm.mockReturnValueOnce(events([{ type: 'done' }]));
    await runRepl();
    expect(mockedConfirm).toHaveBeenCalled();
  });
});
