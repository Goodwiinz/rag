'use client';

import { useEffect, useRef, type ReactElement } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

// ChatInput/CitationPanel resolve through the barrel (not their own module
// paths) — the existing ChatPage.*.test.tsx suite mocks '@/components/chat'
// at exactly this specifier.
import { ChatInput, CitationPanel } from '@/components/chat';
import { ChatDialogs } from '@/components/chat/ChatDialogs';
import { ChatHeader } from '@/components/chat/ChatHeader';
import { ChatSidebar } from '@/components/chat/ChatSidebar';
import { ChatTranscriptState } from '@/components/chat/ChatTranscriptState';
import { ChatRuntimeProvider } from '@/components/chat/aui/ChatRuntimeProvider';
import type { UseChatSessionReturn } from '@/hooks/chat/useChatSession';
import {
  confirmationBelongsToThread,
  type PendingConfirmation,
  type UseChatStreamingReturn,
} from '@/hooks/chat/useChatStreaming';
import type { UseChatThreadActionsReturn } from '@/hooks/chat/useChatThreadActions';
import type { UseChatDrawerReturn } from '@/hooks/chat/useChatDrawer';
import type { UseCitationPanelReturn } from '@/hooks/chat/useCitationPanel';
import type { UseChatComposerActionsReturn } from '@/hooks/chat/useChatComposerActions';
import type { UseSlashCommandsReturn } from '@/hooks/chat/useSlashCommands';
import type { Citation } from '@/utils/citationParser';

interface ChatSurfaceProps {
  session: UseChatSessionReturn;
  streaming: UseChatStreamingReturn;
  threadActions: UseChatThreadActionsReturn;
  drawer: UseChatDrawerReturn;
  citationPanel: UseCitationPanelReturn;
  composerActions: UseChatComposerActionsReturn;
  slashCommands: UseSlashCommandsReturn;
  enableRAG: boolean;
  setEnableRAG: (enabled: boolean) => void;
  /** Route-level: uses next/navigation's router, so it's built in page.tsx. */
  onSelectThread: (id: string) => void;
  /** Route-level: navigates to the source document. */
  onCitationDocumentClick: (citation: Citation) => void;
}

/**
 * The chat route's visible shell (Task 5.3): sidebar (mobile drawer +
 * desktop), the aui-runtime-wrapped header/transcript/composer column, the
 * citation panel, and thread dialogs. Pure composition over explicit
 * props — the hooks themselves (session/streaming/etc.) still own all
 * state and service calls; this component only renders and wires callbacks.
 */
export function ChatSurface({
  session,
  streaming,
  threadActions,
  drawer,
  citationPanel,
  composerActions,
  slashCommands,
  enableRAG,
  setEnableRAG,
  onSelectThread,
  onCitationDocumentClick,
}: ChatSurfaceProps): ReactElement {
  const {
    conversations,
    workspace,
    activeThreadId,
    displayedMessages,
    isAuthenticated,
    isInitializing,
    initError,
    isLoadingMessages,
    hasMoreThreads,
    loadMoreThreads,
    loadOlderMessages,
    messagePagination,
  } = session;

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
  } = streaming;

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
  } = threadActions;

  const {
    isOpen: mobileSidebarOpen,
    closeDrawer,
    toggleDrawer,
    drawerRef,
    handleDrawerKeyDown,
  } = drawer;

  const {
    isCitationPanelOpen,
    setIsCitationPanelOpen,
    citationPanelCitations,
    activeCitationId,
    citationTraceId,
    handleCitationClick,
    handleCiteSource,
  } = citationPanel;

  const { handleAttach, handleRegenerate } = composerActions;

  const {
    commandOutputs,
    handleSlashCommand,
    handleCommandItemAction,
    submitMessage,
    startNewChat,
  } = slashCommands;

  // CX5: storeIsStreaming is intentionally global (single-flight — the
  // composer stays blocked on the raw flag regardless of which thread is
  // displayed). This derived flag is ONLY for streaming-derived UI that must
  // not bleed into a thread that isn't actually streaming — a background
  // turn on thread A rendering into thread B's transcript.
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

  const isBusy = isLoading || storeIsStreaming || !!activeConfirmation;

  const runtimeHydrationPhase =
    displayedMessages.length > 0 ? 'hydrated' : 'empty';

  // Listen for populate-chat-input events from Follow-up Suggestions
  useEffect(() => {
    const handlePopulateChatInput = (event: CustomEvent<string>): void => {
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
                onSelect={onSelectThread}
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
          onSelect={onSelectThread}
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
          isRunning={isBusy}
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

          <ChatTranscriptState
            isAuthenticated={isAuthenticated}
            isInitializing={isInitializing}
            initError={initError}
            isLoadingMessages={isLoadingMessages}
            activeThreadId={activeThreadId}
            displayedMessages={displayedMessages}
            commandOutputs={commandOutputs}
            isStreamingThisThread={isStreamingThisThread}
            isLoading={isLoading}
            storeStreamingContent={storeStreamingContent}
            storeIsRetrievingRag={storeIsRetrievingRag}
            onPromptSelect={setInput}
            onRegenerate={handleRegenerate}
            onCitationClick={handleCitationClick}
            onCommandItemAction={handleCommandItemAction}
            onLoadOlder={loadOlderMessages}
            messagePagination={messagePagination}
          />

          <ChatInput
            value={input}
            onChange={setInput}
            onSubmit={submitMessage}
            onStop={handleStop}
            isLoading={isBusy}
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
          onCitationClick={onCitationDocumentClick}
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
