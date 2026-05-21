'use client';

import { ChatInput, CitationPanel, WelcomeState } from '@/components/chat';
import { ChatDialogs } from '@/components/chat/ChatDialogs';
import { ChatHeader } from '@/components/chat/ChatHeader';
import { ChatMessageList } from '@/components/chat/ChatMessageList';
import { ChatSidebar } from '@/components/chat/ChatSidebar';
import {
  getNewChatUrl,
  getSelectedThreadUrl,
} from '@/components/chat/shared/chatNavigation';
import { enhancedDocumentService } from '@/services/enhancedDocumentService';
import { Citation } from '@/utils/citationParser';
import { motion } from 'framer-motion';
import { Activity, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { useChatSession } from '@/hooks/chat/useChatSession';
import { useChatStreaming } from '@/hooks/chat/useChatStreaming';
import { useChatThreadActions } from '@/hooks/chat/useChatThreadActions';

// ============================================
// CONSTANTS
// ============================================

// ============================================
// MAIN PAGE COMPONENT
// ============================================

function ChatPageContent() {
  // Session / workspace / thread initialization (extracted hook)
  const {
    conversations,
    setConversations,
    activeConversationId,
    setActiveConversationId,
    messages,
    setMessages,
    workspace,
    dbConversation,
    isInitializing,
    initError,
    isLoadingMessages,
    activeConversationIdRef,
    isHydratedRef,
    currentThreadIdFromStore,
    setCurrentThread,
    storeMessages,
    addMessageToStore,
    isAuthenticated,
    activeThreadId,
    displayedMessages,
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
    isConfirming,
    handleConfirmation,
    chatInputRef,
    storeIsStreaming,
    storeStreamingContent,
    streamingTimestampRef,
    selectedModel,
    setSelectedModel,
  } = useChatStreaming({
    messages,
    setMessages,
    conversations,
    setConversations,
    activeConversationId,
    setActiveConversationId,
    activeConversationIdRef,
    dbConversation,
    isAuthenticated,
    setCurrentThread,
    addMessageToStore,
    enableRAG,
  });

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
    activeConversationId,
    setActiveConversationId,
    activeConversationIdRef,
    setMessages,
    setCurrentThread,
  });

  // Citation panel state
  const [isCitationPanelOpen, setIsCitationPanelOpen] = useState(false);
  const [citationPanelCitations, setCitationPanelCitations] = useState<
    Citation[]
  >([]);
  const [activeCitationId, setActiveCitationId] = useState<string | undefined>(
    undefined
  );

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

  const handleCitationClick = useCallback(
    (citations: Citation[], clickedCitation: Citation) => {
      setCitationPanelCitations(citations);
      setActiveCitationId(clickedCitation.documentId);
      setIsCitationPanelOpen(true);
    },
    []
  );

  const handlePromptSelect = (prompt: string) => {
    setInput(prompt);
  };

  // Upload files selected via the Paperclip attach control.
  // Uses enhancedDocumentService (v1 /files/upload) since no workspace-scoped
  // attach endpoint exists yet. Each upload is isolated via .catch so one
  // failure does not cancel others.
  const handleAttach = useCallback(
    async (files: FileList) => {
      if (!workspace) {
        console.warn('[Chat] Cannot attach: no workspace');
        return;
      }
      const uploads = Array.from(files).map((file) =>
        enhancedDocumentService
          .uploadDocument(file, {
            title: file.name,
            processing_priority: 'normal',
          })
          .then((result) => {
            console.log(
              '[Chat] Uploaded',
              file.name,
              '→',
              result.response.document_id
            );
            return result;
          })
          .catch((err) => {
            console.error('[Chat] Upload failed for', file.name, err);
            return null;
          })
      );
      await Promise.all(uploads);
    },
    [workspace]
  );

  const handleRegenerate = useCallback(
    (assistantMessageIndex: number) => {
      // Bug 1: bail BEFORE truncating messages if a stream is in flight.
      // Otherwise `setMessages` clears the list but `handleSubmit`'s internal
      // guard short-circuits, leaving the UI with no response.
      if (isLoading || storeIsStreaming) return;
      const priorUser = [...displayedMessages]
        .slice(0, assistantMessageIndex)
        .reverse()
        .find((m) => m.role === 'user');
      if (!priorUser) return;
      setMessages((prev) => prev.slice(0, assistantMessageIndex));
      setInput(priorUser.content);
      // Bug 2: pass the content explicitly. `handleSubmit` reads `input` from
      // its closure, and `setInput` above only schedules a state update — the
      // deferred `handleSubmit` would otherwise see the stale pre-setInput value.
      const contentToSend = priorUser.content;
      setTimeout(() => handleSubmit(contentToSend), 0);
    },
    [displayedMessages, handleSubmit, isLoading, storeIsStreaming, setMessages]
  );

  return (
    <div className="flex h-full w-full overflow-hidden bg-[var(--terminal-bg)]">
      {/* Chat Sidebar */}
      <div className="hidden md:block h-full shrink-0">
        <ChatSidebar
          conversations={conversations}
          activeId={activeConversationId}
          onSelect={(id) => {
            setActiveConversationId(id);
            activeConversationIdRef.current = id;
            setCurrentThread(id);
            router.push(getSelectedThreadUrl(id));
          }}
          onNew={() => {
            setActiveConversationId(null);
            activeConversationIdRef.current = null;
            setMessages([]);
            setCurrentThread(null);
            router.push(getNewChatUrl());
          }}
          onRename={handleRenameThread}
          onDelete={handleDeleteThread}
          onBulkDelete={handleBulkDeleteThreads}
          currentWorkspace={workspace}
        />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col relative h-full min-w-0 overflow-hidden">
        <ChatHeader
          messages={displayedMessages}
          chatTitle={
            conversations.find((c) => c.id === activeConversationId)?.title ||
            'Chat'
          }
          onCopyAll={() => {
            const text = displayedMessages
              .map((m) => `[${m.role}] ${m.content}`)
              .join('\n\n');
            navigator.clipboard.writeText(text).catch(() => {});
          }}
        />

        {/* Messages Area */}
        {!isAuthenticated ? (
          <div className="flex-1 relative min-h-0">
            <div className="h-full overflow-y-auto overflow-x-hidden terminal-scrollbar">
              <div className="h-full flex flex-col items-center justify-center p-8">
                <div className="text-center">
                  <Loader2 className="w-8 h-8 text-[var(--amber-gold)] animate-spin mx-auto mb-4" />
                  <p className="text-sm font-mono text-[var(--terminal-text-muted)] mt-2">
                    Authentication required. Redirecting...
                  </p>
                </div>
              </div>
            </div>
          </div>
        ) : isInitializing ? (
          <div className="flex-1 relative min-h-0">
            <div className="h-full overflow-y-auto overflow-x-hidden terminal-scrollbar">
              <div className="h-full flex flex-col items-center justify-center p-8">
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center"
                >
                  <div className="relative w-12 h-12 mx-auto mb-6">
                    <Loader2 className="w-12 h-12 text-[var(--phosphor-green)] animate-spin" />
                  </div>
                  <h2
                    className="text-sm text-[var(--phosphor-green)] mb-2 tracking-widest"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    INITIALIZING...
                  </h2>
                </motion.div>
              </div>
            </div>
          </div>
        ) : initError ? (
          <div className="flex-1 relative min-h-0">
            <div className="h-full overflow-y-auto overflow-x-hidden terminal-scrollbar">
              <div className="h-full flex flex-col items-center justify-center p-8">
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="text-center max-w-md"
                >
                  <div className="relative w-16 h-16 mx-auto mb-6">
                    <div className="absolute inset-0 rounded-full bg-[var(--error-red)]/10" />
                    <div className="absolute inset-2 rounded-full border border-[var(--error-red)]/30 flex items-center justify-center">
                      <Activity className="w-6 h-6 text-[var(--error-red)]" />
                    </div>
                  </div>
                  <h2
                    className="text-lg text-[var(--error-red)] mb-3"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    CONNECTION ERROR
                  </h2>
                  <p
                    className="text-xs text-[var(--terminal-text-muted)] mb-6 p-3 rounded bg-[var(--error-red)]/5 border border-[var(--error-red)]/10"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    {initError}
                  </p>
                  <button
                    onClick={() => window.location.reload()}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[var(--terminal-surface)] border border-[var(--terminal-border)] text-[var(--terminal-text)] text-xs font-medium hover:border-[var(--phosphor-green)]/30 transition-all"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    <Activity className="w-3.5 h-3.5" />
                    RETRY CONNECTION
                  </button>
                </motion.div>
              </div>
            </div>
          </div>
        ) : isLoadingMessages ? (
          <div className="flex-1 relative min-h-0">
            <div className="h-full overflow-y-auto overflow-x-hidden terminal-scrollbar">
              <div className="h-full flex flex-col items-center justify-center p-8">
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center"
                >
                  <Loader2 className="w-8 h-8 text-[var(--phosphor-green)] animate-spin mx-auto mb-4" />
                  <p
                    className="text-xs text-[var(--terminal-text-muted)] tracking-wider"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    LOADING MESSAGES...
                  </p>
                </motion.div>
              </div>
            </div>
          </div>
        ) : displayedMessages.length === 0 && !storeIsStreaming ? (
          <div className="flex-1 relative min-h-0">
            <div className="h-full overflow-y-auto overflow-x-hidden terminal-scrollbar">
              <WelcomeState
                onPromptSelect={handlePromptSelect}
                selectedModel="nous-agent"
              />
            </div>
          </div>
        ) : (
          <ChatMessageList
            messages={displayedMessages}
            activeThreadId={activeThreadId}
            isLoading={isLoading}
            storeIsStreaming={storeIsStreaming}
            storeStreamingContent={storeStreamingContent}
            streamingTimestamp={streamingTimestampRef.current}
            onRegenerate={handleRegenerate}
            onCitationClick={handleCitationClick}
          />
        )}

        {/* HITL Confirmation Banner */}
        {pendingConfirmation && (
          <div className="mx-4 mb-2 p-4 rounded-xl border border-[var(--sol)]/30 bg-[var(--sol)]/5">
            <p className="text-xs font-mono text-[var(--terminal-text-muted)] uppercase tracking-wider mb-2">
              Action Requires Approval
            </p>
            <p className="text-sm font-mono text-[var(--terminal-text)] mb-3">
              The agent wants to run{' '}
              <span className="font-bold text-[var(--sol)]">
                {String(
                  pendingConfirmation.confirmation?.tool_name ||
                    'a destructive action'
                )}
              </span>
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => handleConfirmation(true)}
                disabled={isConfirming}
                className="px-4 py-2 rounded-lg bg-[var(--phosphor-green)] text-[var(--terminal-bg)] text-xs font-mono font-bold uppercase tracking-wider hover:shadow-[0_0_15px_var(--phosphor-green-glow)] disabled:opacity-50 transition-all"
              >
                {isConfirming ? 'Processing...' : 'Approve'}
              </button>
              <button
                onClick={() => handleConfirmation(false)}
                disabled={isConfirming}
                className="px-4 py-2 rounded-lg border border-red-500/30 bg-red-500/5 text-red-400 text-xs font-mono font-bold uppercase tracking-wider hover:bg-red-500/10 disabled:opacity-50 transition-all"
              >
                Deny
              </button>
            </div>
          </div>
        )}

        {/* Input Area */}
        <ChatInput
          value={input}
          onChange={setInput}
          onSubmit={handleSubmit}
          onStop={handleStop}
          isLoading={isLoading || storeIsStreaming || !!pendingConfirmation}
          enableRAG={enableRAG}
          onRAGToggle={setEnableRAG}
          inputRef={chatInputRef}
          onAttach={handleAttach}
          selectedModelId={selectedModel}
          onModelChange={setSelectedModel}
        />

        {/* Citation Panel Sidebar */}
        <CitationPanel
          citations={citationPanelCitations}
          isOpen={isCitationPanelOpen}
          onClose={() => setIsCitationPanelOpen(false)}
          onCitationClick={(citation) => {
            setActiveCitationId(citation.documentId);
            router.push(`/documents/${citation.documentId}`);
          }}
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
          <div className="text-center">
            <Loader2 className="w-12 h-12 text-[var(--phosphor-green)] animate-spin mx-auto mb-4" />
            <p className="text-sm font-mono text-[var(--terminal-text-muted)]">
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
