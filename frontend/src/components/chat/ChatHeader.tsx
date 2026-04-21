'use client';

import { IconButton } from '@/components/ui/icon-button';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { AVAILABLE_MODELS, ModelSelector } from '@/components/chat/ModelSelector';
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
  Settings2,
  TerminalSquare,
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
  const [time, setTime] = useState<string>('00:00:00');
  const [exportOpen, setExportOpen] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fn = () => {
      const d = new Date();
      setTime(d.toLocaleTimeString('en-US', { hour12: false }));
    };
    fn();
    const int = setInterval(fn, 1000);
    return () => clearInterval(int);
  }, []);

  // Close export menu on outside click
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
    downloadFile(`${slug}.md`, 'text/markdown', exportAsMarkdown(chatTitle, messages));
    setExportOpen(false);
  };

  const handleExportJson = () => {
    downloadFile(`${slug}.json`, 'application/json', exportAsJson(chatTitle, messages));
    setExportOpen(false);
  };

  return (
    <div className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/95 px-4 z-40">
      {/* Left: breadcrumbs + workspace */}
      <div className="flex items-center gap-4">
        <SidebarTrigger className="h-7 w-7 text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] hover:bg-[var(--terminal-elevated)] transition-all rounded" />

        <div
          className="flex items-center gap-2"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <span className="text-xs text-[var(--terminal-text-dim)]">
            Dashboard /{' '}
            <span className="text-[var(--terminal-text)]">Chat</span>
          </span>
        </div>

        <button
          aria-label="Select workspace"
          className="flex items-center gap-2 ml-4 px-3 py-1.5 rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] hover:bg-[var(--terminal-elevated)] transition-colors"
        >
          <Network className="w-3.5 h-3.5 text-[var(--phosphor-green)]" />
          <span
            className="text-xs text-[var(--terminal-text)]"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {currentWorkspace?.name || 'Fresh Test Workspace'}
          </span>
          <ChevronDown className="w-3.5 h-3.5 text-[var(--terminal-text-dim)] ml-2" />
        </button>
      </div>

      {/* Middle: command palette */}
      <div className="hidden md:flex flex-1 max-w-md relative mx-4">
        <div className="absolute left-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
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
          className="w-full bg-[var(--terminal-surface)] border border-[var(--terminal-border)] rounded-md py-1.5 pl-9 pr-[60px] text-xs text-[var(--terminal-text)] cursor-pointer hover:border-[var(--phosphor-green)]/30 transition-colors"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
          <span
            className="px-1.5 py-0.5 rounded bg-[var(--terminal-elevated)] border border-[var(--terminal-border)] text-[9px] text-[var(--terminal-text-dim)]"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            ⌘K
          </span>
        </div>
      </div>

      {/* Right: model picker + export + copy-all + system status + icons */}
      <div className="flex items-center gap-3">
        {/* Model picker */}
        {onModelChange && (
          <ModelSelector
            models={AVAILABLE_MODELS}
            selectedModelId={selectedModelId}
            onModelChange={onModelChange}
          />
        )}

        {/* Copy all messages */}
        {messages.length > 0 && onCopyAll && (
          <IconButton
            label="Copy all messages"
            icon={<ClipboardCopy className="w-4 h-4" />}
            className="p-1.5 text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] transition-colors"
            onClick={onCopyAll}
          />
        )}

        {/* Export menu */}
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

        {/* Clock */}
        <div
          className="flex items-center gap-3 px-3 py-1.5 rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)]"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <span className="text-[10px] text-[var(--terminal-text-dim)] uppercase tracking-wider">
            Connected
          </span>
          <span className="text-[10px] text-[var(--phosphor-green)] font-bold">
            LTC {time}
          </span>
        </div>

        <IconButton
          label="Terminal"
          icon={<TerminalSquare className="w-4 h-4" />}
          className="p-1.5 text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] transition-colors"
        />
        <IconButton
          label="Settings"
          icon={<Settings2 className="w-4 h-4" />}
          className="p-1.5 text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] transition-colors"
        />
      </div>
    </div>
  );
});
