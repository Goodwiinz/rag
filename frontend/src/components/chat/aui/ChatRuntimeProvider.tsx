'use client';

import { type ReactElement, type ReactNode, useCallback } from 'react';
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
} from '@assistant-ui/react';

import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { AUI_FULL } from '@/components/chat/shared/auiFlags';

import { convertMessage } from './convertMessage';
import { NousToolUIs } from './toolUIs';

export interface ChatRuntimeProviderProps {
  messages: ChatPageMessage[];
  isRunning: boolean;
  /** When true, the composer refuses to send (e.g. a HITL confirmation
   * is pending). Passed through to the runtime's compose disabled state. */
  isSendDisabled?: boolean;
  /** Delegates to the existing useChatStreaming send. Required by the
   * external-store API even though the composer stays custom in stage 1. */
  onSend: (text: string) => void;
  onCancel: () => void;
  /** Resolves an in-band HITL approval (AUI_FULL / P4). Wired to the
   * ExternalStore adapter's onRespondToToolApproval so the approval tool UI's
   * respondToApproval routes to the existing hardened confirm handler. */
  onApproval?: (approved: boolean) => void;
  children: ReactNode;
}

/**
 * Projects the existing /chat page state into an assistant-ui
 * ExternalStoreRuntime. The runtime never owns state — it is a pure
 * projection of the props; sends and cancels delegate back to the
 * existing streaming hooks.
 */
export function ChatRuntimeProvider({
  messages,
  isRunning,
  isSendDisabled,
  onSend,
  onCancel,
  onApproval,
  children,
}: ChatRuntimeProviderProps): ReactElement {
  const onNew = useCallback(
    async (message: AppendMessage) => {
      const text = message.content
        .filter((p): p is { type: 'text'; text: string } => p.type === 'text')
        .map((p) => p.text)
        .join('\n');
      // Guard against empty sends (whitespace-only / no text parts) — the
      // composer should never emit these, but the runtime is a pure
      // projection and should not call onSend with an empty string.
      if (!text) return;
      onSend(text);
    },
    [onSend]
  );

  const handleCancel = useCallback(async () => {
    onCancel();
  }, [onCancel]);

  // Route the runtime's approval resolution to the existing confirm handler.
  // The renderer's respondToApproval → runtime → this adapter callback; opts
  // carries the resolved boolean, so no option-list resolution is needed here.
  const onRespondToToolApproval = useCallback(
    (opts: { approved: boolean }) => {
      onApproval?.(opts.approved);
    },
    [onApproval]
  );

  const runtime = useExternalStoreRuntime({
    messages,
    isRunning,
    isSendDisabled,
    convertMessage,
    onNew,
    onCancel: handleCancel,
    onRespondToToolApproval,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {/* Declarative per-tool renderers (register on mount, render null).
          Flag-gated: unregistered tools keep the generic ToolFallback. */}
      {AUI_FULL && <NousToolUIs />}
      {children}
    </AssistantRuntimeProvider>
  );
}
