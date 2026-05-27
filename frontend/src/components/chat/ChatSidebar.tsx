'use client';

import { memo, useMemo, useState } from 'react';

import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import {
  CheckSquare,
  ChevronDown,
  MessageSquare,
  Network,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import type { Workspace } from '@/types/workspace';

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
  onRename?: (id: string) => void;
  onDelete?: (id: string) => void;
  onBulkDelete?: (ids: string[]) => void;
  currentWorkspace?: Workspace | null;
  className?: string;
}

export const ChatSidebar = memo(function ChatSidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
  onBulkDelete,
  currentWorkspace,
  className,
}: ChatSidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const filteredConversations = useMemo(
    () =>
      searchQuery.trim()
        ? conversations.filter((conv) =>
            conv.title.toLowerCase().includes(searchQuery.toLowerCase())
          )
        : conversations,
    [conversations, searchQuery]
  );

  const exitSelectMode = (): void => {
    setSelectMode(false);
    setSelectedIds([]);
  };

  const toggleSelected = (id: string): void => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleBulkDelete = (): void => {
    if (selectedIds.length === 0) return;
    onBulkDelete?.(selectedIds);
    exitSelectMode();
  };

  return (
    <div
      className={cn(
        'flex flex-col w-64 border-r border-[var(--nous-border-1)] bg-[var(--nous-bg-1)] h-full',
        className
      )}
    >
      {/* Top Actions */}
      <div className="p-4 space-y-3">
        <button
          type="button"
          aria-label="Select workspace"
          className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] hover:border-[var(--nous-sol)]/20 transition-colors min-w-0"
        >
          <Network className="w-3.5 h-3.5 text-[var(--nous-sol)] shrink-0" />
          <div className="flex-1 min-w-0 text-left">
            <div
              className="text-[9px] uppercase tracking-wider text-[var(--nous-fg-3)]"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Workspace
            </div>
            <div
              className="text-xs text-[var(--nous-fg-1)] font-medium truncate"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
              title={currentWorkspace?.name}
            >
              {currentWorkspace?.name || 'Workspace'}
            </div>
          </div>
          <ChevronDown className="w-3.5 h-3.5 text-[var(--nous-fg-3)] shrink-0" />
        </button>

        <button
          onClick={() => {
            exitSelectMode();
            onNew();
          }}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-[var(--nous-sol)]/10 border border-[var(--nous-sol)]/20 hover:bg-[var(--nous-sol)]/15 hover:border-[var(--nous-sol)]/30 transition-all group"
          style={{ fontFamily: 'var(--nous-font-ui)' }}
        >
          <Plus className="w-4 h-4 text-[var(--nous-sol)] group-hover:scale-110 transition-transform" />
          <span className="text-xs font-semibold text-[var(--nous-sol)]">
            New chat
          </span>
        </button>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--nous-fg-3)]" />
          <input
            type="text"
            placeholder="Search chats..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[var(--nous-bg-2)] border border-[var(--nous-border-1)] rounded-lg py-2 pl-9 pr-3 text-xs text-[var(--nous-fg-1)] placeholder-[var(--nous-fg-3)]/60 focus:outline-none focus:border-[var(--nous-sol)]/30 focus:ring-1 focus:ring-[var(--nous-sol)]/10 transition-all"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          />
        </div>

        {selectMode ? (
          <div className="flex items-center gap-2">
            <button
              onClick={handleBulkDelete}
              disabled={selectedIds.length === 0}
              className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg border border-[var(--nous-mars)]/40 text-[var(--nous-mars)] hover:bg-[var(--nous-mars)]/10 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span className="text-[11px] font-medium">
                Delete ({selectedIds.length})
              </span>
            </button>
            <button
              onClick={exitSelectMode}
              aria-label="Exit select mode"
              className="flex items-center justify-center w-8 h-8 rounded-lg border border-[var(--nous-border-1)] hover:border-[var(--nous-fg-3)] hover:bg-[var(--nous-sol)]/5 transition-all"
            >
              <X className="w-3.5 h-3.5 text-[var(--nous-fg-3)]" />
            </button>
          </div>
        ) : (
          <button
            onClick={() => setSelectMode(true)}
            className="w-full flex items-center justify-start gap-2 py-2 px-3 rounded-lg border border-[var(--nous-border-1)] hover:border-[var(--nous-fg-3)] hover:bg-[var(--nous-sol)]/5 transition-all group"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            <CheckSquare className="w-3.5 h-3.5 text-[var(--nous-fg-3)]" />
            <span className="text-[11px] text-[var(--nous-fg-3)] font-medium">
              Select
            </span>
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-2 space-y-4">
        <div>
          <div className="flex items-center justify-between px-2 mb-2">
            <div className="flex items-center gap-2 text-[var(--nous-fg-3)]">
              <ChevronDown className="w-3.5 h-3.5" />
              <span
                className="text-[10px] uppercase tracking-wider font-medium"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                Recent
              </span>
            </div>
            <span
              className="text-[10px] text-[var(--nous-fg-3)]"
              style={{ fontFamily: 'var(--nous-font-mono)' }}
            >
              {filteredConversations.length}
            </span>
          </div>

          <div className="space-y-0.5">
            {filteredConversations.map((conv) => {
              const isActive = conv.id === activeId;
              const isSelected = selectedIds.includes(conv.id);
              const timeString = formatDistanceToNow(new Date(conv.updatedAt), {
                addSuffix: true,
              }).replace('about ', '');
              const lastMessage = conv.messages[conv.messages.length - 1];
              const messageCount = conv.messageCount ?? conv.messages.length;
              const previewText = lastMessage
                ? lastMessage.content.length > 30
                  ? lastMessage.content.substring(0, 30) + '...'
                  : lastMessage.content || 'No messages yet'
                : conv.previewText ||
                  (messageCount > 0
                    ? `${messageCount} message${messageCount === 1 ? '' : 's'}`
                    : 'No messages yet');

              return (
                <div key={conv.id} className="relative group/row">
                  <button
                    onClick={() => {
                      if (selectMode) {
                        toggleSelected(conv.id);
                      } else {
                        onSelect(conv.id);
                      }
                    }}
                    className={cn(
                      'w-full text-left flex gap-3 p-2.5 rounded-xl transition-all border',
                      isActive
                        ? 'bg-[var(--nous-sol)]/8 border-[var(--nous-sol)]/20'
                        : 'bg-transparent border-transparent hover:bg-[var(--nous-sol)]/5'
                    )}
                  >
                    {selectMode ? (
                      <div className="mt-0.5">
                        <input
                          type="checkbox"
                          aria-label={`Select ${conv.title}`}
                          checked={isSelected}
                          onChange={() => toggleSelected(conv.id)}
                          onClick={(e) => e.stopPropagation()}
                          className="w-3.5 h-3.5 accent-[var(--nous-sol)]"
                        />
                      </div>
                    ) : (
                      <div className="mt-0.5">
                        <MessageSquare
                          className={cn(
                            'w-4 h-4',
                            isActive
                              ? 'text-[var(--nous-sol)]'
                              : 'text-[var(--nous-fg-3)]'
                          )}
                        />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span
                          className={cn(
                            'text-[12px] font-medium truncate',
                            isActive
                              ? 'text-[var(--nous-fg-1)]'
                              : 'text-[var(--nous-fg-2)]'
                          )}
                          style={{ fontFamily: 'var(--nous-font-ui)' }}
                        >
                          {conv.title}
                        </span>
                        <span
                          className="text-[9px] text-[var(--nous-fg-3)] shrink-0 ml-2"
                          style={{ fontFamily: 'var(--nous-font-mono)' }}
                        >
                          {timeString}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span
                          className="text-[11px] text-[var(--nous-fg-3)] truncate"
                          style={{ fontFamily: 'var(--nous-font-body)' }}
                        >
                          {previewText}
                        </span>
                        {isActive && (
                          <span className="text-[9px] text-[var(--nous-fg-3)] shrink-0 ml-2 font-mono">
                            {messageCount}
                          </span>
                        )}
                      </div>
                    </div>
                  </button>

                  {!selectMode && (onRename || onDelete) && (
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 hidden group-hover/row:flex group-focus-within/row:flex items-center gap-0.5 bg-[var(--nous-bg-2)] border border-[var(--nous-border-1)] rounded-lg px-1 py-0.5 shadow-sm">
                      {onRename && (
                        <button
                          type="button"
                          aria-label={`Rename ${conv.title}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            onRename(conv.id);
                          }}
                          className="p-1.5 rounded-md hover:bg-[var(--nous-sol)]/8 text-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)] transition-colors"
                        >
                          <Pencil className="w-3 h-3" />
                        </button>
                      )}
                      {onDelete && (
                        <button
                          type="button"
                          aria-label={`Delete ${conv.title}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            onDelete(conv.id);
                          }}
                          className="p-1.5 rounded-md hover:bg-[var(--nous-mars)]/10 text-[var(--nous-fg-3)] hover:text-[var(--nous-mars)] transition-colors"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
});
