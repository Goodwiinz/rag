'use client';

import { IconButton } from '@/components/ui/icon-button';
import { SidebarTrigger } from '@/components/ui/sidebar';
import {
  AVAILABLE_MODELS,
  ModelSelector,
} from '@/components/chat/ModelSelector';
import {
  downloadFile,
  exportAsJson,
  exportAsMarkdown,
} from '@/components/chat/shared/exportConversation';
import { Workspace } from '@/types/workspace';
import {
  ChevronDown,
  ClipboardCopy,
  Download,
  FileJson,
  FileText,
  Network,
  Search,
} from 'lucide-react';
import { memo, useEffect, useRef, useState } from 'react';

interface ExportableMessage {
  role: string;
  content: string;
  timestamp: number;
}

interface ChatHeaderProps {
  currentWorkspace: Workspace | null;
  onCommandPaletteOpen?: () => void;
  selectedModelId?: string;
  onModelChange?: (id: string) => void;
  messages?: ExportableMessage[];
  chatTitle?: string;
  onCopyAll?: () => void;
}

export const ChatHeader = memo(function ChatHeader({
  currentWorkspace,
  onCommandPaletteOpen,
  selectedModelId = 'gpt-4o',
  onModelChange,
  messages = [],
  chatTitle = 'Chat',
  onCopyAll,
}: ChatHeaderProps) {
  const [time, setTime] = useState<string>('--:--');
  const [exportOpen, setExportOpen] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fn = () => {
      const d = new Date();
      setTime(
        d.toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
          hour12: false,
        })
      );
    };
    fn();
    // HH:MM only — refresh once a minute is plenty
    const int = setInterval(fn, 30_000);
    return () => clearInterval(int);
  }, []);

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
    <div className="flex h-14 shrink-0 items-center gap-3 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/95 px-4 z-40">
      {/* Left: sidebar trigger + breadcrumb + workspace (compact, no-wrap) */}
      <div className="flex items-center gap-3 shrink-0 min-w-0">
        <SidebarTrigger className="h-7 w-7 shrink-0 text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] hover:bg-[var(--terminal-elevated)] transition-all rounded" />

        <div
          className="hidden lg:flex items-center whitespace-nowrap"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <span className="text-xs text-[var(--terminal-text-dim)]">
            Dashboard /{' '}
            <span className="text-[var(--terminal-text)]">Chat</span>
          </span>
        </div>

        <button
          aria-label="Select workspace"
          className="flex items-center gap-2 px-3 py-1.5 rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] hover:bg-[var(--terminal-elevated)] transition-colors max-w-[200px] min-w-0"
        >
          <Network className="w-3.5 h-3.5 text-[var(--phosphor-green)] shrink-0" />
          <span
            className="text-xs text-[var(--terminal-text)] truncate"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
            title={currentWorkspace?.name}
          >
            {currentWorkspace?.name || 'Workspace'}
          </span>
          <ChevronDown className="w-3.5 h-3.5 text-[var(--terminal-text-dim)] shrink-0" />
        </button>
      </div>

      {/* Middle: search (flex-1, shrinks before right side does) */}
      <div className="hidden md:flex flex-1 min-w-0 max-w-md relative">
        <div className="absolute left-3 top-1/2 -translate-y-1/2">
          <Search className="w-3.5 h-3.5 text-[var(--terminal-text-dim)]" />
        </div>
        <input
          type="text"
          placeholder="Search or command..."
          readOnly
          role="button"
          aria-label="Open command palette"
          tabIndex={0}
          onClick={onCommandPaletteOpen}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              onCommandPaletteOpen?.();
            }
          }}
          className="w-full bg-[var(--terminal-surface)] border border-[var(--terminal-border)] rounded-md py-1.5 pl-9 pr-[50px] text-xs text-[var(--terminal-text)] cursor-pointer hover:border-[var(--phosphor-green)]/30 transition-colors"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        />
        <span
          className="absolute right-2 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded bg-[var(--terminal-elevated)] border border-[var(--terminal-border)] text-[9px] text-[var(--terminal-text-dim)] whitespace-nowrap"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          ⌘K
        </span>
      </div>

      {/* Right: model + actions + status (all no-wrap) */}
      <div className="flex items-center gap-2 shrink-0 ml-auto">
        {onModelChange && (
          <ModelSelector
            models={AVAILABLE_MODELS}
            selectedModelId={selectedModelId}
            onModelChange={onModelChange}
          />
        )}

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
            {exportOpen && (
              <div
                className="absolute right-0 top-full mt-1 w-44 rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg z-50 overflow-hidden"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                <button
                  onClick={handleExportMarkdown}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)] transition-colors"
                >
                  <FileText className="w-3.5 h-3.5 text-[var(--terminal-text-dim)]" />
                  Export as Markdown
                </button>
                <button
                  onClick={handleExportJson}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)] transition-colors"
                >
                  <FileJson className="w-3.5 h-3.5 text-[var(--terminal-text-dim)]" />
                  Export as JSON
                </button>
              </div>
            )}
          </div>
        )}

        {/* Compact status: green dot + time */}
        <div
          className="hidden lg:flex items-center gap-2 px-2.5 py-1.5 rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] whitespace-nowrap"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
          title="Connected"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--phosphor-green)] animate-pulse" />
          <span className="text-[10px] text-[var(--phosphor-green)] font-bold tabular-nums">
            {time}
          </span>
        </div>
      </div>
    </div>
  );
});
