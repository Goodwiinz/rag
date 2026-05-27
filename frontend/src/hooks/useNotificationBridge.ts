'use client';

import { useEffect, useRef } from 'react';
import { useNotificationStore } from '@/store/notificationStore';
import { useRealtimeProcessingStore } from '@/store/realtimeProcessingStore';
import { useAgentChatStore } from '@/store/agentChatStore';
import type { NotificationChannel } from '@/components/notifications/types';

function mapRealtimeType(
  type: 'success' | 'error' | 'warning' | 'info'
): 'info' | 'warn' | 'error' {
  if (type === 'error') return 'error';
  if (type === 'warning') return 'warn';
  return 'info';
}

export function useNotificationBridge() {
  const addNotification = useNotificationStore((s) => s.addNotification);

  // --- 1. Bridge realtime processing notifications ---
  const realtimeNotifications = useRealtimeProcessingStore(
    (s) => s.notifications
  );
  const lastRealtimeIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (realtimeNotifications.length === 0) return;

    const latest = realtimeNotifications[0];
    if (!latest || latest.id === lastRealtimeIdRef.current) return;

    lastRealtimeIdRef.current = latest.id;

    const channel: NotificationChannel = latest.documentId
      ? 'document'
      : 'system';

    addNotification({
      channel,
      title: latest.title,
      snippet: latest.message,
      severity: mapRealtimeType(latest.type),
      linkTo: latest.documentId ? '/documents' : undefined,
    });
  }, [realtimeNotifications, addNotification]);

  // --- 2. Bridge agent chat events ---
  const agentMessages = useAgentChatStore((s) => s.messages);
  const isStreaming = useAgentChatStore((s) => s.isStreaming);
  const pendingConfirmation = useAgentChatStore((s) => s.pendingConfirmation);
  const prevStreamingRef = useRef(false);
  const lastConfirmIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (prevStreamingRef.current && !isStreaming && agentMessages.length > 0) {
      const lastMsg = agentMessages[agentMessages.length - 1];
      if (lastMsg?.role === 'assistant') {
        const snippet =
          typeof lastMsg.content === 'string'
            ? lastMsg.content.slice(0, 120)
            : 'Agent run completed';

        addNotification({
          channel: 'agent',
          title: 'Agent run completed',
          snippet,
          severity: 'info',
          linkTo: '/chat',
        });
      }
    }
    prevStreamingRef.current = isStreaming;
  }, [isStreaming, agentMessages, addNotification]);

  // HITL interrupt
  useEffect(() => {
    if (!pendingConfirmation) return;
    const confirmId =
      pendingConfirmation.jobId || JSON.stringify(pendingConfirmation);
    if (confirmId === lastConfirmIdRef.current) return;

    lastConfirmIdRef.current = confirmId;

    addNotification({
      channel: 'agent',
      title: 'Agent paused — review required',
      snippet: `The agent wants to run a destructive tool and needs your approval.`,
      severity: 'warn',
      linkTo: '/chat',
    });
  }, [pendingConfirmation, addNotification]);
}
