'use client';

import { ChatMessageList } from '@/components/chat/ChatMessageList';
// WelcomeState resolves through the barrel (not its own module path) — the
// existing ChatPage.*.test.tsx suite mocks '@/components/chat' at exactly
// this specifier.
import { WelcomeState } from '@/components/chat';
import { Skeleton } from '@/components/ui/skeleton';
import { Activity, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';
import type { ReactElement, ReactNode } from 'react';

import type { CommandAction, CommandOutput } from '@/components/chat/commandOutput';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import type { Citation } from '@/utils/citationParser';

// Shared loading skeleton for cold-load + thread-switch (on-brand bubble rows).
function TranscriptSkeleton(): ReactElement {
  return (
    <div
      className="mx-auto max-w-(--nous-chat-col) space-y-8 p-6"
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label="Loading conversation"
    >
      <p className="nous-caption text-(--nous-fg-3)">Loading conversation</p>
      {[0, 1, 2].map((row) => (
        <div
          key={row}
          className={
            row % 2 === 0
              ? 'flex flex-col items-start gap-2'
              : 'flex flex-col items-end gap-2'
          }
        >
          <Skeleton className="h-3 w-24 rounded-md bg-(--nous-bg-2)" />
          <Skeleton
            className={
              (row % 2 === 0 ? 'h-20 w-[80%]' : 'h-12 w-[55%]') +
              ' rounded-xl bg-(--nous-bg-2)'
            }
          />
        </div>
      ))}
    </div>
  );
}

interface ChatTranscriptStateProps {
  isAuthenticated: boolean;
  isInitializing: boolean;
  initError: string | null;
  isLoadingMessages: boolean;
  activeThreadId: string | null;
  displayedMessages: ChatPageMessage[];
  commandOutputs: CommandOutput[];
  // CX5: gates every streaming-derived value below so a background turn on
  // another thread can't render into this (currently displayed) transcript.
  isStreamingThisThread: boolean;
  isLoading: boolean;
  storeStreamingContent: string;
  storeIsRetrievingRag: boolean;
  onPromptSelect: (prompt: string) => void;
  onRegenerate: (assistantMessageIndex: number) => void;
  onCitationClick: (
    citations: Citation[],
    clickedCitation: Citation,
    traceId?: string
  ) => void;
  onCommandItemAction: (action: CommandAction) => void;
  onLoadOlder: (threadId: string) => void;
  messagePagination: Record<
    string,
    { hasMore: boolean; loadingOlder: boolean; loadedCount: number }
  > | null;
}

/** Wraps a branch's content in the scrollable transcript frame every
 * non-message state (auth/init/error/loading) shares. */
function ScrollFrame({ children }: { children: ReactNode }): ReactElement {
  return (
    <div className="flex-1 relative min-h-0">
      <div className="h-full overflow-y-auto overflow-x-hidden nous-scrollbar">
        {children}
      </div>
    </div>
  );
}

/**
 * Transcript loading/empty/error branching (Task 5.3). Renders exactly one
 * of: unauthenticated redirect notice, init skeleton, init error, thread-load
 * skeleton, empty WelcomeState, or the live ChatMessageList — same ladder
 * `page.tsx` used to inline.
 */
export function ChatTranscriptState({
  isAuthenticated,
  isInitializing,
  initError,
  isLoadingMessages,
  activeThreadId,
  displayedMessages,
  commandOutputs,
  isStreamingThisThread,
  isLoading,
  storeStreamingContent,
  storeIsRetrievingRag,
  onPromptSelect,
  onRegenerate,
  onCitationClick,
  onCommandItemAction,
  onLoadOlder,
  messagePagination,
}: ChatTranscriptStateProps): ReactElement {
  if (!isAuthenticated) {
    return (
      <ScrollFrame>
        <div className="h-full flex flex-col items-center justify-center p-8">
          <div className="text-center" role="status">
            <Loader2 className="w-10 h-10 text-(--nous-sol) animate-spin mx-auto mb-4" />
            <p
              className="text-sm text-(--nous-fg-3) mt-2"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Authentication required. Redirecting...
            </p>
          </div>
        </div>
      </ScrollFrame>
    );
  }

  if (isInitializing) {
    return (
      <ScrollFrame>
        <TranscriptSkeleton />
      </ScrollFrame>
    );
  }

  if (initError) {
    return (
      <ScrollFrame>
        <div className="h-full flex flex-col items-center justify-center p-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center max-w-md"
          >
            <div className="relative w-16 h-16 mx-auto mb-6">
              <div className="absolute inset-0 rounded-full bg-(--nous-mars)/10" />
              <div className="absolute inset-2 rounded-full border border-(--nous-mars)/30 flex items-center justify-center">
                <Activity className="w-6 h-6 text-(--nous-mars)" />
              </div>
            </div>
            <h2
              className="text-lg font-semibold text-(--nous-mars) mb-3"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Connection error
            </h2>
            <p
              className="text-xs text-(--nous-fg-3) mb-6 p-3 rounded-lg bg-(--nous-mars)/5 border border-(--nous-mars)/10"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              {initError}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-(--nous-bg-2) border border-(--nous-border-1) text-(--nous-fg-1) text-xs font-medium hover:border-(--nous-sol)/30 transition-all"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              <Activity className="w-3.5 h-3.5" />
              Retry connection
            </button>
          </motion.div>
        </div>
      </ScrollFrame>
    );
  }

  if (isLoadingMessages) {
    return (
      <ScrollFrame>
        <TranscriptSkeleton />
      </ScrollFrame>
    );
  }

  if (
    displayedMessages.length === 0 &&
    commandOutputs.length === 0 &&
    !isStreamingThisThread
  ) {
    return (
      <ScrollFrame>
        <WelcomeState onPromptSelect={onPromptSelect} />
      </ScrollFrame>
    );
  }

  return (
    <ChatMessageList
      messages={displayedMessages}
      activeThreadId={activeThreadId}
      // isLoading is set (globally) for the whole span of a turn, same
      // lifecycle as storeIsStreaming — gate it the same way so the
      // pre-first-token "typing" bubble can't render on a thread that isn't
      // the one actually loading (CX5).
      isLoading={isStreamingThisThread ? isLoading : false}
      storeIsStreaming={isStreamingThisThread}
      storeStreamingContent={isStreamingThisThread ? storeStreamingContent : ''}
      onRegenerate={onRegenerate}
      onCitationClick={onCitationClick}
      commandOutputs={commandOutputs}
      onCommandItemAction={onCommandItemAction}
      isRetrievingRag={isStreamingThisThread ? storeIsRetrievingRag : false}
      onLoadOlder={activeThreadId ? () => onLoadOlder(activeThreadId) : undefined}
      hasMore={activeThreadId ? (messagePagination?.[activeThreadId]?.hasMore ?? false) : false}
      isLoadingOlder={
        activeThreadId
          ? (messagePagination?.[activeThreadId]?.loadingOlder ?? false)
          : false
      }
    />
  );
}
