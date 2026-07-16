/**
 * Race-guard regression test for projectChatStore mutation actions
 * (RS-C4): two overlapping calls to the same action for the SAME project
 * (double-click, retry) must not let the stale call's settle-time write
 * clobber the per-project flags/errors a newer call already owns.
 *
 * fetchProjectThreads is intentionally NOT covered here — it already has
 * its own never-reset sequence guard (fetchThreadsSeq) and is out of scope
 * for this sweep.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock, Mocked } from 'vitest';
import { act } from '@testing-library/react';
import { useProjectChatStore } from '../projectChatStore';
import { projectChatService } from '@/services/projectChatService';
import type {
  ProjectThread,
  StartChatFromProjectResponse,
} from '@/types/project-chat';

vi.mock('@/services/projectChatService', () => ({
  projectChatService: {
    listProjectThreads: vi.fn(),
    startChatFromProject: vi.fn(),
    linkThreadToProject: vi.fn(),
    unlinkThreadFromProject: vi.fn(),
    saveThreadToNote: vi.fn(),
  },
}));

// Mock the chat store so the cross-store binding mirror
// (setThreadProjectBinding) is observable.
const { mockSetThreadProjectBinding } = vi.hoisted(
  (): { mockSetThreadProjectBinding: Mock } => ({
    mockSetThreadProjectBinding: vi.fn(),
  })
);

vi.mock('@/store/chat-store', () => ({
  useChatStore: {
    getState: (): { setThreadProjectBinding: Mock } => ({
      setThreadProjectBinding: mockSetThreadProjectBinding,
    }),
  },
}));

const mockService = projectChatService as Mocked<typeof projectChatService>;

const createMockProjectThread = (
  overrides: Partial<ProjectThread> = {}
): ProjectThread => ({
  id: 'pt-123',
  project_id: 'proj-1',
  thread_id: 'thread-789',
  thread_title: 'Test Discussion',
  conversation_id: 'conv-101',
  link_type: 'manual',
  linked_at: new Date().toISOString(),
  linked_by_id: 'user-001',
  context_note: null,
  message_count: 0,
  last_message_at: null,
  ...overrides,
});

describe('projectChatStore mutation race guards (RS-C4)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    act(() => {
      useProjectChatStore.getState().reset();
    });
  });

  it('does not let a stale linkThreadToProject error clobber a newer completed call for the same project', async () => {
    const projectId = 'proj-1';
    let rejectFirst!: (reason: unknown) => void;
    let resolveSecond!: (thread: ProjectThread) => void;

    mockService.linkThreadToProject
      .mockReturnValueOnce(
        new Promise<ProjectThread>((_, rej) => {
          rejectFirst = rej;
        })
      )
      .mockReturnValueOnce(
        new Promise<ProjectThread>((res) => {
          resolveSecond = res;
        })
      );

    const { linkThreadToProject } = useProjectChatStore.getState();
    const first = linkThreadToProject(projectId, { thread_id: 'thread-a' });
    const second = linkThreadToProject(projectId, { thread_id: 'thread-b' });

    // The newer call (second) completes first and owns the per-project state.
    resolveSecond(createMockProjectThread({ thread_id: 'thread-b' }));
    await act(async () => {
      await second;
    });

    expect(useProjectChatStore.getState().linkingThread[projectId]).toBe(false);
    expect(useProjectChatStore.getState().errors[projectId]).toBeNull();

    // The stale (first) call now fails, after the newer call already
    // finished successfully.
    rejectFirst(new Error('stale failure'));
    await act(async () => {
      await first;
    });

    // The stale error must not clobber the newer call's completed state.
    expect(useProjectChatStore.getState().errors[projectId]).toBeNull();
    expect(useProjectChatStore.getState().linkingThread[projectId]).toBe(false);
  });

  it('does not let a stale link response point the chat-rail binding at the wrong project (thread-keyed ABA)', async () => {
    let resolveFirst!: (thread: ProjectThread) => void;
    let resolveSecond!: (thread: ProjectThread) => void;

    mockService.linkThreadToProject
      .mockReturnValueOnce(
        new Promise<ProjectThread>((res) => {
          resolveFirst = res;
        })
      )
      .mockReturnValueOnce(
        new Promise<ProjectThread>((res) => {
          resolveSecond = res;
        })
      );

    const { linkThreadToProject } = useProjectChatStore.getState();
    // Same thread, two different projects — the binding is thread-keyed and
    // single-valued, so only the most recent call may write the mirror.
    const first = linkThreadToProject('proj-a', { thread_id: 'thread-x' });
    const second = linkThreadToProject('proj-b', { thread_id: 'thread-x' });

    resolveSecond(
      createMockProjectThread({ project_id: 'proj-b', thread_id: 'thread-x' })
    );
    await act(async () => {
      await second;
    });
    expect(mockSetThreadProjectBinding).toHaveBeenLastCalledWith(
      'thread-x',
      'proj-b'
    );

    // The stale first response must not re-point the binding at proj-a.
    resolveFirst(
      createMockProjectThread({ project_id: 'proj-a', thread_id: 'thread-x' })
    );
    await act(async () => {
      await first;
    });

    expect(mockSetThreadProjectBinding).toHaveBeenLastCalledWith(
      'thread-x',
      'proj-b'
    );
  });

  it('still refreshes the thread list when an older successful startChatFromProject settles after being superseded', async () => {
    const projectId = 'proj-1';
    let resolveFirst!: (response: StartChatFromProjectResponse) => void;
    let resolveSecond!: (response: StartChatFromProjectResponse) => void;

    mockService.startChatFromProject
      .mockReturnValueOnce(
        new Promise<StartChatFromProjectResponse>((res) => {
          resolveFirst = res;
        })
      )
      .mockReturnValueOnce(
        new Promise<StartChatFromProjectResponse>((res) => {
          resolveSecond = res;
        })
      );
    mockService.listProjectThreads.mockResolvedValue({
      threads: [],
      total: 0,
    });

    const { startChatFromProject } = useProjectChatStore.getState();
    const first = startChatFromProject(projectId, { initial_message: 'a' });
    const second = startChatFromProject(projectId, { initial_message: 'b' });

    resolveSecond({
      thread_id: 't-2',
      conversation_id: 'c-2',
      project_thread_id: 'pt-2',
      document_scope: [],
    });
    await act(async () => {
      await second;
    });
    expect(mockService.listProjectThreads).toHaveBeenCalledTimes(1);

    // The older call ALSO succeeded — its thread exists server-side and must
    // still appear in the list, so the refresh runs even though the call's
    // ephemeral-flag token was evicted (fetchProjectThreads has its own
    // supersession guard).
    resolveFirst({
      thread_id: 't-1',
      conversation_id: 'c-1',
      project_thread_id: 'pt-1',
      document_scope: [],
    });
    await act(async () => {
      await first;
    });
    expect(mockService.listProjectThreads).toHaveBeenCalledTimes(2);
  });
});
