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
import type { Mocked } from 'vitest';
import { act } from '@testing-library/react';
import { useProjectChatStore } from '../projectChatStore';
import { projectChatService } from '@/services/projectChatService';
import type { ProjectThread } from '@/types/project-chat';

vi.mock('@/services/projectChatService', () => ({
  projectChatService: {
    listProjectThreads: vi.fn(),
    startChatFromProject: vi.fn(),
    linkThreadToProject: vi.fn(),
    unlinkThreadFromProject: vi.fn(),
    saveThreadToNote: vi.fn(),
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
});
