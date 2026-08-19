'use client';

import { useEffect, useRef } from 'react';
import { useNotificationStore } from '@/store/notificationStore';
import { useAgentChatStore } from '@/store/agentChatStore';

export function useNotificationBridge(): void {
  const addNotification = useNotificationStore((s) => s.addNotification);

  // --- Bridge agent chat events ---
  const agentMessages = useAgentChatStore((s) => s.messages);
  const isStreaming = useAgentChatStore((s) => s.isStreaming);
  const pendingConfirmations = useAgentChatStore((s) => s.pendingConfirmations);
  const prevStreamingRef = useRef(false);
  const notifiedConfirmIdsRef = useRef<Set<string>>(new Set());

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
    for (const pending of Object.values(pendingConfirmations)) {
      if (notifiedConfirmIdsRef.current.has(pending.jobId)) continue;
      notifiedConfirmIdsRef.current.add(pending.jobId);
      addNotification({
        channel: 'agent',
        title: 'Agent paused — review required',
        snippet: `The agent wants to run a destructive tool and needs your approval.`,
        severity: 'warn',
        linkTo: '/chat',
      });
    }
  }, [pendingConfirmations, addNotification]);
}
