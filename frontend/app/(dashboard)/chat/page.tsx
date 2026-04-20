'use client';

import { ChatInput, CitationPanel, WelcomeState } from '@/components/chat';
import { ChatHeader } from '@/components/chat/ChatHeader';
import { ChatSidebar } from '@/components/chat/ChatSidebar';
import {
  selectDisplayedMessages,
  syncConversationMessagesWithStore,
} from '@/components/chat/shared/cloudMessageView';
import {
  getNewChatUrl,
  getSelectedThreadUrl,
} from '@/components/chat/shared/chatNavigation';
import { TerminalChatBubble } from '@/components/chat/shared/TerminalChatBubble';
import { upsertConversationFromThreadDetail } from '@/components/chat/shared/threadConversationState';
import { buildThreadCreateRequest } from '@/components/chat/shared/threadCreation';
import { agentChatService } from '@/services/agentChatService';
import { workspaceService } from '@/services/workspaceService';
import { useChatStore } from '@/store/chat-store';
import { useAuthStore } from '@/stores/authStore';
import { useAgentActivityStore } from '@/stores/agentActivityStore';
import { deriveAgentName, deriveTask } from '@/components/context-rail';
import {
  ChatMessage as DBChatMessage,
  Conversation as DBConversation,
  MessageRole,
  Workspace,
} from '@/types/workspace';
import { Citation } from '@/utils/citationParser';
import { normalizeCitation } from '@/utils/citationNormalizer';
import { AnimatePresence, motion } from 'framer-motion';
import { Activity, ArrowDown, Loader2 } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useRef, useState } from 'react';

// ============================================
// HELPERS
// ============================================

/**
 * Generate a dynamic conversation title from the first message
 * Creates a clean, readable title instead of just truncating
 */
function generateConversationTitle(message: string): string {
  // Clean up the message
  let title = message.trim();

  // Remove common prefixes that don't add meaning
  const prefixesToRemove = [
    /^(hi|hello|hey|good morning|good afternoon|good evening)[,!\s]*/i,
    /^(can you|could you|would you|please|i need|i want|i'd like)[,\s]*/i,
    /^(help me|assist me|tell me|show me|explain)[,\s]*/i,
  ];

  for (const prefix of prefixesToRemove) {
    title = title.replace(prefix, '');
  }

  // Capitalize first letter
  title = title.charAt(0).toUpperCase() + title.slice(1);

  // Truncate to reasonable length (40 chars) at word boundary
  if (title.length > 40) {
    const truncated = title.substring(0, 40);
    const lastSpace = truncated.lastIndexOf(' ');
    if (lastSpace > 20) {
      title = truncated.substring(0, lastSpace) + '...';
    } else {
      title = truncated + '...';
    }
  }

  // If we stripped too much and title is too short, use a default approach
  if (title.length < 3) {
    title = message.trim().substring(0, 40);
    if (message.length > 40) title += '...';
  }

  return title;
}

// ============================================
// TYPES
// ============================================

interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
  diagnosticsTraceId?: string;
}

// UI Conversation type (mapped from DB Thread)
interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  modelId?: string;
  createdAt: number;
  updatedAt: number;
  threadId: string; // Links to DB Thread
  conversationId: string; // Links to DB Conversation
  previewText?: string;
  messageCount?: number;
}

// ============================================
// CONSTANTS
// ============================================

// ============================================
// MAIN PAGE COMPONENT
// ============================================

function ChatPageContent() {
  // Core state
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');

  // Database state
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [dbConversation, setDbConversation] = useState<DBConversation | null>(
    null
  );
  const [isInitializing, setIsInitializing] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);

  // Loading states
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

  // RAG state
  const [enableRAG, setEnableRAG] = useState(true);

  // Agent state
  const [agentThreadId, setAgentThreadId] = useState<string | null>(null);
  const agentThreadMapRef = useRef<Record<string, string>>({});

  // HITL confirmation state
  const [pendingConfirmation, setPendingConfirmation] = useState<{
    threadId: string;
    workspaceThreadId: string;
    confirmation: Record<string, unknown>;
  } | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const isHydratedRef = useRef(false);
  const lastStreamedContentRef = useRef<string>('');

  // Scroll state
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Citation panel state
  const [isCitationPanelOpen, setIsCitationPanelOpen] = useState(false);
  const [citationPanelCitations, setCitationPanelCitations] = useState<
    Citation[]
  >([]);
  const [activeCitationId, setActiveCitationId] = useState<string | undefined>(
    undefined
  );

  // Auth
  const { isAuthenticated } = useAuthStore();

  // Get currentThreadId and setCurrentThread from chat store to sync with sidebar
  const currentThreadIdFromStore = useChatStore(
    (state) => state.currentThreadId
  );
  const setCurrentThread = useChatStore((state) => state.setCurrentThread);
  const storeMessages = useChatStore((state) => state.messages);
  const addMessageToStore = useChatStore((state) => state.addMessageToStore);

  // Streaming state from store
  const storeStopStreaming = useChatStore((state) => state.stopStreaming);
  const storeIsStreaming = useChatStore((state) => state.isStreaming);
  const storeStreamingContent = useChatStore((state) => state.streamingContent);
  const activeThreadId = currentThreadIdFromStore || activeConversationId;
  const displayedMessages = selectDisplayedMessages({
    localMessages: messages,
    storeMessages: activeThreadId ? storeMessages[activeThreadId] || [] : [],
  });

  // Map DB messages to UI messages
  const mapDbMessageToUiMessage = useCallback(
    (dbMsg: DBChatMessage): Message => {
      return {
        id: dbMsg.id,
        role: dbMsg.role === MessageRole.USER ? 'user' : 'assistant',
        content: dbMsg.content,
        timestamp: new Date(dbMsg.created_at).getTime(),
        // Use normalizeCitation to handle both DB and API citation formats
        citations: dbMsg.citations?.map(normalizeCitation),
      };
    },
    []
  );

  // Capture a stable timestamp when streaming begins
  const streamingTimestampRef = useRef(Date.now());
  useEffect(() => {
    if (storeIsStreaming) {
      streamingTimestampRef.current = Date.now();
    }
  }, [storeIsStreaming]);

  useEffect(() => {
    if (!activeThreadId) {
      return;
    }

    const activeStoreMessages = storeMessages[activeThreadId] || [];

    if (activeStoreMessages.length === 0) {
      return;
    }

    setConversations((prev) =>
      syncConversationMessagesWithStore(
        prev,
        activeThreadId,
        activeStoreMessages
      )
    );
  }, [activeThreadId, storeMessages]);

  const searchParams = useSearchParams();
  const searchParamsRef = useRef(searchParams);
  searchParamsRef.current = searchParams;
  const router = useRouter();

  // Reset refs when user changes (logout/login)
  useEffect(() => {
    if (!isAuthenticated) {
      isHydratedRef.current = false;
    }
  }, [isAuthenticated]);

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
  }, []);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isAuthenticated && !isInitializing) {
      const timer = setTimeout(() => {
        router.push('/login');
      }, 1500); // Short delay to show the "Redirecting..." state
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, isInitializing, router]);

  // Handle thread switching from URL query param (single source of truth)
  useEffect(() => {
    if (conversations.length === 0 || isInitializing) {
      return;
    }

    const threadFromUrl = searchParams.get('thread');

    if (threadFromUrl) {
      console.log('[Chat] Thread switch requested:', threadFromUrl);
      const targetConv = conversations.find((c) => c.id === threadFromUrl);

      if (targetConv) {
        if (targetConv.id !== activeConversationId) {
          setActiveConversationId(targetConv.id);
          setMessages(targetConv.messages);
          // Also update the Zustand store so sidebar highlights correctly
          setCurrentThread(targetConv.id);
          console.log('[Chat] Switched to thread:', targetConv.title);
        }
        return;
      }

      console.log(
        '[Chat] Thread not found in conversations, fetching detail:',
        threadFromUrl
      );

      let cancelled = false;

      (async () => {
        try {
          const threadDetail = await workspaceService.getThread(threadFromUrl);
          if (cancelled) return;

          const uiMessages = threadDetail.messages.map(mapDbMessageToUiMessage);
          setConversations((prev) =>
            upsertConversationFromThreadDetail(
              prev,
              threadDetail,
              mapDbMessageToUiMessage
            )
          );
          setActiveConversationId(threadDetail.id);
          setMessages(uiMessages);
          setCurrentThread(threadDetail.id);
        } catch (error: unknown) {
          if (!cancelled) {
            console.error('[Chat] Failed to fetch requested thread:', error);
          }
        }
      })();

      return () => {
        cancelled = true;
      };
    }
  }, [
    searchParams,
    conversations,
    isInitializing,
    activeConversationId,
    mapDbMessageToUiMessage,
    setCurrentThread,
  ]);

  // Load threads and messages from database
  const loadThreadsFromDb = useCallback(
    async (conversationId: string, _isRetry = false): Promise<boolean> => {
      try {
        console.log(
          '[Chat] Loading threads from database for conversation:',
          conversationId
        );
        const threadResponse = await workspaceService.listThreads(
          conversationId,
          { limit: 50 }
        );

        // Map threads without loading messages (lazy-loaded on selection)
        const uiConversations: Conversation[] = threadResponse.threads.map(
          (thread) => ({
            id: thread.id,
            title: thread.title || 'New Chat',
            messages: [],
            createdAt: new Date(thread.created_at).getTime(),
            updatedAt: new Date(thread.updated_at).getTime(),
            threadId: thread.id,
            conversationId: conversationId,
            previewText: thread.summary || undefined,
            messageCount: thread.message_count,
          })
        );

        setConversations(uiConversations);
        console.log(
          '[Chat] Loaded',
          uiConversations.length,
          'threads from database'
        );

        // Restore active thread from URL param or default to first
        if (uiConversations.length > 0) {
          const threadFromUrl = searchParamsRef.current.get('thread');
          let selectedConv = uiConversations[0];

          if (threadFromUrl) {
            const urlConv = uiConversations.find((c) => c.id === threadFromUrl);
            if (urlConv) {
              selectedConv = urlConv;
              console.log(
                '[Chat] Restored thread from URL param:',
                urlConv.title
              );
            }
          }

          setActiveConversationId(selectedConv.id);
          setMessages(selectedConv.messages);
          // Sync with Zustand store for sidebar highlighting
          setCurrentThread(selectedConv.id);
          console.log('[Chat] Active thread:', selectedConv.title);
        }
        return true;
      } catch (error: unknown) {
        console.error('[Chat] Failed to load threads from database:', error);

        // Handle 404 - conversation not found (stale data)
        const err = error as {
          response?: { status?: number };
          status_code?: number;
        };
        if (err?.response?.status === 404 || err?.status_code === 404) {
          console.warn(
            '[Chat] Conversation not found (404) - clearing stale data'
          );
          // Clear stale localStorage data
          if (typeof window !== 'undefined') {
            localStorage.removeItem('default-workspace-id');
            localStorage.removeItem('default-conversation-id');
          }
          return false; // Signal to caller to retry with fresh data
        }

        throw error;
      }
    },
    [mapDbMessageToUiMessage, setCurrentThread]
  );

  // Initialize workspace and conversation from database
  useEffect(() => {
    const initializeFromDb = async () => {
      if (!isAuthenticated) {
        console.log(
          '[Chat] Not authenticated, skipping database initialization'
        );
        setIsInitializing(false);
        return;
      }

      try {
        console.log('[Chat] Initializing from database...');
        setIsInitializing(true);
        setInitError(null);

        // Get or create default workspace
        const ws = await workspaceService.getOrCreateDefaultWorkspace();
        setWorkspace(ws);
        console.log('[Chat] Workspace:', ws.name);

        // Get or create default conversation
        const conv = await workspaceService.getOrCreateDefaultConversation(
          ws.id
        );
        setDbConversation(conv);
        console.log('[Chat] DB Conversation:', conv.title);

        // Load threads - handle stale conversation data
        const loadSuccess = await loadThreadsFromDb(conv.id);

        // If load failed due to 404, create fresh conversation
        if (!loadSuccess) {
          console.log('[Chat] Retrying with fresh conversation...');
          const freshConv = await workspaceService.createConversation({
            workspace_id: ws.id,
            title: 'New Chat',
            description: 'A new conversation',
          });
          setDbConversation(freshConv);
          console.log('[Chat] Created fresh conversation:', freshConv.title);

          // Try loading threads again (should be empty for new conversation)
          await loadThreadsFromDb(freshConv.id);
        }

        isHydratedRef.current = true;
        console.log('[Chat] Database initialization complete');
      } catch (error: unknown) {
        console.error('[Chat] Failed to initialize from database:', error);

        // Handle 404 by clearing stale data and retrying once
        const err = error as { response?: { status?: number } };
        if (err?.response?.status === 404) {
          console.warn('[Chat] Stale data detected, clearing and retrying...');
          if (typeof window !== 'undefined') {
            localStorage.removeItem('default-workspace-id');
            localStorage.removeItem('default-conversation-id');
          }
          // Retry once after clearing stale data
          try {
            const ws = await workspaceService.getOrCreateDefaultWorkspace();
            setWorkspace(ws);
            const freshConv = await workspaceService.createConversation({
              workspace_id: ws.id,
              title: 'New Chat',
              description: 'A new conversation',
            });
            setDbConversation(freshConv);
            setConversations([]);
            setMessages([]);
            console.log('[Chat] Created fresh workspace and conversation');
            isHydratedRef.current = true;
            setIsInitializing(false);
            return;
          } catch (retryError) {
            console.error('[Chat] Retry failed:', retryError);
            setInitError(
              'Failed to create new chat session. Please refresh the page.'
            );
            setIsInitializing(false);
            return;
          }
        }

        setInitError(
          error instanceof Error ? error.message : 'Failed to load chat data'
        );
      } finally {
        setIsInitializing(false);
      }
    };

    initializeFromDb();
  }, [isAuthenticated, loadThreadsFromDb]);

  // Load messages when active conversation changes (lazy-load from API)
  useEffect(() => {
    if (!activeConversationId) {
      setIsLoadingMessages(false);
      return;
    }
    const conv = conversations.find((c) => c.id === activeConversationId);
    if (!conv) {
      setIsLoadingMessages(false);
      return;
    }

    // If messages already loaded (cached), use them directly
    if (conv.messages.length > 0) {
      setMessages(conv.messages);
      setIsLoadingMessages(false);
      return;
    }

    // Lazy-load messages for this thread
    let cancelled = false;
    setIsLoadingMessages(true);
    (async () => {
      try {
        const msgResponse = await workspaceService.listMessages(
          activeConversationId,
          { limit: 100 }
        );
        if (cancelled) return;
        const uiMessages = msgResponse.messages.map(mapDbMessageToUiMessage);
        // Update conversation cache so subsequent switches are instant
        setConversations((prev) =>
          prev.map((c) =>
            c.id === activeConversationId ? { ...c, messages: uiMessages } : c
          )
        );
        setMessages(uiMessages);
      } catch (err) {
        if (!cancelled) {
          console.error('[Chat] Failed to load messages:', err);
        }
      } finally {
        if (!cancelled) {
          setIsLoadingMessages(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only trigger on thread selection, not conversation updates
  }, [activeConversationId, mapDbMessageToUiMessage]);

  // Auto-scroll when new messages arrive or streaming content updates
  useEffect(() => {
    if (!showScrollButton) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [displayedMessages, storeStreamingContent, showScrollButton]);

  // Handle scroll to detect if user scrolled up
  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    setShowScrollButton(!isNearBottom && displayedMessages.length > 0);
  }, [displayedMessages.length]);

  // Scroll to bottom function
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    setShowScrollButton(false);
  }, []);

  // Send message
  const handleSubmit = async () => {
    if (!input.trim() || isLoading || storeIsStreaming) return;

    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
      timestamp: Date.now(),
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    // Create new thread if needed (when no active conversation)
    let currentConversationId = activeConversationId;
    let currentThreadId = activeConversationId;

    if (!currentConversationId && dbConversation) {
      try {
        const dynamicTitle = generateConversationTitle(input);
        console.log(
          '[Chat] Creating new thread in database with title:',
          dynamicTitle
        );
        const newThread = await workspaceService.createThread(
          buildThreadCreateRequest({
            conversationId: dbConversation.id,
            title: dynamicTitle,
          })
        );

        currentConversationId = newThread.id;
        currentThreadId = newThread.id;

        const newConv: Conversation = {
          id: newThread.id,
          title: newThread.title || dynamicTitle,
          messages: newMessages,
          createdAt: Date.now(),
          updatedAt: Date.now(),
          threadId: newThread.id,
          conversationId: dbConversation.id,
        };

        setConversations((prev) => [newConv, ...prev]);
        setActiveConversationId(newConv.id);
        setCurrentThread(newConv.id);
        router.replace(getSelectedThreadUrl(newThread.id));
        console.log('[Chat] Created new thread:', newThread.id);
      } catch (error) {
        console.error('[Chat] Failed to create thread:', error);
        setIsLoading(false);
        return;
      }
    }

    try {
      // Stream via Agent (LangGraph) backend
      const existingAgentThreadId = currentThreadId
        ? agentThreadMapRef.current[currentThreadId]
        : undefined;

      console.log(
        '[Chat] Starting agent stream, workspace thread:',
        currentThreadId,
        'agent thread:',
        existingAgentThreadId
      );

      let assistantContent = '';
      lastStreamedContentRef.current = '';
      let streamHadError = false;
      let streamHadConfirmation = false;

      // Set streaming state in store for UI
      useChatStore.setState({
        isStreaming: true,
        streamingContent: '',
      });

      if (currentThreadId) {
        useAgentActivityStore
          .getState()
          .startRun(
            currentThreadId,
            deriveAgentName(),
            deriveTask(input)
          );
      }

      await agentChatService.streamMessage(
        {
          messages: newMessages.map((m) => ({
            role: m.role,
            content: m.content,
          })),
          page_context: { type: 'chat' },
          use_rag: enableRAG,
          thread_id: existingAgentThreadId,
        },
        {
          onToken: (content) => {
            assistantContent += content;
            lastStreamedContentRef.current = assistantContent;
            useChatStore.setState({
              streamingContent: assistantContent,
            });
          },
          onToolStart: (tool, args) => {
            console.log('[Agent] Tool start:', tool, args);
            if (currentThreadId) {
              useAgentActivityStore
                .getState()
                .pushToolStart(currentThreadId, tool);
            }
          },
          onToolEnd: (tool, result) => {
            console.log('[Agent] Tool end:', tool, result);
            if (currentThreadId) {
              const ok = !(result && typeof result === 'object' && 'isError' in result && (result as { isError?: boolean }).isError === true);
              useAgentActivityStore
                .getState()
                .pushToolEnd(currentThreadId, tool, ok);
            }
          },
          onRagContext: (contexts) => {
            console.log('[Agent] RAG contexts:', contexts.length);
            useChatStore.setState({
              streamingCitations: contexts,
            });
          },
          onTrace: (threadId) => {
            // Capture agent thread_id from trace event for subsequent sends
            if (currentThreadId) {
              agentThreadMapRef.current[currentThreadId] = threadId;
            }
            setAgentThreadId(threadId);
          },
          onConfirmation: (threadId, confirmation) => {
            console.log('[Agent] HITL confirmation needed:', confirmation);
            streamHadConfirmation = true;
            // Store agent thread ID for confirmation flow
            if (currentThreadId) {
              agentThreadMapRef.current[currentThreadId] = threadId;
            }
            setAgentThreadId(threadId);
            setPendingConfirmation({
              threadId,
              workspaceThreadId: currentThreadId || '',
              confirmation,
            });
          },
          onDone: () => {
            console.log('[Agent] Stream complete');
            if (currentThreadId) {
              useAgentActivityStore
                .getState()
                .finishRun(currentThreadId, 'done');
            }
          },
          onError: (error) => {
            console.error('[Agent] Stream error:', error);
            streamHadError = true;
            if (currentThreadId) {
              useAgentActivityStore
                .getState()
                .finishRun(currentThreadId, 'error');
            }
            // Show error as assistant message instead of blank bubble
            const errorMsg: Message = {
              role: 'assistant',
              content: `Stream error: ${error}`,
              timestamp: Date.now(),
            };
            setMessages([...newMessages, errorMsg]);
          },
        }
      );

      // Don't append a normal message if stream errored or needs confirmation
      if (streamHadError || streamHadConfirmation) {
        useChatStore.setState({
          isStreaming: false,
          streamingContent: '',
          streamingCitations: [],
        });
        setIsLoading(false);
        return;
      }

      // Guard against empty content (no tokens received). Surface the failure
      // to the user instead of leaving an empty bubble — every "agent broke
      // upstream" failure (DNS, auth, model error) used to look identical from
      // the UI side.
      const finalContent = assistantContent || lastStreamedContentRef.current;
      if (!finalContent.trim()) {
        const emptyResponseMessage: Message = {
          role: 'assistant',
          content:
            '⚠ No response received from the agent. The stream completed without any tokens — check backend logs.',
          timestamp: Date.now(),
        };
        setMessages([...newMessages, emptyResponseMessage]);
        useChatStore.setState({
          isStreaming: false,
          streamingContent: '',
          streamingCitations: [],
        });
        setIsLoading(false);
        return;
      }

      // After streaming completes, build final message
      const finalAssistantMessage: Message = {
        role: 'assistant',
        content: finalContent,
        timestamp: Date.now(),
      };

      const finalMessages = [...newMessages, finalAssistantMessage];
      setMessages(finalMessages);

      // Save messages to workspace database for persistence
      if (currentThreadId && isAuthenticated) {
        try {
          // Save user message
          const savedUserMessage = await workspaceService.createMessage({
            thread_id: currentThreadId,
            content: input.trim(),
            role: MessageRole.USER,
          });
          addMessageToStore(currentThreadId, savedUserMessage);

          // Save assistant message
          const savedAssistantMessage = await workspaceService.createMessage({
            thread_id: currentThreadId,
            content: finalAssistantMessage.content,
            role: MessageRole.ASSISTANT,
          });
          addMessageToStore(currentThreadId, savedAssistantMessage);
          console.log('[Chat] Saved messages to database');
        } catch (error) {
          console.error('[Chat] Failed to save messages:', error);
        }
      }

      // Update conversation
      setConversations((prev) =>
        prev.map((conv) =>
          conv.id === currentConversationId
            ? { ...conv, messages: finalMessages, updatedAt: Date.now() }
            : conv
        )
      );
    } catch (err) {
      console.error('Failed to send message:', err);
      const errorMessage =
        'Error: ' +
        (err instanceof Error ? err.message : 'Failed to get response');

      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: errorMessage,
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setIsLoading(false);
      useChatStore.setState({
        isStreaming: false,
        streamingContent: '',
        streamingCitations: [],
      });
      lastStreamedContentRef.current = '';
    }
  };

  const handleStop = () => {
    setIsLoading(false);
    if (storeIsStreaming) {
      storeStopStreaming();
    }
    useChatStore.setState({
      isStreaming: false,
      streamingContent: '',
      streamingCitations: [],
    });
  };

  const handleConfirmation = async (confirmed: boolean) => {
    if (!pendingConfirmation) return;
    setIsConfirming(true);
    useChatStore.setState({ isStreaming: true, streamingContent: '' });

    let confirmContent = '';
    const confirmMessages = [...messages];

    try {
      await agentChatService.streamConfirm(
        { thread_id: pendingConfirmation.threadId, confirmed },
        {
          onToken: (content) => {
            confirmContent += content;
            useChatStore.setState({ streamingContent: confirmContent });
          },
          onDone: () => {
            if (confirmContent.trim()) {
              const msg: Message = {
                role: 'assistant',
                content: confirmContent,
                timestamp: Date.now(),
              };
              setMessages([...confirmMessages, msg]);
            }
          },
          onError: (error) => {
            console.error('[Agent] Confirm error:', error);
            const msg: Message = {
              role: 'assistant',
              content: `Confirmation error: ${error}`,
              timestamp: Date.now(),
            };
            setMessages([...confirmMessages, msg]);
          },
        }
      );
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : 'Network error during confirmation';
      const msg: Message = {
        role: 'assistant',
        content: `Confirmation failed: ${errorMessage}`,
        timestamp: Date.now(),
      };
      setMessages([...confirmMessages, msg]);
    } finally {
      setPendingConfirmation(null);
      setIsConfirming(false);
      useChatStore.setState({
        isStreaming: false,
        streamingContent: '',
      });
    }
  };

  const handlePromptSelect = (prompt: string) => {
    setInput(prompt);
  };

  return (
    <div className="flex h-full w-full overflow-hidden bg-[var(--terminal-bg)]">
      {/* Chat Sidebar */}
      <div className="hidden md:block h-full shrink-0">
        <ChatSidebar
          conversations={conversations}
          activeId={activeConversationId}
          onSelect={(id) => {
            setActiveConversationId(id);
            setCurrentThread(id);
            router.push(getSelectedThreadUrl(id));
          }}
          onNew={() => {
            setActiveConversationId(null);
            setMessages([]);
            setCurrentThread(null);
            router.push(getNewChatUrl());
          }}
        />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col relative h-full min-w-0 overflow-hidden">
        <ChatHeader currentWorkspace={workspace} />

        {/* Messages Area Wrapper */}
        <div className="flex-1 relative min-h-0">
          <div
            ref={scrollContainerRef}
            onScroll={handleScroll}
            className="h-full overflow-y-auto overflow-x-hidden terminal-scrollbar"
          >
            {/* Authentication Required State */}
            {!isAuthenticated ? (
              <div className="h-full flex flex-col items-center justify-center p-8">
                <div className="text-center">
                  <Loader2 className="w-8 h-8 text-[var(--amber-gold)] animate-spin mx-auto mb-4" />
                  <p className="text-sm font-mono text-[var(--terminal-text-muted)] mt-2">
                    Authentication required. Redirecting...
                  </p>
                </div>
              </div>
            ) : isInitializing ? (
              /* Loading State */
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
            ) : initError ? (
              /* Error State */
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
            ) : isLoadingMessages ? (
              /* Loading Messages State */
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
            ) : displayedMessages.length === 0 && !storeIsStreaming ? (
              <WelcomeState
                onPromptSelect={handlePromptSelect}
                selectedModel="nous-agent"
              />
            ) : (
              <div className="max-w-4xl mx-auto pt-4 px-4 pb-6">
                <AnimatePresence>
                  {displayedMessages.map((message, index) => (
                    <motion.div
                      key={message.id || `msg-${index}`}
                      initial={{ opacity: 0, y: 20, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, transition: { duration: 0.2 } }}
                      transition={{
                        duration: 0.4,
                        delay: Math.min(index * 0.03, 0.3),
                        ease: [0.25, 0.46, 0.45, 0.94],
                      }}
                    >
                      <TerminalChatBubble
                        message={message}
                        index={index}
                        modelName={
                          message.role === 'assistant'
                            ? 'NOUS AGENT'
                            : undefined
                        }
                        isTyping={
                          index === displayedMessages.length - 1 &&
                          isLoading &&
                          !storeIsStreaming &&
                          message.role === 'assistant'
                        }
                        onCitationClick={(citations, clickedCitation) => {
                          setCitationPanelCitations(citations);
                          setActiveCitationId(clickedCitation.documentId);
                          setIsCitationPanelOpen(true);
                        }}
                      />
                    </motion.div>
                  ))}

                  {/* Virtual streaming assistant message (shown during SSE streaming) */}
                  {storeIsStreaming && (
                    <motion.div
                      key="streaming-message"
                      initial={{ opacity: 0, y: 20, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{
                        opacity: 0,
                        y: -10,
                        transition: { duration: 0.2 },
                      }}
                      transition={{ duration: 0.3 }}
                    >
                      <TerminalChatBubble
                        message={{
                          role: 'assistant',
                          content: '',
                          timestamp: streamingTimestampRef.current,
                        }}
                        index={displayedMessages.length}
                        modelName="NOUS AGENT"
                        isStreaming={true}
                        streamingContent={storeStreamingContent}
                        onCitationClick={(citations, clickedCitation) => {
                          setCitationPanelCitations(citations);
                          setActiveCitationId(clickedCitation.documentId);
                          setIsCitationPanelOpen(true);
                        }}
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Scroll to bottom button - Absolute positioned within wrapper */}
          <AnimatePresence>
            {showScrollButton && (
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
                <motion.button
                  initial={{ opacity: 0, y: 10, scale: 0.9 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 10, scale: 0.9 }}
                  onClick={scrollToBottom}
                  className="flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--phosphor-green)] text-[var(--terminal-bg)] text-xs font-bold shadow-[0_0_20px_var(--phosphor-green-glow)] hover:shadow-[0_0_30px_var(--phosphor-green-glow)] transition-all pointer-events-auto border border-[var(--terminal-bg)]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <ArrowDown className="w-4 h-4" />
                  <span className="hidden sm:inline tracking-wider">
                    NEW MESSAGES
                  </span>
                </motion.button>
              </div>
            )}
          </AnimatePresence>
        </div>

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
        />

        {/* Citation Panel Sidebar */}
        <CitationPanel
          citations={citationPanelCitations}
          isOpen={isCitationPanelOpen}
          onClose={() => setIsCitationPanelOpen(false)}
          onCitationClick={(citation) => {
            setActiveCitationId(citation.documentId);
            // Navigate to document detail page
            router.push(`/documents/${citation.documentId}`);
          }}
          activeCitationId={activeCitationId}
        />
      </div>
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
