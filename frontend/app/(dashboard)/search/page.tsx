'use client';

import { CitationPanel } from '@/components/chat/CitationPanel';
import { ChatBubble } from '@/components/chat/shared/ChatBubble';
import { SearchComposer } from '@/components/chat/shared/SearchComposer';
import {
  ChatMessageViewModel,
  mapChatMessageToViewModel,
  mapSearchResultToChatMessages,
} from '@/components/chat/shared/messageViewModel';
import { getAnalytics } from '@/lib/analytics';
import { searchService } from '@/services/searchService';
import { SearchRequest } from '@/types/search';
import type { Citation } from '@/utils/citationParser';
import { AnimatePresence, motion } from 'framer-motion';
import { Brain, Database, FileText, Zap } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function SearchPage() {
  const [messages, setMessages] = useState<ChatMessageViewModel[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isCitationPanelOpen, setIsCitationPanelOpen] = useState(false);
  const [citationPanelCitations, setCitationPanelCitations] = useState<
    Citation[]
  >([]);
  const [activeCitationId, setActiveCitationId] = useState<string | undefined>(
    undefined
  );

  const router = useRouter();
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const loadingTimestampRef = useRef(Date.now());

  const suggestedQueries = [
    {
      icon: Database,
      label: 'Papers about transformers',
      cmd: 'transformers architecture',
    },
    {
      icon: Brain,
      label: 'Explain RAG systems',
      cmd: 'retrieval augmented generation',
    },
    {
      icon: FileText,
      label: 'Recent uploads',
      cmd: 'recently uploaded documents',
    },
    {
      icon: Zap,
      label: 'Optimization metrics',
      cmd: 'system performance metrics',
    },
  ];

  // Cancel in-flight requests on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Global "/" shortcut to focus composer
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (
        document.activeElement?.tagName === 'INPUT' ||
        document.activeElement?.tagName === 'TEXTAREA' ||
        (document.activeElement as HTMLElement)?.isContentEditable
      ) {
        return;
      }

      if (e.key === '/') {
        e.preventDefault();
        composerRef.current?.focus();
      }
    };

    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, []);

  useEffect(() => {
    try {
      const analytics = getAnalytics();
      analytics.trackPageView('/search', 'Semantic Search Chat');
    } catch (_error) {
      // noop
    }
  }, []);

  const toErrorMessage = (err: any): string => {
    if (err?.response?.data?.error) {
      return err.response.data.error.message || err.response.data.error;
    }

    if (err?.response?.data?.detail) {
      return err.response.data.detail;
    }

    if (err?.message) {
      return err.message;
    }

    return 'An unexpected error occurred';
  };

  const runSearch = useCallback(
    async (queryText?: string) => {
      const query = (queryText ?? input).trim();
      if (!query || isLoading) {
        return;
      }

      const userMessage = mapChatMessageToViewModel({
        role: 'user',
        content: query,
        timestamp: Date.now(),
      });

      setMessages((prev) => [...prev, userMessage]);
      setInput('');

      loadingTimestampRef.current = Date.now();
      setIsLoading(true);

      try {
        const analytics = getAnalytics();
        analytics.trackSearch(query, 0, 'semantic-chat');
      } catch (_error) {
        // noop
      }

      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const request: SearchRequest = { query, limit: 10 };
        const response = await searchService.search(request, controller.signal);

        if (response.success && response.data) {
          const mappedMessages = mapSearchResultToChatMessages(response.data);
          const assistantMessage = mappedMessages[1];
          setMessages((prev) => [...prev, assistantMessage]);

          try {
            await searchService.addToHistory(query, response.data.id);
          } catch (_historyError) {
            // noop
          }

          return;
        }

        const msg = response.message || 'Search failed';

        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: msg,
            timestamp: Date.now(),
          },
        ]);
      } catch (err: any) {
        if (
          controller.signal.aborted ||
          err?.name === 'CanceledError' ||
          err?.code === 'ERR_CANCELED'
        ) {
          return; // User cancelled — don't append error message
        }
        const msg = toErrorMessage(err);

        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: msg,
            timestamp: Date.now(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [input, isLoading]
  );

  // Run an initial query passed via ?q= (e.g. from the dashboard quick search).
  // Read from window to avoid a useSearchParams Suspense boundary on this page.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('q');
    if (q && q.trim()) {
      setInput(q);
      void runSearch(q);
    }
    // Mount-only: consume the param once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="relative flex h-full flex-col overflow-hidden">
      <div className="min-h-0 flex-1 overflow-y-auto">
        {messages.length === 0 && !isLoading ? (
          <div className="mx-auto flex h-full w-full max-w-4xl flex-col items-center justify-center p-8">
            <div className="mb-8 text-center">
              <h1
                className="mb-2 text-2xl font-semibold tracking-tight text-[var(--nous-fg-1)]"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                Semantic Search
              </h1>
              <p
                className="text-sm text-[var(--nous-fg-3)]"
                style={{ fontFamily: 'var(--nous-font-body)' }}
              >
                Ask questions and get synthesized answers with source citations.
              </p>
            </div>

            <div className="grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-2">
              {suggestedQueries.map((suggestion, idx) => (
                <motion.button
                  key={suggestion.cmd}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  onClick={() => runSearch(suggestion.cmd)}
                  className="group flex items-center gap-3 rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] p-3 text-left transition-all hover:border-[var(--nous-sol)]/30"
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--nous-bg-1)]">
                    <suggestion.icon className="h-4 w-4 text-[var(--nous-fg-3)] transition-colors group-hover:text-[var(--nous-sol)]" />
                  </div>
                  <span
                    className="truncate text-xs text-[var(--nous-fg-3)] transition-colors group-hover:text-[var(--nous-fg-1)]"
                    style={{ fontFamily: 'var(--nous-font-ui)' }}
                  >
                    {suggestion.label}
                  </span>
                </motion.button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto flex min-h-full w-full max-w-5xl flex-col justify-end px-4 pb-4 pt-4 2xl:max-w-6xl">
            <AnimatePresence>
              {messages.map((message, idx) => (
                <motion.div
                  key={message.id || `search-msg-${idx}`}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, transition: { duration: 0.2 } }}
                  transition={{
                    duration: 0.3,
                    delay: Math.min(idx * 0.03, 0.3),
                  }}
                >
                  <ChatBubble
                    message={message}
                    index={idx}
                    modelName={
                      message.role === 'assistant' ? 'SEMANTIC-RAG' : undefined
                    }
                    onCitationClick={(citations, clickedCitation) => {
                      setCitationPanelCitations(citations);
                      setActiveCitationId(clickedCitation.documentId);
                      setIsCitationPanelOpen(true);
                    }}
                  />
                </motion.div>
              ))}

              {isLoading && (
                <motion.div
                  key="search-loading-message"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10, transition: { duration: 0.2 } }}
                  transition={{ duration: 0.3 }}
                >
                  <ChatBubble
                    message={{
                      role: 'assistant',
                      content: '',
                      timestamp: loadingTimestampRef.current,
                    }}
                    index={messages.length}
                    isTyping={true}
                    modelName="SEMANTIC-RAG"
                  />
                </motion.div>
              )}
            </AnimatePresence>

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <SearchComposer
        value={input}
        onChange={setInput}
        onSubmit={() => runSearch()}
        onStop={() => {
          abortControllerRef.current?.abort();
          setIsLoading(false);
        }}
        isLoading={isLoading}
        textareaRef={composerRef}
      />

      <CitationPanel
        citations={citationPanelCitations}
        isOpen={isCitationPanelOpen}
        onClose={() => setIsCitationPanelOpen(false)}
        onCitationClick={(citation) => {
          setActiveCitationId(citation.documentId);
          if (citation.documentId) {
            router.push(`/documents/${citation.documentId}`);
          }
        }}
        activeCitationId={activeCitationId}
      />
    </div>
  );
}
