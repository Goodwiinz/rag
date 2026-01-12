'use client';

import {
    Breadcrumb,
    BreadcrumbItem,
    BreadcrumbLink,
    BreadcrumbList,
    BreadcrumbPage,
    BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import { Separator } from '@/components/ui/separator';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { UIConversation, useChatPersistence } from '@/hooks';
import { extractCitationIndices } from '@/utils/citationParser';
import { cn } from '@/lib/utils';
import { AnimatePresence, motion } from 'framer-motion';
import {
    Activity,
    BookOpen,
    ChevronDown,
    ChevronRight,
    Clock,
    Cpu,
    Download,
    FileText,
    FolderOpen,
    Loader2,
    Menu,
    MessageSquare,
    MoreVertical,
    Pin,
    Plus,
    Search,
    Settings,
    Share2,
    Sparkles,
    Sun,
    Trash2,
    Users,
    X
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ExportDialog } from '@/components/export';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// ============================================
// TYPES
// ============================================

interface Conversation {
  id: string;
  title: string;
  preview: string;
  timestamp: Date;
  isPinned?: boolean;
  modelId?: string;
  messageCount: number;
  isShared?: boolean;
  sharedBy?: string;
}

interface Collection {
  id: string;
  name: string;
  icon: string;
  count: number;
}

interface Workspace {
  id: string;
  name: string;
  isActive: boolean;
}

// ============================================
// COMMAND PALETTE
// ============================================

function CommandPalette({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands = [
    { id: 'new-chat', label: 'New Chat', icon: Plus, shortcut: '⌘N', category: 'actions' },
    { id: 'upload', label: 'Upload Document', icon: FileText, shortcut: '⌘U', category: 'actions' },
    { id: 'search', label: 'Search Documents', icon: Search, shortcut: '⌘/', category: 'actions' },
    { id: 'collection', label: 'Create Collection', icon: FolderOpen, shortcut: '⌘G', category: 'actions' },
    { id: 'settings', label: 'Open Settings', icon: Settings, shortcut: '⌘,', category: 'actions' },
    { id: 'arxiv', label: 'Browse ArXiv Papers', icon: BookOpen, category: 'navigate' },
    { id: 'dashboard', label: 'Go to Dashboard', icon: Activity, category: 'navigate' },
    { id: 'entities', label: 'Knowledge Graph', icon: Share2, category: 'navigate' },
  ];

  const filteredCommands = commands.filter(
    (cmd) => cmd.label.toLowerCase().includes(query.toLowerCase())
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
        // Execute command
        onClose();
      } else if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, filteredCommands, selectedIndex, onClose]);

  if (!isOpen) return null;

  const groupedCommands = filteredCommands.reduce((acc, cmd) => {
    if (!acc[cmd.category]) acc[cmd.category] = [];
    acc[cmd.category].push(cmd);
    return acc;
  }, {} as Record<string, typeof commands>);

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
            <kbd className="px-2 py-1 rounded bg-[var(--terminal-border)] text-[10px] text-[var(--terminal-text-dim)]"
                 style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              ESC
            </kbd>
          </div>

          {/* Results */}
          <div className="max-h-[60vh] overflow-y-auto terminal-scrollbar p-2">
            {Object.entries(groupedCommands).map(([category, cmds]) => (
              <div key={category} className="mb-4">
                <div className="px-3 py-2 text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider"
                     style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  {category === 'actions' ? '⚡ Quick Actions' : '🔗 Navigate'}
                </div>
                {cmds.map((cmd, idx) => {
                  const globalIdx = filteredCommands.indexOf(cmd);
                  return (
                    <button
                      key={cmd.id}
                      className={cn(
                        "w-full flex items-center gap-3 px-3 py-3 rounded transition-all",
                        globalIdx === selectedIndex
                          ? "bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/30"
                          : "hover:bg-[var(--terminal-elevated)]"
                      )}
                      onClick={onClose}
                    >
                      <cmd.icon className={cn(
                        "w-4 h-4",
                        globalIdx === selectedIndex ? "text-[var(--phosphor-green)]" : "text-[var(--terminal-text-dim)]"
                      )} />
                      <span className={cn(
                        "flex-1 text-left text-sm",
                        globalIdx === selectedIndex ? "text-[var(--phosphor-green)]" : "text-[var(--terminal-text)]"
                      )} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                        {cmd.label}
                      </span>
                      {cmd.shortcut && (
                        <kbd className="px-1.5 py-0.5 rounded bg-[var(--terminal-border)] text-[10px] text-[var(--terminal-text-muted)]"
                             style={{ fontFamily: "'JetBrains Mono', monospace" }}>
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
                <p className="text-sm text-[var(--terminal-text-muted)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  No results found
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
            <div className="flex items-center gap-4 text-[10px] text-[var(--terminal-text-muted)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              <span className="flex items-center gap-1">
                <kbd className="px-1 rounded bg-[var(--terminal-border)]">↑↓</kbd> Navigate
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1 rounded bg-[var(--terminal-border)]">↵</kbd> Select
              </span>
            </div>
            <span className="text-[10px] text-[var(--terminal-text-muted)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              {filteredCommands.length} results
            </span>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// ============================================
// WORKSPACE BAR (TOP)
// ============================================

function WorkspaceBar({
  onCommandPalette,
  onToggleSidebar,
}: {
  onCommandPalette: () => void;
  onToggleSidebar: () => void;
}) {
  const [currentTime, setCurrentTime] = useState<Date | null>(null);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);

  const workspaces: Workspace[] = [
    { id: '1', name: 'AI Research Lab', isActive: true },
    { id: '2', name: 'Academic Projects', isActive: false },
    { id: '3', name: 'Personal', isActive: false },
  ];

  useEffect(() => {
    setCurrentTime(new Date());
    const interval = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="relative z-20 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/95 backdrop-blur-xl">
      <div className="flex items-center justify-between px-4 py-2.5">
        {/* Left: Logo & Workspace */}
        <div className="flex items-center gap-4">
          <button
            onClick={onToggleSidebar}
            className="p-2 rounded hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] transition-colors lg:hidden"
          >
            <Menu className="w-5 h-5" />
          </button>

          {/* Breadcrumb Bar */}
          <div className="hidden md:flex items-center gap-2">
            <SidebarTrigger className="h-7 w-7 text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)]" />
            <Separator orientation="vertical" className="h-4 bg-[var(--terminal-border)]" />
            <Breadcrumb>
              <BreadcrumbList className="font-mono text-xs">
                <BreadcrumbItem>
                  <BreadcrumbLink
                    href="/dashboard"
                    className="text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] transition-colors"
                  >
                    Dashboard
                  </BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="text-[var(--terminal-text-dim)]">/</BreadcrumbSeparator>
                <BreadcrumbItem>
                  <BreadcrumbPage className="text-[var(--phosphor-green)]">
                    Chat
                  </BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>



          {/* Workspace Picker */}
          <div className="relative hidden md:block">
            <button
              onClick={() => setWorkspaceOpen(!workspaceOpen)}
              className="flex items-center gap-2 px-3 py-1.5 rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] hover:border-[var(--phosphor-green)]/30 transition-colors"
            >
              <Users className="w-3.5 h-3.5 text-[var(--phosphor-green)]" />
              <span className="text-xs text-[var(--terminal-text)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                AI Research Lab
              </span>
              <ChevronDown className={cn(
                "w-3 h-3 text-[var(--terminal-text-muted)] transition-transform",
                workspaceOpen && "rotate-180"
              )} />
            </button>

            <AnimatePresence>
              {workspaceOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="absolute top-full left-0 mt-2 w-56 terminal-window z-50"
                >
                  <div className="p-2">
                    {workspaces.map((ws) => (
                      <button
                        key={ws.id}
                        onClick={() => setWorkspaceOpen(false)}
                        className={cn(
                          "w-full flex items-center gap-3 px-3 py-2 rounded text-left transition-colors",
                          ws.isActive
                            ? "bg-[var(--phosphor-green)]/10 text-[var(--phosphor-green)]"
                            : "hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text)]"
                        )}
                      >
                        <Users className="w-4 h-4" />
                        <span className="text-xs" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                          {ws.name}
                        </span>
                        {ws.isActive && (
                          <div className="ml-auto w-1.5 h-1.5 rounded-full bg-[var(--phosphor-green)]" />
                        )}
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Center: Command Palette Trigger */}
        <button
          onClick={onCommandPalette}
          className="hidden sm:flex items-center gap-3 px-4 py-2 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] hover:border-[var(--phosphor-green)]/30 hover:bg-[var(--terminal-elevated)] transition-all group"
        >
          <Search className="w-4 h-4 text-[var(--terminal-text-muted)] group-hover:text-[var(--phosphor-green)]" />
          <span className="text-xs text-[var(--terminal-text-muted)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            Search or command...
          </span>
          <kbd className="px-1.5 py-0.5 rounded bg-[var(--terminal-border)] text-[10px] text-[var(--terminal-text-muted)]"
               style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            ⌘K
          </kbd>
        </button>

        {/* Right: Status & User */}
        <div className="flex items-center gap-3">
          {/* Connection Status */}
          <div className="hidden md:flex items-center gap-2 px-2.5 py-1.5 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)]">
            <div className="w-1.5 h-1.5 rounded-full bg-[var(--phosphor-green)] signal-active" />
            <span className="text-[10px] text-[var(--terminal-text-dim)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              CONNECTED
            </span>
          </div>

          {/* Time */}
          <div className="hidden lg:block text-[10px] text-[var(--terminal-text-muted)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            <span className="text-[var(--terminal-text-dim)]">UTC </span>
            <span className="text-[var(--phosphor-green)]">
              {currentTime?.toISOString().split('T')[1]?.split('.')[0] || '--:--:--'}
            </span>
          </div>

          {/* Theme Toggle */}
          <button className="p-2 rounded hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--amber-gold)] transition-colors">
            <Sun className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}

// ============================================
// CONVERSATION SIDEBAR (LEFT)
// ============================================

function ConversationSidebar({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    pinned: true,
    recent: true,
    collections: true,
  });
  const [isCreatingChat, setIsCreatingChat] = useState(false);

  const router = useRouter();

  // Get real conversations from chat store
  const { conversations: uiConversations, isLoading, isInitialized, currentThreadId, currentConversationId, selectConversation, createNewChat } = useChatPersistence();

  // Only show loading spinner when actively initializing (not just when empty)
  const showLoading = isLoading && !isInitialized;

  // Map UI conversations to the sidebar format
  const conversations: Conversation[] = useMemo(() => {
    return uiConversations.map((conv: UIConversation) => ({
      id: conv.threadId,
      title: conv.title || 'New Chat',
      preview: conv.messages.length > 0
        ? conv.messages[conv.messages.length - 1].content.substring(0, 50) + '...'
        : 'No messages yet',
      timestamp: new Date(conv.updatedAt),
      isPinned: conv.isBookmarked || false,
      messageCount: conv.messages.length,
    }));
  }, [uiConversations]);

  // Collections remain as placeholder for now (can be extended later)
  const collections: Collection[] = [];

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const pinnedConversations = conversations.filter((c) => c.isPinned);
  const recentConversations = conversations.filter((c) => !c.isPinned);

  // Filter conversations based on search
  const filteredConversations = searchQuery
    ? recentConversations.filter(c =>
        c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.preview.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : recentConversations;

  const sidebarContent = (
    <div className="h-full flex flex-col bg-[var(--terminal-bg)]">
      {/* New Chat Button - More prominent */}
      <div className="p-4 pb-3">
        <button
          disabled={isCreatingChat}
          onClick={async () => {
            setIsCreatingChat(true);
            try {
              const threadId = await createNewChat();
              if (threadId) {
                router.push(`/chat?thread=${threadId}`);
              } else {
                console.error('[Sidebar] Failed to create new chat - no threadId returned');
              }
            } catch (error) {
              console.error('[Sidebar] Error creating new chat:', error);
            } finally {
              setIsCreatingChat(false);
            }
          }}
          className="flex items-center justify-center gap-2 w-full px-4 py-3 rounded-xl bg-[var(--phosphor-green)] text-[var(--terminal-bg)] text-xs font-medium hover:shadow-[0_0_25px_var(--phosphor-green-glow)] hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {isCreatingChat ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Plus className="w-4 h-4" />
          )}
          {isCreatingChat ? 'CREATING...' : 'NEW CHAT'}
        </button>
      </div>

      {/* Search - Cleaner design */}
      <div className="px-4 pb-3">
        <div className="relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--terminal-text-muted)] group-focus-within:text-[var(--phosphor-green)] transition-colors" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-[var(--terminal-surface)] border border-[var(--terminal-border)] text-xs text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)] outline-none focus:border-[var(--phosphor-green)]/40 focus:bg-[var(--terminal-elevated)] transition-all"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)] transition-colors"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto terminal-scrollbar px-2">
        {/* Pinned Section */}
        {pinnedConversations.length > 0 && (
          <div className="mb-2">
            <button
              onClick={() => toggleSection('pinned')}
              className="flex items-center gap-2 w-full px-3 py-2 text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <Pin className="w-3 h-3" />
              <span>Pinned</span>
              <span className="ml-auto text-[var(--terminal-text-dim)]">{pinnedConversations.length}</span>
              <ChevronRight className={cn(
                "w-3 h-3 transition-transform duration-200",
                expandedSections.pinned && "rotate-90"
              )} />
            </button>
            <AnimatePresence>
              {expandedSections.pinned && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="space-y-1"
                >
                  {pinnedConversations.map((conv) => (
                    <ConversationItem key={conv.id} conversation={conv} isActive={currentThreadId === conv.id || pathname === `/chat/${conv.id}`} onSelect={selectConversation} />
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Recent Section */}
        <div className="mb-2">
          <button
            onClick={() => toggleSection('recent')}
            className="flex items-center gap-2 w-full px-3 py-2 text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            <Clock className="w-3 h-3" />
            <span>{searchQuery ? 'Results' : 'Recent'}</span>
            {showLoading ? (
              <Loader2 className="w-3 h-3 ml-1 animate-spin" />
            ) : (
              <span className="ml-auto text-[var(--terminal-text-dim)]">{filteredConversations.length}</span>
            )}
            <ChevronRight className={cn(
              "w-3 h-3 transition-transform duration-200",
              expandedSections.recent && "rotate-90"
            )} />
          </button>
          <AnimatePresence>
            {expandedSections.recent && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="space-y-1"
              >
                {showLoading ? (
                  <div className="flex flex-col items-center justify-center py-8">
                    <Loader2 className="w-5 h-5 animate-spin text-[var(--phosphor-green)] mb-2" />
                    <p className="text-[10px] text-[var(--terminal-text-muted)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      Loading conversations...
                    </p>
                  </div>
                ) : filteredConversations.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-8 px-4">
                    <div className="w-10 h-10 rounded-full bg-[var(--terminal-surface)] flex items-center justify-center mb-3">
                      <MessageSquare className="w-5 h-5 text-[var(--terminal-text-muted)]" />
                    </div>
                    <p className="text-xs text-[var(--terminal-text-muted)] text-center" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {searchQuery ? 'No matching conversations' : 'Start a new conversation'}
                    </p>
                  </div>
                ) : (
                  filteredConversations.map((conv, index) => (
                    <motion.div
                      key={conv.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.02 }}
                    >
                      <ConversationItem conversation={conv} isActive={currentThreadId === conv.id || pathname === `/chat/${conv.id}`} onSelect={selectConversation} />
                    </motion.div>
                  ))
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Collections Section */}
        <div className="border-t border-[var(--terminal-border)] pt-2 mt-2">
          <button
            onClick={() => toggleSection('collections')}
            className="flex items-center gap-2 w-full px-3 py-2 text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            <FolderOpen className="w-3 h-3" />
            <span>Collections</span>
            <span className="ml-auto text-[var(--terminal-text-dim)]">{collections.length}</span>
            <ChevronRight className={cn(
              "w-3 h-3 transition-transform duration-200",
              expandedSections.collections && "rotate-90"
            )} />
          </button>
          <AnimatePresence>
            {expandedSections.collections && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="space-y-1"
              >
                {collections.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-6 px-4">
                    <p className="text-[10px] text-[var(--terminal-text-muted)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      No collections yet
                    </p>
                  </div>
                ) : (
                  collections.map((collection) => (
                    <button
                      key={collection.id}
                      className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-left hover:bg-[var(--terminal-elevated)] transition-colors"
                    >
                      <span>{collection.icon}</span>
                      <span className="flex-1 text-xs text-[var(--terminal-text)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                        {collection.name}
                      </span>
                      <span className="text-[10px] text-[var(--terminal-text-muted)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                        {collection.count}
                      </span>
                    </button>
                  ))
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Footer - Settings */}
      <div className="p-3 border-t border-[var(--terminal-border)]">
        <Link
          href="/settings"
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs text-[var(--terminal-text-dim)] hover:bg-[var(--terminal-elevated)] hover:text-[var(--phosphor-green)] transition-all group"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <Settings className="w-4 h-4 group-hover:rotate-90 transition-transform duration-300" />
          Settings
        </Link>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside className="hidden lg:block w-72 border-r border-[var(--terminal-border)] flex-shrink-0">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer */}
      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/50 z-40 lg:hidden"
              onClick={onClose}
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              className="fixed left-0 top-0 bottom-0 w-72 z-50 lg:hidden"
            >
              <button
                onClick={onClose}
                className="absolute top-3 right-3 p-2 rounded-lg hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)]"
              >
                <X className="w-4 h-4" />
              </button>
              {sidebarContent}
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

// Helper function for relative time
function getRelativeTime(timestamp: number): string {
  const now = Date.now();
  const diff = now - timestamp;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m`;
  if (hours < 24) return `${hours}h`;
  if (days < 7) return `${days}d`;
  return new Date(timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function ConversationItem({
  conversation,
  isActive,
  onSelect,
}: {
  conversation: Conversation;
  isActive: boolean;
  onSelect?: (id: string) => void;
}) {
  const messageCount = conversation.messageCount || 0;
  const relativeTime = getRelativeTime(conversation.timestamp.getTime());
  const router = useRouter();
  const [exportDialogOpen, setExportDialogOpen] = useState(false);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    // Update Zustand store first, then navigate
    if (onSelect) {
      onSelect(conversation.id);
    }
    router.push(`/chat?thread=${conversation.id}`);
  };

  return (
    <>
      <div
        className={cn(
          "block px-3 py-3 rounded-xl transition-all group relative cursor-pointer",
          isActive
            ? "bg-[var(--phosphor-green)]/10"
            : "hover:bg-[var(--terminal-elevated)]"
        )}
      >
        {/* Active indicator */}
        {isActive && (
          <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 rounded-r-full bg-[var(--phosphor-green)]" />
        )}

        <div className="flex items-start gap-3">
          <a
            href={`/chat?thread=${conversation.id}`}
            onClick={handleClick}
            className={cn(
              "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors",
              isActive
                ? "bg-[var(--phosphor-green)]/20"
                : "bg-[var(--terminal-surface)] group-hover:bg-[var(--terminal-elevated)]"
            )}
          >
            <MessageSquare className={cn(
              "w-4 h-4",
              isActive ? "text-[var(--phosphor-green)]" : "text-[var(--terminal-text-muted)]"
            )} />
          </a>

          <a
            href={`/chat?thread=${conversation.id}`}
            onClick={handleClick}
            className="flex-1 min-w-0"
          >
            {/* Title row with time */}
            <div className="flex items-center justify-between gap-2 mb-1">
              <p className={cn(
                "text-xs font-medium truncate",
                isActive ? "text-[var(--phosphor-green)]" : "text-[var(--terminal-text)]"
              )} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {conversation.title || 'New Chat'}
              </p>
              <span className="text-[9px] text-[var(--terminal-text-dim)] flex-shrink-0" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {relativeTime}
              </span>
            </div>

            {/* Preview and message count */}
            <div className="flex items-center gap-2">
              <p className="text-[10px] text-[var(--terminal-text-muted)] truncate flex-1"
                 style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {conversation.preview || 'No messages yet'}
              </p>
              {messageCount > 0 && (
                <span className="text-[9px] text-[var(--terminal-text-dim)] flex-shrink-0 px-1.5 py-0.5 rounded bg-[var(--terminal-surface)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  {messageCount}
                </span>
              )}
            </div>
          </a>

          {/* Actions Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="opacity-0 group-hover:opacity-100 p-1.5 rounded-md hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)] transition-all"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreVertical className="w-4 h-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="w-48 bg-[#141414] border-[#333] text-[#e4e4e7]"
            >
              <DropdownMenuItem
                onClick={(e) => {
                  e.stopPropagation();
                  setExportDialogOpen(true);
                }}
                className="text-xs cursor-pointer hover:bg-[#1a1a1a] hover:text-[#00ff9f]"
              >
                <Download className="w-4 h-4 mr-2" />
                Export Thread
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={(e) => e.stopPropagation()}
                className="text-xs cursor-pointer hover:bg-[#1a1a1a] hover:text-[#00ff9f]"
              >
                <Pin className="w-4 h-4 mr-2" />
                {conversation.isPinned ? 'Unpin' : 'Pin'}
              </DropdownMenuItem>
              <DropdownMenuSeparator className="bg-[#333]" />
              <DropdownMenuItem
                onClick={(e) => e.stopPropagation()}
                className="text-xs cursor-pointer hover:bg-[#1a1a1a] text-red-400 hover:text-red-300"
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Export Dialog */}
      <ExportDialog
        open={exportDialogOpen}
        onOpenChange={setExportDialogOpen}
        threadIds={[conversation.id]}
        threadTitle={conversation.title}
      />
    </>
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

    const currentConv = conversations.find(c => c.threadId === currentThreadId);
    if (!currentConv) return [];

    // Collect only citations that are actually referenced in assistant messages
    const allCitations: CitationItem[] = [];
    const seenIds = new Set<string>();

    currentConv.messages.forEach(msg => {
      if (msg.role === 'assistant' && msg.citations) {
        const msgCitations = msg.citations as CitationItem[];

        // Extract which citations are actually referenced in the text (e.g., [Doc 1], [Doc 3])
        const referencedIndices = extractCitationIndices(msg.content);

        // If AI used inline citations, filter to only referenced ones
        // Otherwise fall back to showing all (for responses without inline refs)
        const citationsToShow = referencedIndices.length > 0
          ? msgCitations.filter((_, idx) => referencedIndices.includes(idx + 1))
          : msgCitations;

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
          style={{ backgroundColor: `${PHOSPHOR_GREEN}10`, border: `1px solid ${PHOSPHOR_GREEN}20` }}
        >
          <BookOpen className="w-6 h-6" style={{ color: PHOSPHOR_GREEN }} />
        </div>
        <p
          className="text-xs text-center mb-2"
          style={{ color: 'var(--terminal-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}
        >
          No citations yet
        </p>
        <p
          className="text-[10px] text-center max-w-[200px]"
          style={{ color: 'var(--terminal-text-dim)', fontFamily: "'JetBrains Mono', monospace" }}
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
        style={{ color: `${PHOSPHOR_GREEN}80`, fontFamily: "'JetBrains Mono', monospace" }}
      >
        {citations.length} Source{citations.length !== 1 ? 's' : ''} Referenced
      </div>

      {citations.map((citation, idx) => {
        const isExternal = !citation.documentId;
        const scorePercent = citation.score ? Math.round(citation.score * 100) : 0;

        return (
          <div
            key={citation.id || idx}
            className="rounded-lg overflow-hidden transition-colors"
            style={{
              backgroundColor: '#0a0a0a',
              border: '1px solid #1a1a1a'
            }}
          >
            <div className="p-3">
              <div className="flex items-start gap-3">
                {/* Icon */}
                <div
                  className="w-7 h-7 rounded-md flex items-center justify-center shrink-0"
                  style={{
                    backgroundColor: isExternal ? `${AMBER}10` : `${PHOSPHOR_GREEN}10`,
                    border: `1px solid ${isExternal ? AMBER : PHOSPHOR_GREEN}20`
                  }}
                >
                  {isExternal ? (
                    <BookOpen className="w-3.5 h-3.5" style={{ color: AMBER }} />
                  ) : (
                    <FileText className="w-3.5 h-3.5" style={{ color: PHOSPHOR_GREEN }} />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <p
                    className="text-xs font-medium leading-tight line-clamp-2 mb-1"
                    style={{ color: isExternal ? AMBER : PHOSPHOR_GREEN, fontFamily: "'JetBrains Mono', monospace" }}
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
                          fontFamily: "'JetBrains Mono', monospace"
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
                          fontFamily: "'JetBrains Mono', monospace"
                        }}
                      >
                        External
                      </span>
                    )}
                    {scorePercent > 0 && (
                      <span
                        className="text-[9px] px-1.5 py-0.5 rounded ml-auto"
                        style={{
                          backgroundColor: scorePercent >= 70 ? 'rgba(34, 197, 94, 0.15)' : scorePercent >= 50 ? 'rgba(234, 179, 8, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                          color: scorePercent >= 70 ? '#22c55e' : scorePercent >= 50 ? '#eab308' : '#ef4444',
                          fontFamily: "'JetBrains Mono', monospace"
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
                  style={{ color: 'var(--terminal-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}
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

function ContextPanel() {
  const [activeTab, setActiveTab] = useState<'context' | 'citations' | 'settings'>('context');
  const { conversations, currentThreadId, messages } = useChatPersistence();
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const lastMessageIdRef = useRef<string | null>(null);

  // Get the most relevant document (highest score citation)
  const activeDocument = useMemo((): CitationItem | null => {
    if (!currentThreadId) return null;
    const currentConv = conversations.find(c => c.threadId === currentThreadId);
    if (!currentConv) return null;

    let highestScoreCitation: CitationItem | null = null;
    let highestScore = 0;

    currentConv.messages.forEach(msg => {
      if (msg.role === 'assistant' && msg.citations) {
        (msg.citations as CitationItem[]).forEach(cit => {
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
    const currentConv = conversations.find(c => c.threadId === currentThreadId);
    if (!currentConv) return [];

    const allCitations: CitationItem[] = [];
    const seenIds = new Set<string>();

    currentConv.messages.forEach(msg => {
      if (msg.role === 'assistant' && msg.citations) {
        (msg.citations as CitationItem[]).forEach(cit => {
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
  const fetchSuggestions = useCallback(async (lastAssistantContent: string, lastCitations: CitationItem[]) => {
    setLoadingSuggestions(true);
    try {
      const response = await fetch('/api/v1/chat/suggestions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'assistant', content: lastAssistantContent }],
          citations: lastCitations.map(c => ({
            document_id: c.documentId || '',
            title: c.title || '',
            content: c.snippet || '',
            score: c.score || 0,
            source: c.source || '',
          })),
          count: 3
        })
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
  }, []);

  // Watch for new assistant messages and fetch suggestions
  useEffect(() => {
    if (!currentThreadId) return;
    const currentConv = conversations.find(c => c.threadId === currentThreadId);
    if (!currentConv) return;

    const assistantMessages = currentConv.messages.filter(m => m.role === 'assistant');
    const lastAssistant = assistantMessages[assistantMessages.length - 1];

    if (lastAssistant && lastAssistant.id !== lastMessageIdRef.current) {
      lastMessageIdRef.current = lastAssistant.id || null;
      const citations = (lastAssistant.citations || []) as CitationItem[];
      if (lastAssistant.content) {
        fetchSuggestions(lastAssistant.content, citations);
      }
    }
  }, [conversations, currentThreadId, fetchSuggestions]);

  return (
    <aside className="hidden xl:block w-80 border-l border-[var(--terminal-border)] bg-[var(--terminal-bg)] flex-shrink-0">
      {/* Tabs */}
      <div className="flex items-center gap-1 px-2 py-2 border-b border-[var(--terminal-border)]">
        {[
          { id: 'context', label: 'Context', icon: FileText },
          { id: 'citations', label: 'Citations', icon: BookOpen },
          { id: 'settings', label: 'Settings', icon: Settings },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded text-[10px] transition-colors",
              activeTab === tab.id
                ? "bg-[var(--phosphor-green)]/10 text-[var(--phosphor-green)]"
                : "text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)]"
            )}
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="p-4 overflow-y-auto terminal-scrollbar h-[calc(100%-48px)]">
        {activeTab === 'context' && (
          <div className="space-y-4">
            {/* Document Inspector - Most Relevant RAG Result */}
            <div className="terminal-window p-3">
              <div className="text-[10px] text-[var(--phosphor-green)] uppercase tracking-wider mb-3"
                   style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                📄 Active Document
              </div>
              {activeDocument ? (
                <div className="space-y-2 text-[11px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-[var(--terminal-text-muted)] shrink-0">Title</span>
                    <span className="text-[var(--terminal-text)] text-right truncate" title={activeDocument.title}>
                      {activeDocument.title ? (activeDocument.title.length > 30 ? activeDocument.title.slice(0, 30) + '...' : activeDocument.title) : 'Untitled'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--terminal-text-muted)]">Relevance</span>
                    <span className="text-[var(--phosphor-green)]">
                      {activeDocument.score ? Math.round(activeDocument.score * 100) : 0}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--terminal-text-muted)]">Source</span>
                    <span className="text-[var(--terminal-text)] capitalize">
                      {activeDocument.source || 'document'}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-[11px] text-[var(--terminal-text-muted)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  No active document yet
                </div>
              )}
            </div>

            {/* Related Documents - From RAG Citations */}
            <div>
              <div className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider mb-2"
                   style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                🔍 Related Results
              </div>
              {relatedResults.length > 0 ? (
                relatedResults.map((doc, idx) => {
                  const scorePercent = doc.score ? Math.round(doc.score * 100) : 0;
                  const isExternal = !doc.documentId;
                  return (
                    <button
                      key={doc.documentId || doc.externalReferenceId || idx}
                      className="w-full flex items-center gap-3 p-3 rounded-lg border border-[var(--terminal-border)] hover:border-[var(--phosphor-green)]/30 transition-colors mb-2 text-left"
                    >
                      {isExternal ? (
                        <BookOpen className="w-4 h-4" style={{ color: AMBER }} />
                      ) : (
                        <FileText className="w-4 h-4 text-[var(--terminal-text-muted)]" />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-[var(--terminal-text)] truncate" style={{ fontFamily: "'JetBrains Mono', monospace" }} title={doc.title}>
                          {doc.title || 'Untitled Document'}
                        </p>
                        <p className="text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace", color: scorePercent >= 70 ? PHOSPHOR_GREEN : scorePercent >= 50 ? AMBER : 'var(--terminal-text-muted)' }}>
                          {scorePercent}% match
                        </p>
                      </div>
                    </button>
                  );
                })
              ) : (
                <div className="text-[11px] text-[var(--terminal-text-muted)] py-3" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  No related documents yet
                </div>
              )}
            </div>

            {/* AI Suggestions */}
            <div>
              <div className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider mb-2"
                   style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                💬 Follow-up Suggestions
              </div>
              {loadingSuggestions ? (
                <div className="flex items-center gap-2 py-3 text-[11px] text-[var(--terminal-text-muted)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  <Loader2 className="w-3 h-3 animate-spin" style={{ color: PHOSPHOR_GREEN }} />
                  Generating suggestions...
                </div>
              ) : suggestions.length > 0 ? (
                suggestions.map((suggestion, idx) => (
                  <button
                    key={idx}
                    className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-left text-xs text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)] transition-colors mb-1"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                    onClick={() => {
                      // Dispatch custom event to populate chat input
                      window.dispatchEvent(new CustomEvent('populate-chat-input', { detail: suggestion }));
                    }}
                  >
                    <Sparkles className="w-3 h-3 shrink-0" style={{ color: AMBER }} />
                    <span className="truncate">{suggestion}</span>
                  </button>
                ))
              ) : (
                <div className="text-[11px] text-[var(--terminal-text-muted)] py-3" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  Ask a question to get suggestions
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'citations' && (
          <CitationsTabContent />
        )}

        {activeTab === 'settings' && (
          <div className="space-y-4">
            <div>
              <label className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider"
                     style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                Model
              </label>
              <div className="mt-2 p-3 rounded-lg bg-[var(--terminal-surface)] border border-[var(--terminal-border)]">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-[var(--phosphor-green)]" />
                  <span className="text-xs text-[var(--terminal-text)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    GPT-4O-MINI
                  </span>
                </div>
              </div>
            </div>

            <div>
              <label className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider"
                     style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                Temperature: 0.7
              </label>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                defaultValue="0.7"
                className="w-full mt-2 accent-[var(--phosphor-green)]"
              />
            </div>

            <div>
              <label className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider"
                     style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                Max Tokens: 2048
              </label>
              <input
                type="range"
                min="256"
                max="4096"
                step="256"
                defaultValue="2048"
                className="w-full mt-2 accent-[var(--phosphor-green)]"
              />
            </div>
          </div>
        )}
      </div>
    </aside>
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
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

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
      {/* Workspace Bar */}
      <WorkspaceBar
        onCommandPalette={() => setCommandPaletteOpen(true)}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Main Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <ConversationSidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        {/* Main Content */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {children}
        </main>

        {/* Right Context Panel */}
        <ContextPanel />
      </div>

      {/* Command Palette */}
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
      />
    </div>
  );
}
