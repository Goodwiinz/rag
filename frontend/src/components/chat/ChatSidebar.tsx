'use client';

import { memo, useMemo, useState } from 'react';

import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import {
  CheckSquare,
  ChevronDown,
  MessageSquare,
  Plus,
  Search,
} from 'lucide-react';

// UI conversation type (mapped from DB Thread in page.tsx)
interface SidebarConversation {
  id: string;
  title: string;
  messages: { role: string; content: string }[];
  updatedAt: number;
  previewText?: string;
  messageCount?: number;
}

interface ChatSidebarProps {
  conversations: SidebarConversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  className?: string;
}

export const ChatSidebar = memo(function ChatSidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  className,
}: ChatSidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredConversations = useMemo(
    () =>
      searchQuery.trim()
        ? conversations.filter((conv) =>
            conv.title.toLowerCase().includes(searchQuery.toLowerCase())
          )
        : conversations,
    [conversations, searchQuery]
  );

  return (
    <div
      className={cn(
        'flex flex-col w-64 border-r border-[var(--terminal-border)] bg-[#0A0A0A] h-full',
        className
      )}
    >
      {/* Top Actions */}
      <div className="p-4 space-y-4">
        <button
          onClick={onNew}
          className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded border border-[var(--terminal-border)] hover:border-[var(--terminal-text-dim)] bg-[var(--terminal-surface)] hover:bg-[var(--terminal-elevated)] transition-all group"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <Plus className="w-4 h-4 text-[var(--terminal-text)] group-hover:text-[var(--phosphor-green)] transition-colors" />
          <span className="text-xs font-bold text-[var(--terminal-text)] tracking-wider">
            NEW SESSION
          </span>
        </button>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--terminal-text-dim)]" />
          <input
            type="text"
            placeholder="Search Logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[var(--terminal-surface)] border border-[var(--terminal-border)] rounded py-1.5 pl-9 pr-3 text-xs text-[var(--terminal-text)] placeholder-[var(--terminal-text-dim)]/70 focus:outline-none focus:border-[var(--phosphor-green)]/30 transition-colors"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          />
        </div>

        <button
          className="w-full flex items-center justify-start gap-2 py-1.5 px-3 rounded border border-[var(--terminal-border)] hover:border-[var(--terminal-text-dim)] hover:bg-[var(--terminal-elevated)] transition-all group"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <CheckSquare className="w-3.5 h-3.5 text-[var(--terminal-text-dim)]" />
          <span className="text-[10px] text-[var(--terminal-text-dim)] uppercase tracking-wider">
            Select
          </span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto terminal-scrollbar px-2 space-y-6">
        {/* RECENT Section */}
        <div>
          <div className="flex items-center justify-between px-2 mb-2">
            <div className="flex items-center gap-2 text-[var(--terminal-text-dim)]">
              <ChevronDown className="w-3.5 h-3.5" />
              <span
                className="text-[10px] uppercase tracking-wider"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                Recent
              </span>
            </div>
            <span
              className="text-[10px] text-[var(--terminal-text-dim)]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {filteredConversations.length}
            </span>
          </div>

          <div className="space-y-1">
            {filteredConversations.map((conv) => {
              const isActive = conv.id === activeId;
              const timeString = formatDistanceToNow(new Date(conv.updatedAt), {
                addSuffix: true,
              }).replace('about ', '');
              const lastMessage = conv.messages[conv.messages.length - 1];
              const messageCount = conv.messageCount ?? conv.messages.length;
              const previewText =
                (lastMessage
                ? lastMessage.content.length > 30
                  ? lastMessage.content.substring(0, 30) + '...'
                  : lastMessage.content || 'No messages yet'
                : conv.previewText ||
                  (messageCount > 0
                    ? `${messageCount} message${messageCount === 1 ? '' : 's'}`
                    : 'No messages yet'));

              return (
                <button
                  key={conv.id}
                  onClick={() => onSelect(conv.id)}
                  className={cn(
                    'w-full text-left flex gap-3 p-2.5 rounded-lg transition-all border',
                    isActive
                      ? 'bg-[var(--phosphor-green)]/5 border-[var(--phosphor-green)]/20'
                      : 'bg-transparent border-transparent hover:bg-[var(--terminal-elevated)]'
                  )}
                >
                  <div className="mt-0.5">
                    <MessageSquare
                      className={cn(
                        'w-4 h-4',
                        isActive
                          ? 'text-[var(--phosphor-green)]'
                          : 'text-[var(--terminal-text-dim)]'
                      )}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span
                        className={cn(
                          'text-xs font-semibold truncate',
                          isActive
                            ? 'text-[var(--terminal-text)]'
                            : 'text-[var(--terminal-text)]/80'
                        )}
                        style={{ fontFamily: "'JetBrains Mono', monospace" }}
                      >
                        {conv.title}
                      </span>
                      <span
                        className="text-[9px] text-[var(--terminal-text-dim)] shrink-0 ml-2"
                        style={{ fontFamily: "'JetBrains Mono', monospace" }}
                      >
                        {timeString}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-[var(--terminal-text-dim)] truncate">
                        {previewText}
                      </span>
                      {isActive && (
                        <span className="text-[9px] text-[var(--terminal-text-dim)] shrink-0 ml-2 font-mono">
                          {messageCount}
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
});
