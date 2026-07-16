'use client';

import { ChatInput, CitationPanel, WelcomeState } from '@/components/chat';
import { ChatDialogs } from '@/components/chat/ChatDialogs';
import { ChatHeader } from '@/components/chat/ChatHeader';
import { ChatMessageList } from '@/components/chat/ChatMessageList';
import { ChatRuntimeProvider } from '@/components/chat/aui/ChatRuntimeProvider';
import { ChatSidebar } from '@/components/chat/ChatSidebar';
import { Skeleton } from '@/components/ui/skeleton';
import { getSelectedThreadUrl } from '@/components/chat/shared/chatNavigation';
import { AnimatePresence, motion } from 'framer-motion';
import { Activity, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useChatSession } from '@/hooks/chat/useChatSession';
import {
  useChatStreaming,
  confirmationBelongsToThread,
  type PendingConfirmation,
} from '@/hooks/chat/useChatStreaming';
import { useChatThreadActions } from '@/hooks/chat/useChatThreadActions';
import { useSlashCommands } from '@/hooks/chat/useSlashCommands';
import { useCitationPanel } from '@/hooks/chat/useCitationPanel';
import { useChatDrawer } from '@/hooks/chat/useChatDrawer';
import { useChatComposerActions } from '@/hooks/chat/useChatComposerActions';

// Shared loading skeleton for cold-load + thread-switch (on-brand bubble rows).
function TranscriptSkeleton() {
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

// ============================================
// MAIN PAGE COMPONENT
// ============================================

function ChatPageContent() {
  // Session / workspace / thread initialization (extracted hook)
  const {
    conversations,
    setConversations,
    messages,
    setMessages,
    workspace,
    dbConversation,
    isInitializing,
    initError,
    isLoadingMessages,
    isHydratedRef,
    setCurrentThread,
    storeMessages,
    isAuthenticated,
    activeThreadId,
    displayedMessages,
    loadOlderMessages,
    messagePagination,
    hasMoreThreads,
    loadMoreThreads,
    mapDbMessageToUiMessage,
    loadThreadsFromDb,
  } = useChatSession();

  // RAG state
  const [enableRAG, setEnableRAG] = useState(true);

  // Streaming / submit / HITL logic (extracted hook)
  const {
    input,
    setInput,
    isLoading,
    handleSubmit,
    handleStop,
    pendingConfirmation,
    handleConfirmation,
    chatInputRef,
    storeIsStreaming,
    storeStreamingContent,
    storeIsRetrievingRag,
    streamingThreadId,
  } = useChatStreaming({
    messages,
    displayedMessages,
    setMessages,
    conversations,
    setConversations,
    dbConversation,
    enableRAG,
  });

  // CX5: storeIsStreaming is intentionally global (single-flight — the
  // composer below stays blocked on the raw flag regardless of which thread
  // is displayed). This derived flag is ONLY for streaming-derived UI that
  // must not bleed into a thread that isn't actually streaming — a
  // background turn on thread A rendering into thread B's transcript.
  const isStreamingThisThread =
    storeIsStreaming && streamingThreadId === activeThreadId;

  // Only the thread that owns the pending confirmation shows the banner or
  // has its input locked — pendingConfirmation itself survives navigation so
  // returning to the owning thread re-shows it.
  const activeConfirmation = confirmationBelongsToThread(
    pendingConfirmation,
    activeThreadId
  )
    ? pendingConfirmation
    : null;

  // Rename/delete/bulk-delete thread action handlers and dialog state
  const {
    renameDialog,
    setRenameDialog,
    deleteDialog,
    setDeleteDialog,
    bulkDeleteDialog,
    setBulkDeleteDialog,
    handleRenameThread,
    commitRename,
    handleDeleteThread,
    commitDeleteThread,
    handleBulkDeleteThreads,
    commitBulkDelete,
  } = useChatThreadActions({
    conversations,
    setConversations,
    activeThreadId,
    setCurrentThread,
  });

  // Mobile sidebar drawer state + WCAG focus/Escape/Tab-trap behavior
  // (extracted hook)
  const {
    isOpen: mobileSidebarOpen,
    closeDrawer,
    toggleDrawer,
    drawerRef,
    handleDrawerKeyDown,
  } = useChatDrawer();

  // Citation panel state + coordination (extracted hook)
  const {
    isCitationPanelOpen,
    setIsCitationPanelOpen,
    citationPanelCitations,
    activeCitationId,
    citationTraceId,
    handleCitationClick,
    handleCiteSource,
  } = useCitationPanel({ setInput, chatInputRef });

  const router = useRouter();

  // Listen for populate-chat-input events from Follow-up Suggestions
  useEffect(() => {
    const handlePopulateChatInput = (event: CustomEvent<string>) => {
      if (event.detail) {
        setInput(event.detail);
        // Focus the textarea after populating
        chatInputRef.current?.focus();
      }
    };

    window.addEventListener(
      'populate-chat-input',
      handlePopulateChatInput as EventListener
    );
    return () => {
      window.removeEventListener(
        'populate-chat-input',
        handlePopulateChatInput as EventListener
      );
    };
  }, [setInput, chatInputRef]);

  const handlePromptSelect = (prompt: string) => {
    setInput(prompt);
  };

  // Composer actions — attach, retry, regenerate, submit (extracted hook).
  // Delegates persistence/streaming to useChatStreaming's handleSubmit.
  const { handleAttach, handleRegenerate, retryLast, submit } =
    useChatComposerActions({
      workspace,
      setInput,
      handleSubmit,
      isLoading,
      storeIsStreaming,
      displayedMessages,
    });

  // Stable across renders so ChatSidebar's React.memo holds on every composer
  // keystroke (an inline closure re-rendered the sidebar per keystroke).
  // Shared by both sidebars — closing the mobile drawer is an idempotent no-op
  // on desktop, where it's already closed and hidden.
  const handleSelectThread = useCallback(
    (id: string) => {
      if (id === activeThreadId) {
        closeDrawer();
        return;
      }
      setCurrentThread(id);
      router.push(getSelectedThreadUrl(id));
      closeDrawer();
    },
    [router, setCurrentThread, activeThreadId, closeDrawer]
  );

  // Slash-command execution, project-context wiring, and the /new command
  // the command vocabulary triggers (extracted hook). /retry and the plain
  // send path delegate to useChatComposerActions.
  const {
    commandOutputs,
    handleSlashCommand,
    handleCommandItemAction,
    submitMessage,
    startNewChat,
  } = useSlashCommands({
    input,
    setInput,
    handleSubmit,
    submit,
    retryLast,
    conversations,
    activeThreadId,
    setCurrentThread,
    chatInputRef,
  });

  // Return focus to the composer when a HITL confirmation resolves — the
  // in-band Approve/Deny part just unmounted, so without this focus would drop
  // to <body>. (The approval part handles its own Approve autofocus on appear.)
  const prevActiveConfirmationRef = useRef<PendingConfirmation | null>(null);
  useEffect(() => {
    const had = prevActiveConfirmationRef.current;
    if (!activeConfirmation && had) {
      chatInputRef.current?.focus();
    }
    prevActiveConfirmationRef.current = activeConfirmation;
  }, [activeConfirmation, chatInputRef]);

  const runtimeHydrationPhase =
    displayedMessages.length > 0 ? 'hydrated' : 'empty';

  return (
    <div className="flex h-full w-full overflow-hidden bg-(--nous-bg-1)">
      {/* Mobile sidebar backdrop + drawer */}
      <AnimatePresence>
        {mobileSidebarOpen && (
          <div className="fixed inset-0 z-50 md:hidden">
            <motion.div
              className="absolute inset-0 bg-(--nous-erebus)/50"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={closeDrawer}
            />
            <motion.div
              ref={drawerRef}
              tabIndex={-1}
              role="dialog"
              aria-modal="true"
              aria-label="Chat history"
              onKeyDown={handleDrawerKeyDown}
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              className="absolute left-0 top-0 bottom-0 w-[min(280px,85vw)] bg-(--nous-bg-2) border-r border-(--nous-border-1) shadow-(--nous-shadow-lg) outline-hidden"
            >
              <ChatSidebar
                conversations={conversations}
                activeId={activeThreadId}
                onSelect={handleSelectThread}
                onNew={() => {
                  startNewChat();
                  closeDrawer();
                }}
                onRename={handleRenameThread}
                onDelete={handleDeleteThread}
                onBulkDelete={handleBulkDeleteThreads}
                currentWorkspace={workspace}
                hasMoreThreads={hasMoreThreads}
                onLoadMoreThreads={loadMoreThreads}
              />
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Desktop sidebar */}
      <div className="hidden md:block h-full shrink-0">
        <ChatSidebar
          conversations={conversations}
          activeId={activeThreadId}
          onSelect={handleSelectThread}
          onNew={startNewChat}
          onRename={handleRenameThread}
          onDelete={handleDeleteThread}
          onBulkDelete={handleBulkDeleteThreads}
          currentWorkspace={workspace}
          hasMoreThreads={hasMoreThreads}
          onLoadMoreThreads={loadMoreThreads}
        />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col relative h-full min-w-0 overflow-hidden">
        <ChatRuntimeProvider
          key={`${activeThreadId ?? 'new'}:${runtimeHydrationPhase}`}
          messages={displayedMessages}
          isRunning={isLoading || storeIsStreaming || !!activeConfirmation}
          isSendDisabled={!!activeConfirmation}
          onSend={handleSubmit}
          onCancel={handleStop}
          onApproval={handleConfirmation}
        >
          <ChatHeader
            messages={displayedMessages}
            chatTitle={
              conversations.find((c) => c.id === activeThreadId)?.title ||
              'Chat'
            }
            onCopyAll={() => {
              const text = displayedMessages
                .map((m) => `[${m.role}] ${m.content}`)
                .join('\n\n');
              navigator.clipboard.writeText(text).catch(() => {});
            }}
            onMobileSidebarToggle={toggleDrawer}
          />

          {/* Messages Area */}
          {!isAuthenticated ? (
            <div className="flex-1 relative min-h-0">
              <div className="h-full overflow-y-auto overflow-x-hidden nous-scrollbar">
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
              </div>
            </div>
          ) : isInitializing ? (
            <div className="flex-1 relative min-h-0">
              <div className="h-full overflow-y-auto overflow-x-hidden nous-scrollbar">
                <TranscriptSkeleton />
              </div>
            </div>
          ) : initError ? (
            <div className="flex-1 relative min-h-0">
              <div className="h-full overflow-y-auto overflow-x-hidden nous-scrollbar">
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
              </div>
            </div>
          ) : isLoadingMessages ? (
            <div className="flex-1 relative min-h-0">
              <div className="h-full overflow-y-auto overflow-x-hidden nous-scrollbar">
                <TranscriptSkeleton />
              </div>
            </div>
          ) : displayedMessages.length === 0 &&
            commandOutputs.length === 0 &&
            !isStreamingThisThread ? (
            <div className="flex-1 relative min-h-0">
              <div className="h-full overflow-y-auto overflow-x-hidden nous-scrollbar">
                <WelcomeState onPromptSelect={handlePromptSelect} />
              </div>
            </div>
          ) : (
            <ChatMessageList
              messages={displayedMessages}
              activeThreadId={activeThreadId}
              // isLoading is set (globally) for the whole span of a turn,
              // same lifecycle as storeIsStreaming — gate it the same way so
              // the pre-first-token "typing" bubble can't render on a thread
              // that isn't the one actually loading (CX5).
              isLoading={isStreamingThisThread ? isLoading : false}
              storeIsStreaming={isStreamingThisThread}
              storeStreamingContent={
                isStreamingThisThread ? storeStreamingContent : ''
              }
              onRegenerate={handleRegenerate}
              onCitationClick={handleCitationClick}
              commandOutputs={commandOutputs}
              onCommandItemAction={handleCommandItemAction}
              isRetrievingRag={
                isStreamingThisThread ? storeIsRetrievingRag : false
              }
              onLoadOlder={
                activeThreadId
                  ? () => loadOlderMessages(activeThreadId)
                  : undefined
              }
              hasMore={
                activeThreadId
                  ? (messagePagination?.[activeThreadId]?.hasMore ?? false)
                  : false
              }
              isLoadingOlder={
                activeThreadId
                  ? (messagePagination?.[activeThreadId]?.loadingOlder ?? false)
                  : false
              }
            />
          )}

          {/* Input Area */}
          <ChatInput
            value={input}
            onChange={setInput}
            onSubmit={submitMessage}
            onStop={handleStop}
            isLoading={isLoading || storeIsStreaming || !!activeConfirmation}
            enableRAG={enableRAG}
            onRAGToggle={setEnableRAG}
            inputRef={chatInputRef}
            onAttach={handleAttach}
            onCommand={handleSlashCommand}
          />
        </ChatRuntimeProvider>

        {/* Citation Panel Sidebar */}
        <CitationPanel
          citations={citationPanelCitations}
          isOpen={isCitationPanelOpen}
          onClose={() => setIsCitationPanelOpen(false)}
          onCitationClick={(citation) => {
            if (citation.documentId) {
              router.push(`/documents/${citation.documentId}`);
            }
          }}
          onCite={handleCiteSource}
          diagnosticsTraceId={citationTraceId}
          activeCitationId={activeCitationId}
        />
      </div>

      <ChatDialogs
        renameDialog={renameDialog}
        setRenameDialog={setRenameDialog}
        commitRename={commitRename}
        deleteDialog={deleteDialog}
        setDeleteDialog={setDeleteDialog}
        commitDeleteThread={commitDeleteThread}
        bulkDeleteDialog={bulkDeleteDialog}
        setBulkDeleteDialog={setBulkDeleteDialog}
        commitBulkDelete={commitBulkDelete}
      />
    </div>
  );
}

// Wrapper component with Suspense boundary for useSearchParams
export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex-1 flex flex-col items-center justify-center p-8">
          <div className="text-center" role="status">
            <Loader2 className="w-10 h-10 text-(--nous-sol) animate-spin mx-auto mb-4" />
            <p
              className="text-sm text-(--nous-fg-3)"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Loading chat...
            </p>
          </div>
        </div>
      }
    >
      <ChatPageContent />
    </Suspense>
  );
}
