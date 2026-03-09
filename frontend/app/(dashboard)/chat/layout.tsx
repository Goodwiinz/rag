'use client';

import { useChatPersistence } from '@/hooks';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';
import { workspaceService } from '@/services/workspaceService';
import type {
  Collection as WorkspaceCollection,
  Workspace as WorkspaceType,
} from '@/types/workspace';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  ArrowUp,
  BookOpen,
  Cpu,
  FileText,
  FolderOpen,
  Plus,
  Search,
  Settings,
  Share2,
  Sparkles,
  X,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// ============================================
// TYPES
// ============================================

// Note: Collection and Workspace types are imported from @/types/workspace
// as WorkspaceCollection and WorkspaceType respectively

// ============================================
// COMMAND PALETTE
// ============================================

function CommandPalette({
  isOpen,
  onClose,
  onExecute,
}: {
  isOpen: boolean;
  onClose: () => void;
  onExecute?: (commandId: string) => void;
}) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands = [
    {
      id: 'new-chat',
      label: 'New Chat',
      icon: Plus,
      shortcut: '⌘N',
      category: 'actions',
    },
    {
      id: 'upload',
      label: 'Upload Document',
      icon: FileText,
      shortcut: '⌘U',
      category: 'actions',
    },
    {
      id: 'search',
      label: 'Search Documents',
      icon: Search,
      shortcut: '⌘/',
      category: 'actions',
    },
    {
      id: 'collection',
      label: 'Create Collection',
      icon: FolderOpen,
      shortcut: '⌘G',
      category: 'actions',
    },
    {
      id: 'settings',
      label: 'Open Settings',
      icon: Settings,
      shortcut: '⌘,',
      category: 'actions',
    },
    {
      id: 'arxiv',
      label: 'Browse ArXiv Papers',
      icon: BookOpen,
      category: 'navigate',
    },
    {
      id: 'dashboard',
      label: 'Go to Dashboard',
      icon: Activity,
      category: 'navigate',
    },
    {
      id: 'entities',
      label: 'Knowledge Graph',
      icon: Share2,
      category: 'navigate',
    },
  ];

  const filteredCommands = commands.filter((cmd) =>
    cmd.label.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
      setQuery('');
      setSelectedIndex(0);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filteredCommands.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter' && filteredCommands[selectedIndex]) {
        e.preventDefault();
        onExecute?.(filteredCommands[selectedIndex].id);
        onClose();
      } else if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, filteredCommands, selectedIndex, onClose, onExecute]);

  if (!isOpen) return null;

  const groupedCommands = filteredCommands.reduce(
    (acc, cmd) => {
      if (!acc[cmd.category]) acc[cmd.category] = [];
      acc[cmd.category].push(cmd);
      return acc;
    },
    {} as Record<string, typeof commands>
  );

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
        onClick={onClose}
      >
        {/* Backdrop */}
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

        {/* Palette */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: -20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -20 }}
          transition={{ duration: 0.15, ease: 'easeOut' }}
          onClick={(e) => e.stopPropagation()}
          className="relative w-full max-w-2xl terminal-window overflow-hidden"
        >
          {/* Search Input */}
          <div className="flex items-center gap-3 px-4 py-4 border-b border-[var(--terminal-border)]">
            <Search className="w-5 h-5 text-[var(--phosphor-green)]" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 bg-transparent text-[var(--terminal-text)] text-sm outline-none"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            />
            <kbd
              className="px-2 py-1 rounded bg-[var(--terminal-border)] text-[10px] text-[var(--terminal-text-dim)]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              ESC
            </kbd>
          </div>

          {/* Results */}
          <div className="max-h-[60vh] overflow-y-auto terminal-scrollbar p-2">
            {Object.entries(groupedCommands).map(([category, cmds]) => (
              <div key={category} className="mb-4">
                <div
                  className="px-3 py-2 text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  {category === 'actions' ? '⚡ Quick Actions' : '🔗 Navigate'}
                </div>
                {cmds.map((cmd, _idx) => {
                  const globalIdx = filteredCommands.indexOf(cmd);
                  return (
                    <button
                      key={cmd.id}
                      className={cn(
                        'w-full flex items-center gap-3 px-3 py-3 rounded transition-all',
                        globalIdx === selectedIndex
                          ? 'bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/30'
                          : 'hover:bg-[var(--terminal-elevated)]'
                      )}
                      onClick={() => {
                        onExecute?.(cmd.id);
                        onClose();
                      }}
                    >
                      <cmd.icon
                        className={cn(
                          'w-4 h-4',
                          globalIdx === selectedIndex
                            ? 'text-[var(--phosphor-green)]'
                            : 'text-[var(--terminal-text-dim)]'
                        )}
                      />
                      <span
                        className={cn(
                          'flex-1 text-left text-sm',
                          globalIdx === selectedIndex
                            ? 'text-[var(--phosphor-green)]'
                            : 'text-[var(--terminal-text)]'
                        )}
                        style={{ fontFamily: "'JetBrains Mono', monospace" }}
                      >
                        {cmd.label}
                      </span>
                      {cmd.shortcut && (
                        <kbd
                          className="px-1.5 py-0.5 rounded bg-[var(--terminal-border)] text-[10px] text-[var(--terminal-text-muted)]"
                          style={{ fontFamily: "'JetBrains Mono', monospace" }}
                        >
                          {cmd.shortcut}
                        </kbd>
                      )}
                    </button>
                  );
                })}
              </div>
            ))}

            {filteredCommands.length === 0 && (
              <div className="text-center py-8">
                <Search className="w-8 h-8 text-[var(--terminal-border)] mx-auto mb-2" />
                <p
                  className="text-sm text-[var(--terminal-text-muted)]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  No results found
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
            <div
              className="flex items-center gap-4 text-[10px] text-[var(--terminal-text-muted)]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <span className="flex items-center gap-1">
                <kbd className="px-1 rounded bg-[var(--terminal-border)]">
                  ↑↓
                </kbd>{' '}
                Navigate
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1 rounded bg-[var(--terminal-border)]">
                  ↵
                </kbd>{' '}
                Select
              </span>
            </div>
            <span
              className="text-[10px] text-[var(--terminal-text-muted)]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {filteredCommands.length} results
            </span>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// ============================================
// CITATIONS TAB CONTENT
// ============================================

// Terminal Observatory theme colors
const PHOSPHOR_GREEN = '#00ff9f';
const AMBER = '#ffb700';

interface CitationItem {
  id?: string;
  documentId?: string;
  externalReferenceId?: string;
  title?: string;
  snippet?: string;
  score?: number;
  source?: string;
}

function CitationsTabContent() {
  const { conversations, currentThreadId } = useChatPersistence();

  // Get citations from the current conversation's messages
  // Only include citations that are actually referenced in the response text
  const citations = useMemo(() => {
    if (!currentThreadId) return [];

    const currentConv = conversations.find(
      (c) => c.threadId === currentThreadId
    );
    if (!currentConv) return [];

    // Collect only citations that are actually referenced in assistant messages
    const allCitations: CitationItem[] = [];
    const seenIds = new Set<string>();

    currentConv.messages.forEach((msg) => {
      if (msg.role === 'assistant' && msg.citations) {
        const msgCitations = msg.citations as CitationItem[];

        // Show all retrieved sources in the Citations panel
        // The inline citations in the text ([1], [Doc 1], etc.) will link to specific sources
        // but the panel shows all available sources for reference
        const citationsToShow = msgCitations;

        citationsToShow.forEach((cit) => {
          const citId = cit.documentId || cit.externalReferenceId || cit.id;
          if (citId && !seenIds.has(citId)) {
            seenIds.add(citId);
            allCitations.push(cit);
          }
        });
      }
    });

    return allCitations;
  }, [conversations, currentThreadId]);

  if (citations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-4">
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
          style={{
            backgroundColor: `${PHOSPHOR_GREEN}10`,
            border: `1px solid ${PHOSPHOR_GREEN}20`,
          }}
        >
          <BookOpen className="w-6 h-6" style={{ color: PHOSPHOR_GREEN }} />
        </div>
        <p
          className="text-xs text-center mb-2"
          style={{
            color: 'var(--terminal-text-muted)',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          No citations yet
        </p>
        <p
          className="text-[10px] text-center max-w-[200px]"
          style={{
            color: 'var(--terminal-text-dim)',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          Citations from RAG search results will appear here as you chat
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div
        className="text-[10px] uppercase tracking-wider mb-3"
        style={{
          color: `${PHOSPHOR_GREEN}80`,
          fontFamily: "'JetBrains Mono', monospace",
        }}
      >
        {citations.length} Source{citations.length !== 1 ? 's' : ''} Referenced
      </div>

      {citations.map((citation, idx) => {
        const isExternal = !citation.documentId;
        const scorePercent = citation.score
          ? Math.round(citation.score * 100)
          : 0;

        return (
          <div
            key={citation.id || idx}
            className="rounded-lg overflow-hidden transition-colors"
            style={{
              backgroundColor: '#0a0a0a',
              border: '1px solid #1a1a1a',
            }}
          >
            <div className="p-3">
              <div className="flex items-start gap-3">
                {/* Icon */}
                <div
                  className="w-7 h-7 rounded-md flex items-center justify-center shrink-0"
                  style={{
                    backgroundColor: isExternal
                      ? `${AMBER}10`
                      : `${PHOSPHOR_GREEN}10`,
                    border: `1px solid ${isExternal ? AMBER : PHOSPHOR_GREEN}20`,
                  }}
                >
                  {isExternal ? (
                    <BookOpen
                      className="w-3.5 h-3.5"
                      style={{ color: AMBER }}
                    />
                  ) : (
                    <FileText
                      className="w-3.5 h-3.5"
                      style={{ color: PHOSPHOR_GREEN }}
                    />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <p
                    className="text-xs font-medium leading-tight line-clamp-2 mb-1"
                    style={{
                      color: isExternal ? AMBER : PHOSPHOR_GREEN,
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {citation.title || 'Untitled Source'}
                  </p>

                  <div className="flex items-center gap-2">
                    {citation.source && (
                      <span
                        className="text-[9px] px-1.5 py-0.5 rounded"
                        style={{
                          backgroundColor: '#1a1a1a',
                          color: 'var(--terminal-text-dim)',
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        {citation.source}
                      </span>
                    )}
                    {isExternal && (
                      <span
                        className="text-[9px] px-1.5 py-0.5 rounded"
                        style={{
                          backgroundColor: `${AMBER}15`,
                          color: AMBER,
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        External
                      </span>
                    )}
                    {scorePercent > 0 && (
                      <span
                        className="text-[9px] px-1.5 py-0.5 rounded ml-auto"
                        style={{
                          backgroundColor:
                            scorePercent >= 70
                              ? 'rgba(34, 197, 94, 0.15)'
                              : scorePercent >= 50
                                ? 'rgba(234, 179, 8, 0.15)'
                                : 'rgba(239, 68, 68, 0.15)',
                          color:
                            scorePercent >= 70
                              ? '#22c55e'
                              : scorePercent >= 50
                                ? '#eab308'
                                : '#ef4444',
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        {scorePercent}%
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Snippet preview */}
              {citation.snippet && (
                <p
                  className="text-[10px] mt-2 line-clamp-2 leading-relaxed"
                  style={{
                    color: 'var(--terminal-text-muted)',
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  {citation.snippet}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ============================================
// CONTEXT PANEL (RIGHT)
// ============================================

function ContextPanel({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const [activeTab, setActiveTab] = useState<
    'context' | 'citations' | 'settings'
  >('context');
  const {
    conversations,
    currentThreadId,
    messages: _messages,
  } = useChatPersistence();
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const lastMessageIdRef = useRef<string | null>(null);

  // Get the most relevant document (highest score citation)
  const activeDocument = useMemo((): CitationItem | null => {
    if (!currentThreadId) return null;
    const currentConv = conversations.find(
      (c) => c.threadId === currentThreadId
    );
    if (!currentConv) return null;

    let highestScoreCitation: CitationItem | null = null;
    let highestScore = 0;

    currentConv.messages.forEach((msg) => {
      if (msg.role === 'assistant' && msg.citations) {
        (msg.citations as CitationItem[]).forEach((cit) => {
          if ((cit.score || 0) > highestScore) {
            highestScore = cit.score || 0;
            highestScoreCitation = cit;
          }
        });
      }
    });

    return highestScoreCitation;
  }, [conversations, currentThreadId]);

  // Get all related results (deduplicated citations sorted by score)
  const relatedResults = useMemo((): CitationItem[] => {
    if (!currentThreadId) return [];
    const currentConv = conversations.find(
      (c) => c.threadId === currentThreadId
    );
    if (!currentConv) return [];

    const allCitations: CitationItem[] = [];
    const seenIds = new Set<string>();

    currentConv.messages.forEach((msg) => {
      if (msg.role === 'assistant' && msg.citations) {
        (msg.citations as CitationItem[]).forEach((cit) => {
          const citId = cit.documentId || cit.externalReferenceId;
          if (citId && !seenIds.has(citId)) {
            seenIds.add(citId);
            allCitations.push(cit);
          }
        });
      }
    });

    return allCitations
      .sort((a, b) => (b.score || 0) - (a.score || 0))
      .slice(0, 5);
  }, [conversations, currentThreadId]);

  // Fetch AI-generated suggestions when a new assistant message appears
  const fetchSuggestions = useCallback(
    async (lastAssistantContent: string, lastCitations: CitationItem[]) => {
      setLoadingSuggestions(true);
      try {
        const token = useAuthStore.getState().token;
        if (!token) {
          setSuggestions([]);
          setLoadingSuggestions(false);
          return;
        }

        const response = await fetch('/api/v1/chat/suggestions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            messages: [{ role: 'assistant', content: lastAssistantContent }],
            citations: lastCitations.map((c) => ({
              document_id: c.documentId || '',
              title: c.title || '',
              content: c.snippet || '',
              score: c.score || 0,
              source: c.source || '',
            })),
            count: 3,
          }),
        });
        if (response.ok) {
          const data = await response.json();
          setSuggestions(data.suggestions || []);
        } else {
          setSuggestions([]);
        }
      } catch {
        setSuggestions([]);
      } finally {
        setLoadingSuggestions(false);
      }
    },
    []
  );

  // Watch for new assistant messages and fetch suggestions
  useEffect(() => {
    if (!currentThreadId) return;
    const currentConv = conversations.find(
      (c) => c.threadId === currentThreadId
    );
    if (!currentConv) return;

    const assistantMessages = currentConv.messages.filter(
      (m) => m.role === 'assistant'
    );
    const lastAssistant = assistantMessages[assistantMessages.length - 1];

    if (lastAssistant && lastAssistant.id !== lastMessageIdRef.current) {
      lastMessageIdRef.current = lastAssistant.id || null;
      const citations = (lastAssistant.citations || []) as CitationItem[];
      if (lastAssistant.content) {
        fetchSuggestions(lastAssistant.content, citations);
      }
    }
  }, [conversations, currentThreadId, fetchSuggestions]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.aside
        initial={{ width: 0, opacity: 0 }}
        animate={{ width: 320, opacity: 1 }}
        exit={{ width: 0, opacity: 0 }}
        transition={{ duration: 0.2, ease: 'easeInOut' }}
        className="hidden xl:block border-l border-[var(--terminal-border)] bg-[var(--terminal-bg)] flex-shrink-0 overflow-hidden"
      >
        {/* Header with close button */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--terminal-border)]">
          <div className="flex items-center gap-1">
            {[
              { id: 'context', label: 'Context', icon: FileText },
              { id: 'citations', label: 'Citations', icon: BookOpen },
              { id: 'settings', label: 'Settings', icon: Settings },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={cn(
                  'flex items-center gap-2 px-2 py-1.5 rounded text-[10px] transition-colors',
                  activeTab === tab.id
                    ? 'bg-[var(--phosphor-green)]/10 text-[var(--phosphor-green)]'
                    : 'text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)]'
                )}
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                <tab.icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            ))}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] transition-colors"
            aria-label="Close context panel"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 overflow-y-auto terminal-scrollbar h-[calc(100%-48px)]">
          {activeTab === 'context' && (
            <div className="space-y-4">
              {/* Document Inspector - Most Relevant RAG Result */}
              <div className="terminal-window p-3">
                <div
                  className="text-[10px] text-[var(--phosphor-green)] uppercase tracking-wider mb-3"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  ACTIVE DOCUMENT
                </div>
                {activeDocument ? (
                  <div
                    className="space-y-2 text-[11px]"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-[var(--terminal-text-muted)] shrink-0">
                        Title
                      </span>
                      <span
                        className="text-[var(--terminal-text)] text-right truncate"
                        title={activeDocument.title}
                      >
                        {activeDocument.title
                          ? activeDocument.title.length > 30
                            ? activeDocument.title.slice(0, 30) + '...'
                            : activeDocument.title
                          : 'Untitled'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--terminal-text-muted)]">
                        Relevance
                      </span>
                      <span className="text-[var(--phosphor-green)]">
                        {activeDocument.score
                          ? Math.round(activeDocument.score * 100)
                          : 0}
                        %
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--terminal-text-muted)]">
                        Source
                      </span>
                      <span className="text-[var(--terminal-text)] capitalize">
                        {activeDocument.source || 'document'}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div
                    className="text-[11px] text-[var(--terminal-text-muted)]"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    No active document yet
                  </div>
                )}
              </div>

              {/* Related Documents - From RAG Citations */}
              <div>
                <div
                  className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider mb-2"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  RELATED RESULTS
                </div>
                {relatedResults.length > 0 ? (
                  relatedResults.map((doc, idx) => {
                    const scorePercent = doc.score
                      ? Math.round(doc.score * 100)
                      : 0;
                    const _isExternal = !doc.documentId;
                    return (
                      <button
                        key={doc.documentId || doc.externalReferenceId || idx}
                        className="w-full flex items-start gap-3 p-3 rounded-lg border border-[var(--terminal-border)] hover:border-[var(--phosphor-green)]/30 hover:bg-[var(--terminal-elevated)] transition-all mb-2 text-left group"
                      >
                        <div className="flex-1 min-w-0">
                          <p
                            className="text-xs font-medium text-[var(--terminal-text)] truncate group-hover:text-[var(--phosphor-green)] transition-colors"
                            style={{
                              fontFamily: "'JetBrains Mono', monospace",
                            }}
                            title={doc.title}
                          >
                            {doc.title || 'Untitled Document'}
                          </p>
                          <p
                            className="text-[10px]"
                            style={{
                              fontFamily: "'JetBrains Mono', monospace",
                              color:
                                scorePercent >= 70
                                  ? 'var(--phosphor-green-dim)'
                                  : scorePercent >= 50
                                    ? 'var(--amber-gold-dim)'
                                    : 'var(--terminal-text-muted)',
                            }}
                          >
                            {scorePercent}% match
                          </p>
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <div
                    className="text-[11px] text-[var(--terminal-text-muted)] py-3"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    No related documents yet
                  </div>
                )}
              </div>

              {/* AI Suggestions */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="w-3.5 h-3.5" style={{ color: AMBER }} />
                  <div
                    className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    FOLLOW-UP SUGGESTIONS
                  </div>
                </div>
                {loadingSuggestions ? (
                  // Skeleton loading state
                  <div className="space-y-2">
                    {[1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)]"
                      >
                        <div
                          className="w-5 h-5 rounded-md bg-[var(--terminal-elevated)] animate-pulse"
                          style={{ animationDelay: `${i * 100}ms` }}
                        />
                        <div className="flex-1 space-y-1.5">
                          <div
                            className="h-2.5 rounded bg-[var(--terminal-elevated)] animate-pulse"
                            style={{
                              width: `${70 - i * 10}%`,
                              animationDelay: `${i * 100}ms`,
                            }}
                          />
                          <div
                            className="h-2 rounded bg-[var(--terminal-elevated)] animate-pulse"
                            style={{
                              width: `${40 - i * 5}%`,
                              animationDelay: `${i * 100 + 50}ms`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : suggestions.length > 0 ? (
                  <div className="space-y-2">
                    {suggestions.map((suggestion, idx) => (
                      <button
                        key={idx}
                        className="group flex items-start gap-3 w-full px-3 py-2.5 rounded-lg text-left border border-[var(--terminal-border)] bg-[var(--terminal-surface)] hover:border-[var(--amber-gold)]/40 hover:bg-[var(--terminal-elevated)] transition-all duration-200 hover:shadow-[0_0_12px_-4px_var(--amber-gold)]"
                        style={{ fontFamily: "'JetBrains Mono', monospace" }}
                        onClick={() => {
                          window.dispatchEvent(
                            new CustomEvent('populate-chat-input', {
                              detail: suggestion,
                            })
                          );
                        }}
                      >
                        {/* Number badge */}
                        <div className="flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center text-[9px] font-bold border border-[var(--terminal-border)] group-hover:border-[var(--amber-gold)]/40 group-hover:text-[var(--amber-gold)] text-[var(--terminal-text-dim)] transition-colors">
                          {idx + 1}
                        </div>

                        {/* Suggestion text */}
                        <span className="flex-1 text-[11px] text-[var(--terminal-text)] leading-relaxed group-hover:text-[var(--amber-gold)] transition-colors">
                          {suggestion}
                        </span>

                        {/* Arrow indicator */}
                        <ArrowUp className="w-3 h-3 rotate-45 text-[var(--terminal-text-dim)] opacity-0 group-hover:opacity-100 group-hover:text-[var(--amber-gold)] transition-all flex-shrink-0 mt-0.5" />
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center py-6 px-3 rounded-lg border border-dashed border-[var(--terminal-border)] bg-[var(--terminal-surface)]/50">
                    <div
                      className="w-10 h-10 rounded-xl flex items-center justify-center mb-3"
                      style={{
                        backgroundColor: `${AMBER}10`,
                        border: `1px solid ${AMBER}20`,
                      }}
                    >
                      <Sparkles className="w-5 h-5" style={{ color: AMBER }} />
                    </div>
                    <p
                      className="text-[11px] text-center text-[var(--terminal-text-muted)] mb-1"
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}
                    >
                      No suggestions yet
                    </p>
                    <p
                      className="text-[10px] text-center text-[var(--terminal-text-dim)] max-w-[180px]"
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}
                    >
                      Ask a question to get AI-powered follow-up ideas
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'citations' && <CitationsTabContent />}

          {activeTab === 'settings' && (
            <div className="space-y-4">
              <div>
                <label
                  className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  Model
                </label>
                <div className="mt-2 p-3 rounded-lg bg-[var(--terminal-surface)] border border-[var(--terminal-border)]">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-[var(--phosphor-green)]" />
                    <span
                      className="text-xs text-[var(--terminal-text)]"
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}
                    >
                      GPT-4O-MINI
                    </span>
                  </div>
                </div>
              </div>

              <p
                className="text-[10px] text-[var(--terminal-text-dim)] mt-2"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                Use the model selector in the chat input to change models.
                Temperature and token limits are configured per-model.
              </p>
            </div>
          )}
        </div>
      </motion.aside>
    </AnimatePresence>
  );
}

// ============================================
// MAIN LAYOUT
// ============================================

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [contextPanelOpen, setContextPanelOpen] = useState(false);

  // Workspace and project state
  const [workspaces, setWorkspaces] = useState<WorkspaceType[]>([]);
  const [currentWorkspaceId, setCurrentWorkspaceId] = useState<string | null>(
    null
  );
  const [projects, setProjects] = useState<WorkspaceCollection[]>([]);
  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = useState(true);
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);

  // Fetch workspaces on mount
  useEffect(() => {
    async function fetchWorkspaces() {
      setIsLoadingWorkspaces(true);
      try {
        const fetchedWorkspaces = await workspaceService.listWorkspaces();

        // Sort workspaces: prioritize ones with collections, then by most recent
        const sortedWorkspaces = [...fetchedWorkspaces].sort((a, b) => {
          // First prioritize workspaces with collections
          const aHasCollections = (a.collection_count ?? 0) > 0;
          const bHasCollections = (b.collection_count ?? 0) > 0;
          if (aHasCollections && !bHasCollections) return -1;
          if (!aHasCollections && bHasCollections) return 1;
          // Then sort by collection count
          if ((a.collection_count ?? 0) !== (b.collection_count ?? 0)) {
            return (b.collection_count ?? 0) - (a.collection_count ?? 0);
          }
          // Finally by updated_at (most recent first)
          return (
            new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
          );
        });

        setWorkspaces(sortedWorkspaces);

        // Set first workspace with collections as current, or just first available
        if (sortedWorkspaces.length > 0 && !currentWorkspaceId) {
          const workspaceWithProjects = sortedWorkspaces.find(
            (w) => (w.collection_count ?? 0) > 0
          );
          setCurrentWorkspaceId(
            workspaceWithProjects?.id || sortedWorkspaces[0].id
          );
        }
      } catch (error) {
        console.error('[ChatLayout] Failed to fetch workspaces:', error);
      } finally {
        setIsLoadingWorkspaces(false);
      }
    }
    fetchWorkspaces();
  }, []);

  // Fetch projects when workspace changes
  useEffect(() => {
    async function fetchProjects() {
      if (!currentWorkspaceId) {
        setProjects([]);
        return;
      }

      setIsLoadingProjects(true);
      try {
        const response =
          await workspaceService.listCollections(currentWorkspaceId);
        setProjects(response.collections || []);
      } catch (error) {
        console.error('[ChatLayout] Failed to fetch projects:', error);
        setProjects([]);
      } finally {
        setIsLoadingProjects(false);
      }
    }
    fetchProjects();
  }, [currentWorkspaceId]);

  // Handle workspace change
  const handleWorkspaceChange = useCallback((workspaceId: string) => {
    setCurrentWorkspaceId(workspaceId);
  }, []);

  // Global keyboard shortcut for command palette
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="h-screen flex flex-col star-field terminal-grid noise-texture overflow-hidden">
      {/* Main Layout */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Main Content */}
        <main className="flex-1 flex flex-col overflow-hidden">{children}</main>

        {/* Context Panel Toggle Button - only show when panel is closed */}
        {!contextPanelOpen && (
          <button
            onClick={() => setContextPanelOpen(true)}
            className="hidden xl:flex absolute right-4 top-4 z-10 items-center gap-2 px-3 py-2 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] hover:border-[var(--phosphor-green)]/30 hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] transition-all"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
            title="Open context panel"
          >
            <FileText className="w-4 h-4" />
            <span className="text-[10px] uppercase tracking-wider">
              Context
            </span>
          </button>
        )}

        {/* Right Context Panel */}
        <ContextPanel
          isOpen={contextPanelOpen}
          onClose={() => setContextPanelOpen(false)}
        />
      </div>

      {/* Command Palette */}
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        onExecute={(id) => {
          switch (id) {
            case 'new-chat':
              router.push('/chat/new');
              break;
            case 'search':
              router.push('/search');
              break;
            case 'arxiv':
              router.push('/arxiv');
              break;
            case 'dashboard':
              router.push('/dashboard');
              break;
            case 'entities':
              router.push('/entities');
              break;
          }
        }}
      />
    </div>
  );
}
