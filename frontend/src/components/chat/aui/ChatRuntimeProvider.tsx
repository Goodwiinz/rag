'use client';

import {
  type ReactElement,
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react';
import {
  AssistantRuntimeProvider,
  createMessageQueue,
  useExternalStoreRuntime,
  type AppendMessage,
} from '@assistant-ui/react';

import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';

import { convertMessage } from './convertMessage';
import { NousToolUIs } from './toolUIs';

function useLatestSend(
  callback: ChatRuntimeProviderProps['onSend']
): ChatRuntimeProviderProps['onSend'] {
  const callbackRef = useRef(callback);
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);
  return useCallback(
    (text: string, attachmentIds?: string[]) =>
      callbackRef.current(text, attachmentIds),
    []
  );
}

export interface ChatRuntimeProviderProps {
  messages: ChatPageMessage[];
  isRunning: boolean;
  /** When true, the composer refuses to send (e.g. a HITL confirmation
   * is pending). Passed through to the runtime's compose disabled state. */
  isSendDisabled?: boolean;
  /** Delegates to the existing useChatStreaming send. */
  onSend: (text: string, attachmentIds?: string[]) => void | Promise<void>;
  onCancel: () => void;
  /** Resolves an in-band HITL approval (P4). Wired to the ExternalStore
   * adapter's onRespondToToolApproval so the approval tool UI's
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
  const send = useLatestSend(onSend);

  // Keep one queue for this runtime identity. The driver deliberately has no
  // cancel callback: assistant-ui Steer therefore reorders a pending item and
  // lets the current single-flight stream settle before processing it.
  const [queue] = useState(() => {
    const controller = createMessageQueue({
      run: (message) => {
        const text = message.content
          .filter(
            (part): part is { type: 'text'; text: string } =>
              part.type === 'text'
          )
          .map((part) => part.text)
          .join('\n');
        if (!text.trim()) return;

        const custom = message.runConfig?.custom;
        const attachmentIds = custom?.attachmentIds;
        void send(
          text,
          Array.isArray(attachmentIds) &&
            attachmentIds.every((id): id is string => typeof id === 'string')
            ? attachmentIds
            : undefined
        );
      },
    });
    return controller;
  });

  // createMessageQueue mutates its adapter in place. Subscribe so the
  // external-store runtime receives a fresh render and projects queue items.
  useSyncExternalStore(
    queue.subscribe,
    () => queue.adapter.items,
    () => queue.adapter.items
  );

  const previousRunningRef = useRef<boolean | undefined>(undefined);
  useEffect(() => {
    const previous = previousRunningRef.current;
    previousRunningRef.current = isRunning;
    if (previous === undefined) {
      if (isRunning) queue.notifyBusy();
      return;
    }
    if (isRunning && !previous) queue.notifyBusy();
    if (!isRunning && previous) queue.notifyIdle();
  }, [isRunning, queue]);

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
      const custom = message.runConfig?.custom;
      const attachmentIds = custom?.attachmentIds;
      await onSend(
        text,
        Array.isArray(attachmentIds) &&
          attachmentIds.every((id): id is string => typeof id === 'string')
          ? attachmentIds
          : undefined
      );
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
    queue: queue.adapter,
    onNew,
    onCancel: handleCancel,
    onRespondToToolApproval,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {/* Declarative per-tool renderers (register on mount, render null).
          Unregistered tools keep the generic ToolFallback. */}
      <NousToolUIs />
      {children}
    </AssistantRuntimeProvider>
  );
}
