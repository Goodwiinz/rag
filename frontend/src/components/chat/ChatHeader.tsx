'use client';

import { IconButton } from '@/components/ui/icon-button';
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
    <div className="bg-[var(--nous-bg-1)] flex h-12 sm:h-14 shrink-0 items-center gap-2 sm:gap-3 border-b border-[var(--nous-border-1)] px-3 sm:px-4 z-40">
      {/* Left: sidebar trigger + mobile menu + breadcrumb */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0 min-w-0">
        {onMobileSidebarToggle && (
          <button
            type="button"
            onClick={onMobileSidebarToggle}
            className="md:hidden h-9 w-9 shrink-0 flex items-center justify-center text-[var(--nous-fg-3)] hover:text-[var(--nous-sol)] hover:bg-[var(--nous-sol)]/8 transition-all rounded-xl"
            aria-label="Toggle chat history"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}

        {/* Mobile: show chat title */}
        <span
          className="md:hidden text-[13px] font-medium text-[var(--nous-fg-1)] truncate max-w-[160px]"
          style={{ fontFamily: 'var(--nous-font-ui)' }}
        >
          {chatTitle}
        </span>

        <div
          className="hidden lg:flex items-center whitespace-nowrap"
          style={{ fontFamily: 'var(--nous-font-ui)' }}
        >
          <span className="text-xs text-[var(--nous-fg-3)]">
            Dashboard /{' '}
            <span className="text-[var(--nous-fg-1)] font-medium">Chat</span>
          </span>
        </div>
      </div>

      {/* Command palette trigger */}
      <button
        type="button"
        onClick={onCommandPaletteOpen}
        aria-label="Search"
        className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]/50 hover:border-[var(--nous-sol)]/25 transition-colors"
        style={{ fontFamily: 'var(--nous-font-ui)' }}
      >
        <Search className="w-3.5 h-3.5 text-[var(--nous-fg-3)]" />
        <span className="text-[11px] text-[var(--nous-fg-3)]">Search</span>
        <span className="px-1.5 py-0.5 rounded-md bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)] text-[9px] text-[var(--nous-fg-3)] whitespace-nowrap">
          ⌘K
        </span>
      </button>

      {/* Right: chat actions */}
      <div className="flex items-center gap-1.5 shrink-0 ml-auto">
        {messages.length > 0 && onCopyAll && (
          <IconButton
            label="Copy all messages"
            icon={<ClipboardCopy className="w-4 h-4" />}
            className="p-1.5 text-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)] hover:bg-[var(--nous-sol)]/8 rounded-lg transition-colors"
            onClick={onCopyAll}
          />
        )}

        {messages.length > 0 && (
          <div className="relative" ref={exportRef}>
            <IconButton
              label="Export chat"
              icon={<Download className="w-4 h-4" />}
              className="p-1.5 text-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)] hover:bg-[var(--nous-sol)]/8 rounded-lg transition-colors"
              onClick={() => setExportOpen((v) => !v)}
            />
            <AnimatePresence>
              {exportOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -5 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 top-full mt-1 w-48 rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-lg z-50 overflow-hidden p-1"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                >
                  <button
                    onClick={handleExportMarkdown}
                    className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-[var(--nous-fg-2)] hover:bg-[var(--nous-sol)]/8 hover:text-[var(--nous-fg-1)] focus-visible:bg-[var(--nous-sol)]/8 focus-visible:outline-none rounded-lg transition-colors"
                  >
                    <FileText className="w-3.5 h-3.5 text-[var(--nous-fg-3)]" />
                    Export as Markdown
                  </button>
                  <button
                    onClick={handleExportJson}
                    className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-[var(--nous-fg-2)] hover:bg-[var(--nous-sol)]/8 hover:text-[var(--nous-fg-1)] focus-visible:bg-[var(--nous-sol)]/8 focus-visible:outline-none rounded-lg transition-colors"
                  >
                    <FileJson className="w-3.5 h-3.5 text-[var(--nous-fg-3)]" />
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
