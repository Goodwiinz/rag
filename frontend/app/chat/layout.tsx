'use client';

import { cn } from '@/lib/utils';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Clock,
  Command,
  Cpu,
  FileText,
  FolderOpen,
  Hash,
  Hexagon,
  LogOut,
  Menu,
  MessageSquare,
  Moon,
  Pin,
  Plus,
  Radio,
  Search,
  Settings,
  Share2,
  Sparkles,
  Sun,
  Terminal,
  User,
  Users,
  X,
  Zap,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

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

          <Link href="/" className="flex items-center gap-3">
            <div className="relative">
              <Hexagon className="w-7 h-7 text-[var(--phosphor-green)]" />
              <Terminal className="absolute inset-0 m-auto w-3.5 h-3.5 text-[var(--phosphor-green)]" />
            </div>
            <div className="hidden sm:block">
              <h1 className="text-xs font-semibold text-[var(--terminal-text)] tracking-wider"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                TERMINAL OBSERVATORY
              </h1>
              <p className="text-[9px] text-[var(--terminal-text-muted)]"
                 style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                GENAI RESEARCH PLATFORM
              </p>
            </div>
          </Link>

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

  // Mock data
  const conversations: Conversation[] = [
    { id: '1', title: 'Research Paper Summary', preview: 'Analyzing the BIT paper...', timestamp: new Date(), isPinned: true, messageCount: 12 },
    { id: '2', title: 'RAG Optimization Guide', preview: 'Key findings from the...', timestamp: new Date(), isPinned: true, messageCount: 8 },
    { id: '3', title: 'How does BIT improve RAG precision?', preview: 'Based on the analysis...', timestamp: new Date(), messageCount: 5 },
    { id: '4', title: 'Compare BAAI/bge vs OpenAI', preview: 'Comparing embedding models...', timestamp: new Date(), messageCount: 15 },
    { id: '5', title: 'Prompt injection defense', preview: 'Defense strategies include...', timestamp: new Date(Date.now() - 86400000), messageCount: 7 },
  ];

  const collections: Collection[] = [
    { id: '1', name: 'ML Research', icon: '📁', count: 12 },
    { id: '2', name: 'Project: BIT Defense', icon: '📁', count: 5 },
    { id: '3', name: 'Paper Notes', icon: '📁', count: 23 },
  ];

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const pinnedConversations = conversations.filter((c) => c.isPinned);
  const recentConversations = conversations.filter((c) => !c.isPinned);

  const sidebarContent = (
    <div className="h-full flex flex-col bg-[var(--terminal-bg)]">
      {/* Search */}
      <div className="p-3 border-b border-[var(--terminal-border)]">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--terminal-text-muted)]" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-[var(--terminal-surface)] border border-[var(--terminal-border)] text-xs text-[var(--terminal-text)] outline-none focus:border-[var(--phosphor-green)]/30"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          />
        </div>
      </div>

      {/* New Chat Button */}
      <div className="px-3 py-2">
        <Link
          href="/chat/new"
          className="flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-lg bg-[var(--phosphor-green)] text-[var(--terminal-bg)] text-xs font-medium hover:shadow-[0_0_20px_var(--phosphor-green-glow)] transition-all"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <Plus className="w-4 h-4" />
          NEW CHAT
        </Link>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto terminal-scrollbar">
        {/* Pinned */}
        {pinnedConversations.length > 0 && (
          <div className="px-2 py-2">
            <button
              onClick={() => toggleSection('pinned')}
              className="flex items-center gap-2 w-full px-2 py-1.5 text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider hover:text-[var(--terminal-text-dim)]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <Pin className="w-3 h-3" />
              Pinned
              <ChevronRight className={cn(
                "w-3 h-3 ml-auto transition-transform",
                expandedSections.pinned && "rotate-90"
              )} />
            </button>
            <AnimatePresence>
              {expandedSections.pinned && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                >
                  {pinnedConversations.map((conv) => (
                    <ConversationItem key={conv.id} conversation={conv} isActive={pathname === `/chat/${conv.id}`} />
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Recent */}
        <div className="px-2 py-2">
          <button
            onClick={() => toggleSection('recent')}
            className="flex items-center gap-2 w-full px-2 py-1.5 text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider hover:text-[var(--terminal-text-dim)]"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            <Clock className="w-3 h-3" />
            Recent
            <ChevronRight className={cn(
              "w-3 h-3 ml-auto transition-transform",
              expandedSections.recent && "rotate-90"
            )} />
          </button>
          <AnimatePresence>
            {expandedSections.recent && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
              >
                {recentConversations.map((conv) => (
                  <ConversationItem key={conv.id} conversation={conv} isActive={pathname === `/chat/${conv.id}`} />
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Collections */}
        <div className="px-2 py-2 border-t border-[var(--terminal-border)]">
          <button
            onClick={() => toggleSection('collections')}
            className="flex items-center gap-2 w-full px-2 py-1.5 text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider hover:text-[var(--terminal-text-dim)]"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            <FolderOpen className="w-3 h-3" />
            Collections
            <ChevronRight className={cn(
              "w-3 h-3 ml-auto transition-transform",
              expandedSections.collections && "rotate-90"
            )} />
          </button>
          <AnimatePresence>
            {expandedSections.collections && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
              >
                {collections.map((collection) => (
                  <button
                    key={collection.id}
                    className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-left hover:bg-[var(--terminal-elevated)] transition-colors"
                  >
                    <span>{collection.icon}</span>
                    <span className="flex-1 text-xs text-[var(--terminal-text)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {collection.name}
                    </span>
                    <span className="text-[10px] text-[var(--terminal-text-muted)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {collection.count}
                    </span>
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-[var(--terminal-border)]">
        <Link
          href="/settings"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-xs text-[var(--terminal-text-dim)] hover:bg-[var(--terminal-elevated)] hover:text-[var(--terminal-text)] transition-colors"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <Settings className="w-4 h-4" />
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

function ConversationItem({
  conversation,
  isActive,
}: {
  conversation: Conversation;
  isActive: boolean;
}) {
  return (
    <Link
      href={`/chat/${conversation.id}`}
      className={cn(
        "block px-3 py-2.5 rounded-lg my-0.5 transition-all group",
        isActive
          ? "bg-[var(--phosphor-green)]/10 border-l-2 border-[var(--phosphor-green)]"
          : "hover:bg-[var(--terminal-elevated)]"
      )}
    >
      <div className="flex items-start gap-3">
        <MessageSquare className={cn(
          "w-4 h-4 mt-0.5 flex-shrink-0",
          isActive ? "text-[var(--phosphor-green)]" : "text-[var(--terminal-text-muted)]"
        )} />
        <div className="flex-1 min-w-0">
          <p className={cn(
            "text-xs truncate",
            isActive ? "text-[var(--phosphor-green)]" : "text-[var(--terminal-text)]"
          )} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {conversation.title}
          </p>
          <p className="text-[10px] text-[var(--terminal-text-muted)] truncate mt-0.5"
             style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {conversation.preview}
          </p>
        </div>
      </div>
    </Link>
  );
}

// ============================================
// CONTEXT PANEL (RIGHT)
// ============================================

function ContextPanel() {
  const [activeTab, setActiveTab] = useState<'context' | 'citations' | 'settings'>('context');

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
            {/* Document Inspector */}
            <div className="terminal-window p-3">
              <div className="text-[10px] text-[var(--phosphor-green)] uppercase tracking-wider mb-3"
                   style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                📄 Active Document
              </div>
              <div className="space-y-2 text-[11px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--terminal-text-muted)]">File</span>
                  <span className="text-[var(--terminal-text)]">research-paper.pdf</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--terminal-text-muted)]">Tokens</span>
                  <span className="text-[var(--phosphor-green)]">8,243</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--terminal-text-muted)]">Embedding</span>
                  <span className="text-[var(--terminal-text)]">bge-large-en</span>
                </div>
              </div>
            </div>

            {/* Related Documents */}
            <div>
              <div className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider mb-2"
                   style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                🔍 Related Results
              </div>
              {[
                { title: 'RAG Optimization', score: 85 },
                { title: 'Embedding Fine-tuning', score: 72 },
                { title: 'BIT Defense Strategies', score: 68 },
              ].map((doc, idx) => (
                <button
                  key={idx}
                  className="w-full flex items-center gap-3 p-3 rounded-lg border border-[var(--terminal-border)] hover:border-[var(--phosphor-green)]/30 transition-colors mb-2 text-left"
                >
                  <FileText className="w-4 h-4 text-[var(--terminal-text-muted)]" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-[var(--terminal-text)] truncate" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {doc.title}
                    </p>
                    <p className="text-[10px] text-[var(--phosphor-green)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {doc.score}% match
                    </p>
                  </div>
                </button>
              ))}
            </div>

            {/* AI Suggestions */}
            <div>
              <div className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider mb-2"
                   style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                💬 Follow-up Suggestions
              </div>
              {[
                'Compare with Transformer models',
                'Evaluate on benchmark datasets',
                'Generate test cases for defense',
              ].map((suggestion, idx) => (
                <button
                  key={idx}
                  className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-left text-xs text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)] transition-colors mb-1"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <Sparkles className="w-3 h-3 text-[var(--amber-gold)]" />
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'citations' && (
          <div className="space-y-3">
            <p className="text-xs text-[var(--terminal-text-muted)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              Citations from current conversation will appear here.
            </p>
          </div>
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
