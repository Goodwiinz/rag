'use client';

import { IconButton } from '@/components/ui/icon-button';
import { SidebarTrigger } from '@/components/ui/sidebar';
import {
  downloadFile,
  exportAsJson,
  exportAsMarkdown,
} from '@/components/chat/shared/exportConversation';
import {
  ClipboardCopy,
  Download,
  FileJson,
  FileText,
  Menu,
  Search,
} from 'lucide-react';
import { memo, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

interface ExportableMessage {
  role: string;
  content: string;
  timestamp: number;
}

interface ChatHeaderProps {
  onCommandPaletteOpen?: () => void;
  messages?: ExportableMessage[];
  chatTitle?: string;
  onCopyAll?: () => void;
  onMobileSidebarToggle?: () => void;
}

export const ChatHeader = memo(function ChatHeader({
  onCommandPaletteOpen,
  messages = [],
  chatTitle = 'Chat',
  onCopyAll,
  onMobileSidebarToggle,
}: ChatHeaderProps) {
  const [exportOpen, setExportOpen] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!exportOpen) return;
    const handler = (e: MouseEvent) => {
      if (!exportRef.current?.contains(e.target as Node)) {
        setExportOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [exportOpen]);

  const slug = chatTitle.toLowerCase().replace(/\s+/g, '-').slice(0, 40);

  const handleExportMarkdown = () => {
    downloadFile(
      `${slug}.md`,
      'text/markdown',
      exportAsMarkdown(chatTitle, messages)
    );
    setExportOpen(false);
  };

  const handleExportJson = () => {
    downloadFile(
      `${slug}.json`,
      'application/json',
      exportAsJson(chatTitle, messages)
    );
    setExportOpen(false);
  };

  return (
    <div className="flex h-12 sm:h-14 shrink-0 items-center gap-2 sm:gap-3 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/95 px-3 sm:px-4 z-40">
      {/* Left: sidebar trigger + mobile menu + breadcrumb */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0 min-w-0">
        {/* Mobile sidebar toggle */}
        {onMobileSidebarToggle && (
          <button
            type="button"
            onClick={onMobileSidebarToggle}
            className="md:hidden h-9 w-9 shrink-0 flex items-center justify-center text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] hover:bg-[var(--terminal-elevated)] transition-all rounded-lg"
            aria-label="Toggle chat history"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}

        <SidebarTrigger className="hidden md:flex h-7 w-7 shrink-0 text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] hover:bg-[var(--terminal-elevated)] transition-all rounded" />

        {/* Mobile: show chat title */}
        <span
          className="md:hidden text-xs text-[var(--terminal-text)] truncate max-w-[140px]"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {chatTitle}
        </span>

        <div
          className="hidden lg:flex items-center whitespace-nowrap"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <span className="text-xs text-[var(--terminal-text-dim)]">
            Dashboard /{' '}
            <span className="text-[var(--terminal-text)]">Chat</span>
          </span>
        </div>

      </div>

      {/* Middle: compact ⌘K command-palette trigger. The sidebar already has
          a session search; this is the global command affordance only. */}
      <button
        type="button"
        onClick={onCommandPaletteOpen}
        aria-label="Open command palette"
        className="hidden md:flex items-center gap-2 px-2.5 py-1.5 rounded-md border border-[var(--terminal-border)] bg-[var(--terminal-surface)] hover:border-[var(--phosphor-green)]/30 transition-colors"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        <Search className="w-3.5 h-3.5 text-[var(--terminal-text-dim)]" />
        <span className="text-[10px] text-[var(--terminal-text-dim)] uppercase tracking-wider">
          Command
        </span>
        <span className="px-1.5 py-0.5 rounded bg-[var(--terminal-elevated)] border border-[var(--terminal-border)] text-[9px] text-[var(--terminal-text-dim)] whitespace-nowrap">
          ⌘K
        </span>
      </button>

      {/* Right: chat-level actions only. The model picker belongs next to
          the composer, not in the global page chrome. */}
      <div className="flex items-center gap-2 shrink-0 ml-auto">
        {messages.length > 0 && onCopyAll && (
          <IconButton
            label="Copy all messages"
            icon={<ClipboardCopy className="w-4 h-4" />}
            className="p-1.5 text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] transition-colors"
            onClick={onCopyAll}
          />
        )}

        {messages.length > 0 && (
          <div className="relative" ref={exportRef}>
            <IconButton
              label="Export chat"
              icon={<Download className="w-4 h-4" />}
              className="p-1.5 text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] transition-colors"
              onClick={() => setExportOpen((v) => !v)}
            />
            <AnimatePresence>
              {exportOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -5 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 top-full mt-1 w-44 rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg z-50 overflow-hidden"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <button
                    onClick={handleExportMarkdown}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)] focus-visible:bg-[var(--terminal-elevated)] focus-visible:outline-none transition-colors"
                  >
                    <FileText className="w-3.5 h-3.5 text-[var(--terminal-text-dim)]" />
                    Export as Markdown
                  </button>
                  <button
                    onClick={handleExportJson}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)] focus-visible:bg-[var(--terminal-elevated)] focus-visible:outline-none transition-colors"
                  >
                    <FileJson className="w-3.5 h-3.5 text-[var(--terminal-text-dim)]" />
                    Export as JSON
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

      </div>
    </div>
  );
});
