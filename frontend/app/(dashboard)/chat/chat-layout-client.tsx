'use client';

import { ArtifactPanel } from '@/components/chat/artifact-panel/ArtifactPanel';
import { ContextRail } from '@/components/context-rail';
import type { WorkingFoldersSelection } from '@/components/context-rail/WorkingFoldersPanel';
import { useChatPersistence } from '@/hooks';
import { cn } from '@/lib/utils';
import { useArtifactPanelStore } from '@/store/artifactPanelStore';
import {
  resolveBoundProjectId,
  selectCurrentThreadProjectId,
  useChatStore,
} from '@/store/chat-store';
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

  // Reset on open via the "adjust state when a prop changes" pattern rather
  // than in an effect: setState inside an effect triggers a second render pass
  // (react-hooks/set-state-in-effect). Pre-existing, fixed here because the
  // changed-file ratchet requires touched files to be error-clean.
  const [wasOpen, setWasOpen] = useState(isOpen);
  if (isOpen !== wasOpen) {
    setWasOpen(isOpen);
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
    }
  }

  // Focus is a DOM side effect, so it stays in an effect.
  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
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
        <div className="absolute inset-0 bg-(--nous-erebus)/50" />

        {/* Palette */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: -20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -20 }}
          transition={{ duration: 0.15, ease: 'easeOut' }}
          onClick={(e) => e.stopPropagation()}
          className="relative w-full max-w-2xl overflow-hidden rounded-(--nous-radius-lg) border border-(--nous-border-1) bg-(--nous-bg-2) shadow-(--nous-shadow-lg)"
        >
          {/* Search Input */}
          <div className="flex items-center gap-3 px-4 py-4 border-b border-(--nous-border-1)">
            <Search className="w-5 h-5 text-(--nous-sol)" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 bg-transparent text-(--nous-fg-1) text-sm outline-hidden"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            />
            <kbd
              className="px-2 py-1 rounded bg-(--nous-border-1) text-[10px] text-(--nous-fg-3)"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              ESC
            </kbd>
          </div>

          {/* Results */}
          <div className="max-h-[60vh] overflow-y-auto nous-scrollbar p-2">
            {Object.entries(groupedCommands).map(([category, cmds]) => (
              <div key={category} className="mb-4">
                <div
                  className="px-3 py-2 text-[10px] text-(--nous-fg-3) uppercase tracking-wider"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
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
                          ? 'bg-(--nous-sol)/10 border border-(--nous-sol)/30'
                          : 'hover:bg-(--nous-bg-3)'
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
                            ? 'text-(--nous-sol)'
                            : 'text-(--nous-fg-3)'
                        )}
                      />
                      <span
                        className={cn(
                          'flex-1 text-left text-sm',
                          globalIdx === selectedIndex
                            ? 'text-(--nous-sol)'
                            : 'text-(--nous-fg-1)'
                        )}
                        style={{ fontFamily: 'var(--nous-font-ui)' }}
                      >
                        {cmd.label}
                      </span>
                      {cmd.shortcut && (
                        <kbd
                          className="px-1.5 py-0.5 rounded bg-(--nous-border-1) text-[10px] text-(--nous-fg-3)"
                          style={{ fontFamily: 'var(--nous-font-ui)' }}
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
                <Search className="w-8 h-8 text-(--nous-border-1) mx-auto mb-2" />
                <p
                  className="text-sm text-(--nous-fg-3)"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                >
                  No results found
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-(--nous-border-1) bg-(--nous-bg-2)">
            <div
              className="flex items-center gap-4 text-[10px] text-(--nous-fg-3)"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              <span className="flex items-center gap-1">
                <kbd className="px-1 rounded bg-(--nous-border-1)">↑↓</kbd>{' '}
                Navigate
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1 rounded bg-(--nous-border-1)">↵</kbd>{' '}
                Select
              </span>
            </div>
            <span
              className="text-[10px] text-(--nous-fg-3)"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
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
  const { currentThreadId, currentWorkspaceId } = useChatPersistence();
  // The binding's source of truth is the thread row (source_project_id) —
  // the ?projectId= param is only the initial intent and is dropped by
  // thread navigation (getSelectedThreadUrl builds /chat?thread=… with no
  // other params), so deriving from it alone made the rail "forget" the
  // project on every thread switch. Sentinel semantics documented on
  // selectCurrentThreadProjectId.
  const threadProjectId = useChatStore(selectCurrentThreadProjectId);
  const projectId = resolveBoundProjectId(
    threadProjectId,
    searchParams.get('projectId')
  );
  const projectStoreProjects = useProjectStore((s) => s.projects);
  const currentProject = useProjectStore((s) => s.currentProject);
  const fetchProject = useProjectStore((s) => s.fetchProject);
  const resolvedProjectName = projectId
    ? currentProject?.id === projectId
      ? currentProject.name
      : (projectStoreProjects.find((p) => p.id === projectId)?.name ?? null)
    : null;
  const storeWorkspaces = useChatStore((s) => s.workspaces);
  const workspaceName = isAuthenticated
    ? (storeWorkspaces.find((w) => w.id === currentWorkspaceId)?.name ?? null)
    : null;
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  // Split-view artifact panel: when open it takes over the rail's slot, and
  // the rail becomes a button-toggled overlay (Codex-style) so its content
  // stays reachable without a third permanent column.
  const artifact = useArtifactPanelStore((s) => s.artifact);
  const isArtifactPanelOpen = useArtifactPanelStore((s) => s.isOpen);
  const openArtifact = useArtifactPanelStore((s) => s.openArtifact);
  const [railOverlayOpen, setRailOverlayOpen] = useState(false);
  // The overlay only exists while the panel is docked; reset on panel close
  // so reopening the panel starts without a stale overlay.
  const showArtifactPanel = isArtifactPanelOpen && artifact !== null;
  const [panelWasOpen, setPanelWasOpen] = useState(showArtifactPanel);
  if (showArtifactPanel !== panelWasOpen) {
    setPanelWasOpen(showArtifactPanel);
    if (!showArtifactPanel) setRailOverlayOpen(false);
  }

  useEffect(() => {
    if (projectId && !resolvedProjectName) {
      fetchProject(projectId);
    }
  }, [projectId, resolvedProjectName, fetchProject]);

  const handleProjectBound = useCallback(
    (boundProjectId: string) => {
      // Mirror into the store thread so the rail updates immediately and the
      // binding survives in-session thread switches (the server row, written
      // before this callback fires, covers reloads). Read the thread id live:
      // the picker popover can stay open across a thread switch, and a
      // closure-captured id would bind the wrong thread.
      const liveThreadId = useChatStore.getState().currentThreadId;
      if (liveThreadId) {
        useChatStore
          .getState()
          .setThreadProjectBinding(liveThreadId, boundProjectId);
      }
      const params = new URLSearchParams(searchParams.toString());
      params.set('projectId', boundProjectId);
      router.replace(`/chat?${params.toString()}`);
    },
    [router, searchParams]
  );

  // Rail file-tree selections: documents/external sources open in the
  // artifact panel beside the chat (the split-view pattern — never navigate
  // away). Note/draft detail routes don't exist yet, so those still fall back
  // to the project page until the panel learns to render them.
  const handleRailSelect = useCallback(
    (node: WorkingFoldersSelection) => {
      if ((node.kind === 'note' || node.kind === 'draft') && projectId) {
        router.push(`/projects/${projectId}`);
        return;
      }
      if (node.kind === 'document' || node.kind === 'external') {
        openArtifact(
          node.kind === 'document'
            ? { kind: 'document', id: node.id, title: node.title }
            : {
                kind: 'external',
                id: node.id,
                title: node.title,
                ...(node.source ? { source: node.source } : {}),
              }
        );
      }
    },
    [projectId, router, openArtifact]
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

  // h-full, not h-screen: the parent shell is h-svh (SidebarLayout), and
  // h-screen is 100vh — the LARGE viewport. On a phone with the URL bar
  // showing, 100vh exceeds 100svh, so this column overflowed its scroll parent
  // and the composer's action row fell below the fold.
  return (
    <div className="h-full flex flex-col bg-(--nous-bg-1) overflow-hidden">
      {/* Main Layout */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Main Content */}
        <main className="flex-1 flex flex-col overflow-hidden">{children}</main>

        {/* Right slot: the docked ContextRail, or — when an artifact is in
            focus — the ArtifactPanel, with the rail demoted to a
            button-toggled overlay so its content stays reachable. */}
        {isAuthenticated && (
          <>
            {!showArtifactPanel && (
              <ContextRail
                threadId={currentThreadId ?? null}
                workspaceName={workspaceName}
                workspaceId={currentWorkspaceId ?? undefined}
                ragEnabled={true}
                projectId={projectId}
                projectName={resolvedProjectName}
                onProjectBound={handleProjectBound}
                onSelect={handleRailSelect}
                className="hidden lg:flex shrink-0 w-[320px] border-l border-(--nous-border-1)"
              />
            )}
            {showArtifactPanel && (
              <>
                <ArtifactPanel
                  artifact={artifact}
                  onToggleRail={() => setRailOverlayOpen((o) => !o)}
                  railOpen={railOverlayOpen}
                />
                {railOverlayOpen && (
                  <>
                    {/* Click-away layer for the rail overlay. */}
                    <div
                      className="absolute inset-0 z-30 hidden lg:block"
                      aria-hidden="true"
                      onClick={() => setRailOverlayOpen(false)}
                    />
                    <ContextRail
                      threadId={currentThreadId ?? null}
                      workspaceName={workspaceName}
                      workspaceId={currentWorkspaceId ?? undefined}
                      ragEnabled={true}
                      projectId={projectId}
                      projectName={resolvedProjectName}
                      onProjectBound={handleProjectBound}
                      onSelect={(node) => {
                        setRailOverlayOpen(false);
                        handleRailSelect(node);
                      }}
                      className="absolute right-2 top-2 bottom-2 z-40 hidden lg:flex w-[340px] rounded-(--nous-radius-lg) border border-(--nous-border-1) bg-(--nous-bg-1) shadow-(--nous-shadow-lg)"
                    />
                  </>
                )}
              </>
            )}
          </>
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
