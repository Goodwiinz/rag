import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { useNotificationBridge } from '@/hooks/useNotificationBridge';
import { useAgentChatStore } from '@/store/agentChatStore';
import { useNotificationStore } from '@/store/notificationStore';
import { useRealtimeProcessingStore } from '@/store/realtimeProcessingStore';

describe('useNotificationBridge', () => {
  beforeEach(() => {
    act(() => {
      useNotificationStore.getState().clearAll();
      useRealtimeProcessingStore.setState({ notifications: [] });
      useAgentChatStore.getState().reset();
    });
  });

  it('bridges the latest realtime document notification once with severity and link mapping', async () => {
    renderHook(() => useNotificationBridge());

    act(() => {
      useRealtimeProcessingStore.setState({
        notifications: [
          {
            id: 'rt-1',
            type: 'warning',
            title: 'Extraction needs review',
            message: 'The document parser detected a low-confidence table.',
            timestamp: '2026-05-27T10:04:00.000Z',
            documentId: 'doc-1',
          },
        ],
      });
    });

    await waitFor(() => {
      expect(useNotificationStore.getState().notifications).toHaveLength(1);
    });

    expect(useNotificationStore.getState().notifications[0]).toMatchObject({
      channel: 'document',
      title: 'Extraction needs review',
      snippet: 'The document parser detected a low-confidence table.',
      severity: 'warn',
      linkTo: '/documents',
      read: false,
    });

    act(() => {
      useRealtimeProcessingStore.setState({
        notifications: [
          {
            id: 'rt-1',
            type: 'warning',
            title: 'Extraction needs review',
            message: 'The document parser detected a low-confidence table.',
            timestamp: '2026-05-27T10:04:00.000Z',
            documentId: 'doc-1',
          },
        ],
      });
    });

    expect(useNotificationStore.getState().notifications).toHaveLength(1);
  });

  it('maps realtime errors without document ids to system notifications', async () => {
    renderHook(() => useNotificationBridge());

    act(() => {
      useRealtimeProcessingStore.setState({
        notifications: [
          {
            id: 'rt-system-error',
            type: 'error',
            title: 'Realtime connection failed',
            message: 'The processing channel disconnected.',
            timestamp: '2026-05-27T10:04:00.000Z',
          },
        ],
      });
    });

    await waitFor(() => {
      expect(useNotificationStore.getState().notifications[0]).toMatchObject({
        channel: 'system',
        severity: 'error',
        linkTo: undefined,
      });
    });
  });

  it('emits an agent completion notification only when streaming transitions from true to false', async () => {
    renderHook(() => useNotificationBridge());

    act(() => {
      useAgentChatStore.setState({
        isStreaming: true,
        messages: [
          {
            id: 'msg-user',
            role: 'user',
            content: 'Summarize the upload.',
            timestamp: new Date('2026-05-27T10:03:00.000Z'),
          },
        ],
      });
    });

    expect(useNotificationStore.getState().notifications).toEqual([]);

    act(() => {
      useAgentChatStore.setState({
        isStreaming: false,
        messages: [
          {
            id: 'msg-user',
            role: 'user',
            content: 'Summarize the upload.',
            timestamp: new Date('2026-05-27T10:03:00.000Z'),
          },
          {
            id: 'msg-assistant',
            role: 'assistant',
            content: 'Upload summary is ready.',
            timestamp: new Date('2026-05-27T10:04:00.000Z'),
          },
        ],
      });
    });

    await waitFor(() => {
      expect(useNotificationStore.getState().notifications).toHaveLength(1);
    });

    expect(useNotificationStore.getState().notifications[0]).toMatchObject({
      channel: 'agent',
      title: 'Agent run completed',
      snippet: 'Upload summary is ready.',
      severity: 'info',
      linkTo: '/chat',
    });
  });

  it('emits each human-in-the-loop confirmation notification once per confirmation id', async () => {
    renderHook(() => useNotificationBridge());

    const pendingConfirmation = {
      jobId: 'job-1',
      tools: [{ name: 'ingest_arxiv_papers', args: { query: 'RAG' } }],
      message: 'Approve ingestion?',
    };

    act(() => {
      useAgentChatStore.setState({ pendingConfirmation });
    });

    await waitFor(() => {
      expect(useNotificationStore.getState().notifications).toHaveLength(1);
    });

    expect(useNotificationStore.getState().notifications[0]).toMatchObject({
      channel: 'agent',
      title: 'Agent paused — review required',
      severity: 'warn',
      linkTo: '/chat',
    });

    act(() => {
      useAgentChatStore.setState({ pendingConfirmation });
    });

    expect(useNotificationStore.getState().notifications).toHaveLength(1);
  });
});
