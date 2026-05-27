'use client';

import { ContextRail } from '@/components/context-rail';
import { useChatPersistence } from '@/hooks';
import { cn } from '@/lib/utils';
import { useChatStore } from '@/store/chat-store';
import { useProjectStore } from '@/store/projectStore';
import { useAuthStore } from '@/stores/authStore';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  BookOpen,
  FileText,
  FolderOpen,
  Plus,
  Search,
  Settings,
  Share2,
} from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

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

  const commands = useMemo(
    () => [
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
    ],
    []
  );

  const filteredCommands = useMemo(
    () =>
      commands.filter((cmd) =>
        cmd.label.toLowerCase().includes(query.toLowerCase())
      ),
    [commands, query]
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

  // Memoize grouped commands and build index lookup to avoid indexOf per item
  const { groupedCommands, commandIndexMap } = useMemo(() => {
    const grouped = filteredCommands.reduce(
      (acc, cmd) => {
        if (!acc[cmd.category]) acc[cmd.category] = [];
        acc[cmd.category].push(cmd);
        return acc;
      },
      {} as Record<string, typeof commands>
    );
    const indexMap = new Map<string, number>();
    filteredCommands.forEach((cmd, i) => indexMap.set(cmd.id, i));
    return { groupedCommands: grouped, commandIndexMap: indexMap };
  }, [filteredCommands]);

  if (!isOpen) return null;

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
                {cmds.map((cmd) => {
                  const globalIdx = commandIndexMap.get(cmd.id) ?? -1;
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
// MAIN LAYOUT
// ============================================

function ChatLayoutContent({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const projectId = searchParams.get('projectId') ?? undefined;
  const projectStoreProjects = useProjectStore((s) => s.projects);
  const currentProject = useProjectStore((s) => s.currentProject);
  const fetchProject = useProjectStore((s) => s.fetchProject);
  const resolvedProjectName = projectId
    ? currentProject?.id === projectId
      ? currentProject.name
      : (projectStoreProjects.find((p) => p.id === projectId)?.name ?? null)
    : null;
  const { currentThreadId, currentWorkspaceId } = useChatPersistence();
  const storeWorkspaces = useChatStore((s) => s.workspaces);
  const workspaceName = isAuthenticated
    ? (storeWorkspaces.find((w) => w.id === currentWorkspaceId)?.name ?? null)
    : null;
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  useEffect(() => {
    if (projectId && !resolvedProjectName) {
      fetchProject(projectId);
    }
  }, [projectId, resolvedProjectName, fetchProject]);

  const handleProjectBound = useCallback(
    (boundProjectId: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set('projectId', boundProjectId);
      router.replace(`/chat?${params.toString()}`);
    },
    [router, searchParams]
  );

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

        {/* Right-rail: stacked Agent Activity, Related Results, Citations */}
        {isAuthenticated && (
          <ContextRail
            threadId={currentThreadId ?? null}
            workspaceName={workspaceName}
            workspaceId={currentWorkspaceId ?? undefined}
            ragEnabled={true}
            projectId={projectId}
            projectName={resolvedProjectName}
            onProjectBound={handleProjectBound}
            onSelect={(node) => {
              // Per design + Task 1 verification: note/draft detail routes don't
              // exist yet, so navigate to the project page as a stable fallback.
              // Document previews (kind: 'document' | 'external') are still a
              // follow-up wiring through the chat page's CitationPanel state.
              if (
                (node.kind === 'note' || node.kind === 'draft') &&
                projectId
              ) {
                router.push(`/projects/${projectId}`);
                return;
              }
              // TODO(follow-up): open CitationPanel with a synthetic citation
              // for kind === 'document' | 'external'.
              console.log('[ContextRail] preview', node);
            }}
            className="hidden lg:flex shrink-0 w-[320px] border-l border-[var(--nous-border-1)]"
          />
        )}
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

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Suspense>
      <ChatLayoutContent>{children}</ChatLayoutContent>
    </Suspense>
  );
}
