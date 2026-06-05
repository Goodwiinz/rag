'use client';

import { ChatInput, CitationPanel, WelcomeState } from '@/components/chat';
import { ChatDialogs } from '@/components/chat/ChatDialogs';
import { ChatHeader } from '@/components/chat/ChatHeader';
import { ChatMessageList } from '@/components/chat/ChatMessageList';
import { ChatSidebar } from '@/components/chat/ChatSidebar';
import { Skeleton } from '@/components/ui/skeleton';
import {
  getNewChatUrl,
  getSelectedThreadUrl,
} from '@/components/chat/shared/chatNavigation';
import { enhancedDocumentService } from '@/services/enhancedDocumentService';
import { Citation } from '@/utils/citationParser';
import { motion } from 'framer-motion';
import { Activity, Loader2, ShieldCheck } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Fragment, Suspense, useCallback, useEffect, useState } from 'react';
import { useChatSession } from '@/hooks/chat/useChatSession';
import { useChatStreaming } from '@/hooks/chat/useChatStreaming';
import { useChatThreadActions } from '@/hooks/chat/useChatThreadActions';
import {
  SLASH_COMMANDS,
  type SlashCommandId,
} from '@/components/chat/slashCommands';
import type {
  CommandAction,
  CommandOutput,
  CommandOutputItem,
} from '@/components/chat/commandOutput';
import { useProjectStore } from '@/store/projectStore';
import { documentService } from '@/services/documentService';

function relativeTime(ms: number): string {
  const diff = Date.now() - ms;
  if (diff < 60_000) return 'just now';
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(ms).toLocaleDateString();
}

// ============================================
// HITL HELPERS
// ============================================

interface ToolCallPreview {
  name: string;
  args: Record<string, unknown>;
}

function extractToolCall(
  confirmation: Record<string, unknown> | undefined
): ToolCallPreview | null {
  if (!confirmation) return null;
  const flatName = confirmation.tool_name as string | undefined;
  const flatArgs = (confirmation.tool_args ?? confirmation.args) as
    | Record<string, unknown>
    | undefined;
  if (flatName) return { name: flatName, args: flatArgs ?? {} };
  const tools = confirmation.tools as
    | Array<{ name?: string; args?: Record<string, unknown> }>
    | undefined;
  const first = tools?.[0];
  if (first?.name) return { name: first.name, args: first.args ?? {} };
  return null;
}

function formatArgValue(value: unknown, max = 140): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') {
    return value.length > max ? value.slice(0, max - 1) + '…' : value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  try {
    const s = JSON.stringify(value);
    return s.length > max ? s.slice(0, max - 1) + '…' : s;
  } catch {
    return '[unserializable]';
  }
}

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
    storeIsRetrievingRag,
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

  // Mobile sidebar drawer state
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

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

  // Start a fresh chat — shared by the sidebar "new" button and the /new command
  const startNewChat = useCallback(() => {
    setActiveConversationId(null);
    activeConversationIdRef.current = null;
    setMessages([]);
    setCurrentThread(null);
    router.push(getNewChatUrl());
  }, [
    router,
    setActiveConversationId,
    setMessages,
    setCurrentThread,
    activeConversationIdRef,
  ]);

  // Regenerate the most recent assistant response (the /retry command)
  const retryLast = useCallback(() => {
    const lastAssistantIdx = [...displayedMessages]
      .map((m, i) => ({ role: m.role, i }))
      .reverse()
      .find((x) => x.role === 'assistant')?.i;
    if (lastAssistantIdx !== undefined) handleRegenerate(lastAssistantIdx);
  }, [displayedMessages, handleRegenerate]);

  // ---- CLI slash-command output (ephemeral, in-chat) ----
  // Lives in page state, never in the message arrays, so it is never sent to
  // the agent or persisted. Cleared on thread change (effect below) and on send.
  const [commandOutputs, setCommandOutputs] = useState<CommandOutput[]>([]);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);

  useEffect(() => {
    setCommandOutputs([]);
  }, [activeThreadId]);

  const appendOutput = useCallback((o: CommandOutput) => {
    setCommandOutputs((prev) => [...prev, o]);
  }, []);

  const patchOutput = useCallback(
    (id: string, patch: Partial<CommandOutput>) => {
      setCommandOutputs((prev) =>
        prev.map((o) => (o.id === id ? { ...o, ...patch } : o))
      );
    },
    []
  );

  // Bind the chat to a project via the same ?projectId= param the context rail
  // uses (the streaming hook reads it into page_context).
  const handleSetProjectContext = useCallback(
    (projectId: string) => {
      const params = new URLSearchParams(window.location.search);
      params.set('projectId', projectId);
      router.replace(`/chat?${params.toString()}`);
    },
    [router]
  );

  // Run a slash command. Output prints into the chat transcript, CLI-style;
  // nothing navigates away (except /new, which starts a fresh chat).
  const handleSlashCommand = useCallback(
    (id: SlashCommandId) => {
      const now = Date.now();
      const outId = `cmd-${now}-${Math.random().toString(36).slice(2, 8)}`;
      switch (id) {
        case 'new':
          startNewChat();
          return;
        case 'retry':
          retryLast();
          return;
        case 'clear':
          setCommandOutputs([]);
          setInput('');
          return;
        case 'help':
          appendOutput({
            id: outId,
            command: '/help',
            timestamp: now,
            status: 'ready',
            lines: SLASH_COMMANDS.map((c) => `${c.label.padEnd(10)}${c.title}`),
            note: 'Type / in the message box to autocomplete.',
          });
          return;
        case 'threads': {
          const items: CommandOutputItem[] = conversations.map((c) => ({
            key: c.id,
            label: c.title || 'Untitled',
            meta: c.updatedAt ? relativeTime(c.updatedAt) : undefined,
            active: c.id === activeConversationId,
            action: { type: 'open-thread', id: c.id },
          }));
          appendOutput({
            id: outId,
            command: '/threads',
            timestamp: now,
            status: 'ready',
            items,
            emptyText: 'No threads yet.',
            note: items.length ? 'Tap a thread to open it.' : undefined,
          });
          return;
        }
        case 'projects':
          appendOutput({
            id: outId,
            command: '/projects',
            timestamp: now,
            status: 'loading',
            items: [],
          });
          void (async () => {
            try {
              await fetchProjects({ limit: 20, project_status: 'active' });
              const { projects, currentProject } = useProjectStore.getState();
              const items: CommandOutputItem[] = projects.map((p) => ({
                key: p.id,
                label: p.name,
                meta: p.project_type?.replace('_', ' '),
                active: p.id === currentProject?.id,
                action: { type: 'set-project', id: p.id, name: p.name },
              }));
              patchOutput(outId, {
                status: 'ready',
                items,
                emptyText: 'No active projects.',
                note: items.length
                  ? 'Tap a project to use it as context.'
                  : undefined,
              });
            } catch {
              patchOutput(outId, {
                status: 'ready',
                items: [],
                emptyText: 'Could not load projects.',
              });
            }
          })();
          return;
        case 'papers':
          appendOutput({
            id: outId,
            command: '/papers',
            timestamp: now,
            status: 'loading',
            items: [],
          });
          void (async () => {
            try {
              const res = await documentService.getDocuments(1, 10);
              const docs = res?.data?.documents ?? [];
              const items: CommandOutputItem[] = docs.map((d) => ({
                key: d.id,
                label: d.title || d.filename,
                meta: d.processing_status,
                action: {
                  type: 'cite-paper',
                  id: d.id,
                  title: d.title || d.filename,
                },
              }));
              patchOutput(outId, {
                status: 'ready',
                items,
                emptyText: 'No papers found.',
                note: items.length
                  ? 'Tap a paper to reference it in your message.'
                  : undefined,
              });
            } catch {
              patchOutput(outId, {
                status: 'ready',
                items: [],
                emptyText: 'Could not load papers.',
              });
            }
          })();
          return;
      }
    },
    [
      startNewChat,
      retryLast,
      setInput,
      conversations,
      activeConversationId,
      appendOutput,
      patchOutput,
      fetchProjects,
    ]
  );

  // A tap on a clickable command-output row.
  const handleCommandItemAction = useCallback(
    (action: CommandAction) => {
      switch (action.type) {
        case 'open-thread':
          setActiveConversationId(action.id);
          activeConversationIdRef.current = action.id;
          setCurrentThread(action.id);
          router.push(getSelectedThreadUrl(action.id));
          return;
        case 'set-project':
          handleSetProjectContext(action.id);
          setCommandOutputs([
            {
              id: `cmd-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
              command: '/projects',
              timestamp: Date.now(),
              status: 'ready',
              lines: [`Project context set: ${action.name}`],
            },
          ]);
          return;
        case 'cite-paper':
          setInput((cur) =>
            cur ? `${cur} "${action.title}"` : `"${action.title}" `
          );
          chatInputRef.current?.focus();
          return;
      }
    },
    [
      router,
      setActiveConversationId,
      setCurrentThread,
      activeConversationIdRef,
      handleSetProjectContext,
      setInput,
      chatInputRef,
    ]
  );

  // Clear ephemeral command output when a real message is sent.
  const submitMessage = useCallback(() => {
    setCommandOutputs([]);
    handleSubmit();
  }, [handleSubmit]);

  return (
    <div className="flex h-full w-full overflow-hidden bg-[var(--nous-bg-1)]">
      {/* Mobile sidebar backdrop + drawer */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 z-50 md:hidden"
          onClick={() => setMobileSidebarOpen(false)}
        >
          <div className="absolute inset-0 bg-[var(--nous-erebus)]/50" />
          <motion.div
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            exit={{ x: -280 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="absolute left-0 top-0 bottom-0 w-[280px] bg-[var(--nous-bg-2)] border-r border-[var(--nous-border-1)] shadow-[var(--nous-shadow-lg)]"
            onClick={(e) => e.stopPropagation()}
          >
            <ChatSidebar
              conversations={conversations}
              activeId={activeConversationId}
              onSelect={(id) => {
                setActiveConversationId(id);
                activeConversationIdRef.current = id;
                setCurrentThread(id);
                router.push(getSelectedThreadUrl(id));
                setMobileSidebarOpen(false);
              }}
              onNew={() => {
                startNewChat();
                setMobileSidebarOpen(false);
              }}
              onRename={handleRenameThread}
              onDelete={handleDeleteThread}
              onBulkDelete={handleBulkDeleteThreads}
              currentWorkspace={workspace}
            />
          </motion.div>
        </div>
      )}

      {/* Desktop sidebar */}
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
          onNew={startNewChat}
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
          onMobileSidebarToggle={() => setMobileSidebarOpen((v) => !v)}
        />

        {/* Messages Area */}
        {!isAuthenticated ? (
          <div className="flex-1 relative min-h-0">
            <div className="h-full overflow-y-auto overflow-x-hidden nous-scrollbar">
              <div className="h-full flex flex-col items-center justify-center p-8">
                <div className="text-center">
                  <Loader2 className="w-8 h-8 text-[var(--nous-sol)] animate-spin mx-auto mb-4" />
                  <p
                    className="text-sm text-[var(--nous-fg-3)] mt-2"
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
              <div className="h-full flex flex-col items-center justify-center p-8">
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center"
                >
                  <div className="relative w-12 h-12 mx-auto mb-6">
                    <Loader2 className="w-12 h-12 text-[var(--nous-sol)] animate-spin" />
                  </div>
                  <h2
                    className="text-sm text-[var(--nous-fg-3)] mb-2"
                    style={{ fontFamily: 'var(--nous-font-ui)' }}
                  >
                    Initializing...
                  </h2>
                </motion.div>
              </div>
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
                    <div className="absolute inset-0 rounded-full bg-[var(--nous-mars)]/10" />
                    <div className="absolute inset-2 rounded-full border border-[var(--nous-mars)]/30 flex items-center justify-center">
                      <Activity className="w-6 h-6 text-[var(--nous-mars)]" />
                    </div>
                  </div>
                  <h2
                    className="text-lg font-semibold text-[var(--nous-mars)] mb-3"
                    style={{ fontFamily: 'var(--nous-font-ui)' }}
                  >
                    Connection error
                  </h2>
                  <p
                    className="text-xs text-[var(--nous-fg-3)] mb-6 p-3 rounded-lg bg-[var(--nous-mars)]/5 border border-[var(--nous-mars)]/10"
                    style={{ fontFamily: 'var(--nous-font-ui)' }}
                  >
                    {initError}
                  </p>
                  <button
                    onClick={() => window.location.reload()}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--nous-bg-2)] border border-[var(--nous-border-1)] text-[var(--nous-fg-1)] text-xs font-medium hover:border-[var(--nous-sol)]/30 transition-all"
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
              <div
                className="mx-auto max-w-3xl space-y-8 p-6"
                aria-busy="true"
                aria-label="Loading messages"
              >
                {[0, 1, 2].map((row) => (
                  <div
                    key={row}
                    className={
                      row % 2 === 0
                        ? 'flex flex-col items-start gap-2'
                        : 'flex flex-col items-end gap-2'
                    }
                  >
                    <Skeleton className="h-3 w-24 rounded-md" />
                    <Skeleton
                      className={
                        row % 2 === 0
                          ? 'h-20 w-[80%] rounded-xl'
                          : 'h-12 w-[55%] rounded-xl'
                      }
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : displayedMessages.length === 0 &&
          commandOutputs.length === 0 &&
          !storeIsStreaming ? (
          <div className="flex-1 relative min-h-0">
            <div className="h-full overflow-y-auto overflow-x-hidden nous-scrollbar">
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
            commandOutputs={commandOutputs}
            onCommandItemAction={handleCommandItemAction}
          />
        )}

        {/* HITL Confirmation Banner */}
        {pendingConfirmation && (
          <div
            role="alertdialog"
            aria-label="Approval needed"
            className="mx-2 sm:mx-4 mb-2 p-3 sm:p-4 rounded-xl border border-[var(--nous-sol)]/30 bg-[var(--nous-sol)]/5"
          >
            <div className="mb-2 flex items-center gap-2">
              <ShieldCheck
                aria-hidden
                className="h-4 w-4 text-[var(--nous-sol)]"
                strokeWidth={1.8}
              />
              <p
                className="text-sm font-medium text-[var(--nous-fg-2)]"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                Approval needed
              </p>
            </div>
            {(() => {
              const call = extractToolCall(pendingConfirmation.confirmation);
              const argEntries = call ? Object.entries(call.args) : [];
              return (
                <>
                  <p
                    className="text-sm leading-relaxed text-[var(--nous-fg-1)] mb-3"
                    style={{ fontFamily: 'var(--nous-font-ui)' }}
                  >
                    The agent wants to run{' '}
                    <span
                      className="rounded bg-[var(--nous-sol-subtle)] px-1.5 py-0.5 text-[var(--nous-fg-accent)]"
                      style={{ fontFamily: 'var(--nous-font-mono)' }}
                    >
                      {call?.name ?? 'a destructive action'}
                    </span>
                    . Approve to let it continue, or deny to stop here.
                  </p>
                  {argEntries.length > 0 && (
                    <dl
                      className="mb-3 grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-1.5 rounded-lg border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]/60 p-3 text-xs"
                      aria-label="Tool arguments"
                    >
                      {argEntries.map(([key, value]) => (
                        <Fragment key={key}>
                          <dt
                            className="whitespace-nowrap text-[var(--nous-fg-3)]"
                            style={{ fontFamily: 'var(--nous-font-mono)' }}
                          >
                            {key}
                          </dt>
                          <dd
                            className="break-all text-[var(--nous-fg-2)]"
                            style={{ fontFamily: 'var(--nous-font-mono)' }}
                          >
                            {formatArgValue(value)}
                          </dd>
                        </Fragment>
                      ))}
                    </dl>
                  )}
                </>
              );
            })()}
            <div className="flex items-center gap-3">
              <button
                onClick={() => handleConfirmation(true)}
                disabled={isConfirming}
                className="px-4 py-2 rounded-xl bg-[var(--nous-sol)] text-[var(--nous-erebus)] text-xs font-semibold hover:brightness-110 disabled:opacity-50 transition-all"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                {isConfirming ? 'Processing…' : 'Approve'}
              </button>
              <button
                onClick={() => handleConfirmation(false)}
                disabled={isConfirming}
                className="px-4 py-2 rounded-xl border border-[var(--nous-mars)]/40 bg-[var(--nous-mars)]/5 text-[var(--nous-mars)] text-xs font-semibold hover:bg-[var(--nous-mars)]/10 disabled:opacity-50 transition-all"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
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
          onSubmit={submitMessage}
          onStop={handleStop}
          isLoading={isLoading || storeIsStreaming || !!pendingConfirmation}
          enableRAG={enableRAG}
          onRAGToggle={setEnableRAG}
          isRAGLoading={storeIsRetrievingRag}
          isStreaming={storeIsStreaming}
          streamingContent={storeStreamingContent}
          inputRef={chatInputRef}
          onAttach={handleAttach}
          selectedModelId={selectedModel}
          onModelChange={setSelectedModel}
          onCommand={handleSlashCommand}
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
            <Loader2 className="w-12 h-12 text-[var(--nous-sol)] animate-spin mx-auto mb-4" />
            <p
              className="text-sm text-[var(--nous-fg-3)]"
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
