'use client';

import { memo, useCallback, useEffect, useMemo, useState } from 'react';

import { cn } from '@/lib/utils';
import { isToday, isYesterday, formatDistanceToNowStrict } from 'date-fns';
import {
  CheckSquare,
  ChevronDown,
  MessageSquare,
  Network,
  Pencil,
  Pin,
  Plus,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import type { Workspace } from '@/types/workspace';

interface SidebarConversation {
  id: string;
  title: string;
  messages: { role: string; content: string }[];
  updatedAt: number;
  previewText?: string;
  messageCount?: number;
  pinned?: boolean;
  unread?: boolean;
  tags?: string[];
}

type FilterKey = 'all' | 'pinned' | 'drafts' | 'shared';

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

function formatCompactTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffH = Math.floor(diffMs / (1000 * 60 * 60));
  const diffD = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffH < 1)
    return formatDistanceToNowStrict(date, { addSuffix: false })
      .replace(' minutes', 'm')
      .replace(' minute', 'm')
      .replace(' seconds', 's')
      .replace(' second', 's');
  if (diffH < 24) return `${diffH}h`;
  return `${diffD}d`;
}

interface DateSection {
  label: string;
  items: SidebarConversation[];
}

function groupByDate(conversations: SidebarConversation[]): DateSection[] {
  const pinned: SidebarConversation[] = [];
  const today: SidebarConversation[] = [];
  const yesterday: SidebarConversation[] = [];
  const earlier: SidebarConversation[] = [];

  for (const conv of conversations) {
    if (conv.pinned) {
      pinned.push(conv);
      continue;
    }
    const d = new Date(conv.updatedAt);
    if (isToday(d)) today.push(conv);
    else if (isYesterday(d)) yesterday.push(conv);
    else earlier.push(conv);
  }

  const sections: DateSection[] = [];
  if (pinned.length > 0) sections.push({ label: 'Pinned', items: pinned });
  if (today.length > 0) sections.push({ label: 'Today', items: today });
  if (yesterday.length > 0)
    sections.push({ label: 'Yesterday', items: yesterday });
  if (earlier.length > 0) sections.push({ label: 'Earlier', items: earlier });
  return sections;
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
  const [activeFilter, setActiveFilter] = useState<FilterKey>('all');

  const filteredConversations = useMemo(() => {
    let list = conversations;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((c) => c.title.toLowerCase().includes(q));
    }
    if (activeFilter === 'pinned') list = list.filter((c) => c.pinned);
    return list;
  }, [conversations, searchQuery, activeFilter]);

  const sections = useMemo(
    () => groupByDate(filteredConversations),
    [filteredConversations]
  );

  const pinnedCount = useMemo(
    () => conversations.filter((c) => c.pinned).length,
    [conversations]
  );

  const exitSelectMode = useCallback((): void => {
    setSelectMode(false);
    setSelectedIds([]);
  }, []);

  const toggleSelected = useCallback((id: string): void => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }, []);

  const handleBulkDelete = useCallback((): void => {
    if (selectedIds.length === 0) return;
    onBulkDelete?.(selectedIds);
    exitSelectMode();
  }, [selectedIds, onBulkDelete, exitSelectMode]);

  // ⌘N shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
        e.preventDefault();
        exitSelectMode();
        onNew();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onNew, exitSelectMode]);

  return (
    <aside
      aria-label="Conversations"
      className={cn(
        'flex flex-col w-[260px] border-r border-[var(--nous-border-1)] bg-[var(--nous-bg-1)] dark:bg-[var(--nous-nyx)] dark:border-[var(--nous-shade)] h-full',
        className
      )}
    >
      {/* Top chrome — pinned, doesn't scroll */}
      <div className="shrink-0 p-3.5 pb-3 flex flex-col gap-2.5 border-b border-[var(--nous-border-1)] dark:border-[var(--nous-shade)]">
        {/* Workspace switcher */}
        <button
          type="button"
          aria-label="Select workspace"
          className="w-full flex items-center gap-[9px] px-2.5 py-2 rounded-lg border border-[var(--nous-border-1)] dark:border-[var(--nous-shade)] bg-transparent hover:border-[var(--nous-sol)]/30 hover:bg-[var(--nous-bg-2)] dark:hover:bg-[var(--nous-obsidian)] transition-all min-w-0"
        >
          <div className="w-[22px] h-[22px] rounded-[5px] flex items-center justify-center bg-[var(--nous-aurum)] dark:bg-[var(--nous-ember)] shrink-0">
            <Network className="w-3 h-3 text-[var(--nous-sol-safe)] dark:text-[var(--nous-helios)]" />
          </div>
          <div className="flex-1 min-w-0 text-left flex flex-col gap-px">
            <span
              className="text-[13px] font-semibold text-[var(--nous-fg-1)] truncate leading-tight"
              style={{
                fontFamily: 'var(--nous-font-ui)',
                letterSpacing: '-0.005em',
              }}
            >
              {currentWorkspace?.name || 'My Workspace'}
            </span>
            <span
              className="text-[11px] text-[var(--nous-fg-3)]"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              {conversations.length} thread
              {conversations.length !== 1 ? 's' : ''}
            </span>
          </div>
          <ChevronDown className="w-3 h-3 text-[var(--nous-fg-3)] shrink-0" />
        </button>

        {/* New chat */}
        <button
          onClick={() => {
            exitSelectMode();
            onNew();
          }}
          className="w-full flex items-center justify-center gap-[7px] py-[9px] px-3 rounded-lg bg-[var(--nous-erebus)] dark:bg-[var(--nous-umber)] dark:border dark:border-[var(--nous-shade)] text-white shadow-sm hover:shadow-md transition-shadow"
          style={{ fontFamily: 'var(--nous-font-ui)' }}
        >
          <Plus className="w-[13px] h-[13px]" />
          <span
            className="text-[13px] font-semibold"
            style={{ letterSpacing: '-0.005em' }}
          >
            New chat
          </span>
          <kbd
            className="ml-auto px-[5px] py-px rounded-[3px] bg-white/12 text-white/70 text-[9px] font-semibold"
            style={{ fontFamily: 'var(--nous-font-mono)' }}
          >
            ⌘N
          </kbd>
        </button>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-[10px] top-1/2 -translate-y-1/2 w-[13px] h-[13px] text-[var(--nous-fg-3)] pointer-events-none" />
          <input
            type="text"
            placeholder="Search threads..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-8 bg-[var(--nous-bg-2)] dark:bg-[var(--nous-obsidian)] border border-[var(--nous-border-1)] dark:border-[var(--nous-shade)] rounded-[7px] py-0 pl-[30px] pr-[38px] text-xs text-[var(--nous-fg-1)] placeholder-[var(--nous-fg-3)] focus:outline-none focus:border-[var(--nous-sol)] dark:focus:border-[var(--nous-helios)] focus:bg-[var(--nous-bg-1)] transition-all"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          />
          <kbd
            className="absolute right-2 top-1/2 -translate-y-1/2 px-[5px] py-px bg-[var(--nous-bg-1)] dark:bg-[var(--nous-nyx)] border border-[var(--nous-border-1)] dark:border-[var(--nous-shade)] rounded-[3px] text-[9px] font-semibold text-[var(--nous-fg-3)] pointer-events-none"
            style={{ fontFamily: 'var(--nous-font-mono)' }}
          >
            ⌘K
          </kbd>
        </div>
      </div>

      {/* Filter chips */}
      <div className="shrink-0 flex gap-1 px-3.5 py-2.5 overflow-x-auto border-b border-[var(--nous-border-1)] dark:border-[var(--nous-shade)] scrollbar-hide">
        {(
          [
            {
              key: 'all' as FilterKey,
              label: 'All',
              count: conversations.length,
            },
            { key: 'pinned' as FilterKey, label: 'Pinned', count: pinnedCount },
          ] as const
        ).map((f) => (
          <button
            key={f.key}
            onClick={() => setActiveFilter(f.key)}
            className={cn(
              'inline-flex items-center px-[9px] py-[3px] rounded-full border text-[10px] whitespace-nowrap transition-all',
              activeFilter === f.key
                ? 'bg-[var(--nous-erebus)] dark:bg-[var(--nous-helios)] text-white dark:text-[var(--nous-nyx)] border-[var(--nous-erebus)] dark:border-[var(--nous-helios)]'
                : 'bg-transparent border-[var(--nous-border-1)] dark:border-[var(--nous-shade)] text-[var(--nous-fg-2)] hover:border-[var(--nous-sol)] hover:text-[var(--nous-sol-safe)]'
            )}
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            {f.label}
            <span
              className={cn(
                'ml-1',
                activeFilter === f.key ? 'opacity-70' : 'opacity-55'
              )}
            >
              {f.count}
            </span>
          </button>
        ))}

        {/* Select mode toggle */}
        {selectMode ? (
          <div className="ml-auto flex items-center gap-1 shrink-0">
            <button
              onClick={handleBulkDelete}
              disabled={selectedIds.length === 0}
              className="inline-flex items-center gap-1 px-2 py-[3px] rounded-full border border-[var(--nous-mars)]/40 text-[var(--nous-mars)] text-[10px] hover:bg-[var(--nous-mars)]/10 transition-all disabled:opacity-40"
              style={{ fontFamily: 'var(--nous-font-mono)' }}
            >
              <Trash2 className="w-2.5 h-2.5" />
              {selectedIds.length}
            </button>
            <button
              onClick={exitSelectMode}
              aria-label="Exit select mode"
              className="w-5 h-5 flex items-center justify-center rounded-full border border-[var(--nous-border-1)] hover:bg-[var(--nous-sol)]/5 transition-all"
            >
              <X className="w-2.5 h-2.5 text-[var(--nous-fg-3)]" />
            </button>
          </div>
        ) : (
          <button
            onClick={() => setSelectMode(true)}
            aria-label="Select conversations"
            className="ml-auto inline-flex items-center gap-1 px-[9px] py-[3px] rounded-full border border-[var(--nous-border-1)] dark:border-[var(--nous-shade)] text-[10px] text-[var(--nous-fg-3)] hover:border-[var(--nous-fg-3)] transition-all shrink-0"
            style={{ fontFamily: 'var(--nous-font-mono)' }}
          >
            <CheckSquare className="w-2.5 h-2.5" aria-hidden="true" />
          </button>
        )}
      </div>

      {/* Scroll region — only this scrolls */}
      <div className="flex-1 overflow-y-auto pt-1">
        {sections.map((section) => (
          <div key={section.label} className="px-2.5 pb-1.5">
            {/* Section label */}
            <div className="flex items-center gap-1.5 px-2 pt-2.5 pb-1.5">
              {section.label === 'Pinned' && (
                <Pin className="w-[9px] h-[9px] text-[var(--nous-sol)] dark:text-[var(--nous-helios)]" />
              )}
              <span
                className="text-[11px] font-medium text-[var(--nous-fg-3)]"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                {section.label}
              </span>
              <span
                className="ml-auto px-[5px] py-px bg-[var(--nous-bg-2)] dark:bg-[var(--nous-obsidian)] border border-[var(--nous-border-1)] dark:border-[var(--nous-shade)] rounded-[3px] text-[9px] text-[var(--nous-fg-2)]"
                style={{
                  fontFamily: 'var(--nous-font-mono)',
                  letterSpacing: '0.04em',
                }}
              >
                {section.items.length}
              </span>
            </div>

            {/* Conversation items */}
            {section.items.map((conv) => {
              const isActive = conv.id === activeId;
              const isSelected = selectedIds.includes(conv.id);
              const timeStr = formatCompactTime(new Date(conv.updatedAt));
              const messageCount = conv.messageCount ?? conv.messages.length;
              const lastMessage = conv.messages[conv.messages.length - 1];
              const snippet =
                conv.previewText ||
                (lastMessage?.content
                  ? lastMessage.content.length > 60
                    ? lastMessage.content.substring(0, 60) + '…'
                    : lastMessage.content
                  : messageCount > 0
                    ? `${messageCount} message${messageCount === 1 ? '' : 's'}`
                    : 'No messages yet');

              return (
                <div key={conv.id} className="relative group/row">
                  <button
                    onClick={() =>
                      selectMode ? toggleSelected(conv.id) : onSelect(conv.id)
                    }
                    className={cn(
                      'sb-conv w-full text-left block p-[9px_11px] rounded-[7px] border transition-[background,border-color] duration-[180ms] mb-px relative',
                      isActive
                        ? 'bg-[var(--nous-aurum)] dark:bg-[var(--nous-ember)] border-[rgba(212,160,57,0.2)] dark:border-[rgba(232,184,74,0.25)]'
                        : 'bg-transparent border-transparent hover:bg-[var(--nous-bg-2)] dark:hover:bg-[var(--nous-obsidian)]'
                    )}
                  >
                    {/* Row 1: pin + title + unread */}
                    <div className="flex items-center gap-1.5 mb-[3px]">
                      {selectMode && (
                        <input
                          type="checkbox"
                          aria-label={`Select ${conv.title}`}
                          checked={isSelected}
                          onChange={() => toggleSelected(conv.id)}
                          onClick={(e) => e.stopPropagation()}
                          className="w-3 h-3 accent-[var(--nous-sol)] shrink-0"
                        />
                      )}
                      {conv.pinned && !selectMode && (
                        <Pin className="w-[10px] h-[10px] text-[var(--nous-sol)] dark:text-[var(--nous-helios)] shrink-0" />
                      )}
                      <span
                        className="text-[13px] font-medium text-[var(--nous-fg-1)] truncate flex-1 min-w-0"
                        style={{ fontFamily: 'var(--nous-font-ui)' }}
                      >
                        {conv.title}
                      </span>
                      {conv.unread && (
                        <span className="w-1.5 h-1.5 rounded-full bg-[var(--nous-sol)] dark:bg-[var(--nous-helios)] shadow-[0_0_0_2px_rgba(212,160,57,0.15)] shrink-0" />
                      )}
                    </div>

                    {/* Snippet */}
                    <div
                      className="text-[11px] leading-[1.5] text-[var(--nous-fg-3)] truncate"
                      style={{ fontFamily: 'var(--nous-font-body)' }}
                    >
                      {snippet}
                    </div>

                    {/* Meta row: tags + time */}
                    <div className="flex items-center justify-between gap-2 mt-1.5">
                      <div className="flex gap-1 min-w-0 overflow-hidden">
                        {(conv.tags || []).slice(0, 2).map((tag) => (
                          <span
                            key={tag}
                            className="inline-flex items-center px-1.5 py-px bg-[var(--nous-bg-2)] dark:bg-[var(--nous-nyx)] border border-[var(--nous-border-1)] dark:border-[var(--nous-shade)] rounded-[3px] text-[9px] text-[var(--nous-fg-2)] dark:text-[var(--nous-parchment)] whitespace-nowrap"
                            style={{
                              fontFamily: 'var(--nous-font-mono)',
                              letterSpacing: '0.04em',
                            }}
                          >
                            {tag}
                          </span>
                        ))}
                        {messageCount > 0 && (
                          <span
                            className="inline-flex items-center px-1.5 py-px bg-[var(--nous-bg-2)] dark:bg-[var(--nous-nyx)] border border-[var(--nous-border-1)] dark:border-[var(--nous-shade)] rounded-[3px] text-[9px] text-[var(--nous-fg-2)] dark:text-[var(--nous-parchment)] whitespace-nowrap"
                            style={{
                              fontFamily: 'var(--nous-font-mono)',
                              letterSpacing: '0.04em',
                            }}
                          >
                            {messageCount}
                          </span>
                        )}
                      </div>
                      <span
                        className="text-[9px] text-[var(--nous-fg-3)] shrink-0"
                        style={{
                          fontFamily: 'var(--nous-font-mono)',
                          letterSpacing: '0.04em',
                        }}
                      >
                        {timeStr}
                      </span>
                    </div>
                  </button>

                  {/* Hover actions */}
                  {!selectMode && (onRename || onDelete) && (
                    <div className="absolute right-1.5 top-2 hidden group-hover/row:flex group-focus-within/row:flex items-center gap-0.5 bg-[var(--nous-bg-2)] dark:bg-[var(--nous-obsidian)] border border-[var(--nous-border-1)] dark:border-[var(--nous-shade)] rounded-md px-0.5 py-0.5 shadow-sm">
                      {onRename && (
                        <button
                          type="button"
                          aria-label={`Rename ${conv.title}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            onRename(conv.id);
                          }}
                          className="p-1 rounded hover:bg-[var(--nous-sol)]/8 text-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)] transition-colors"
                        >
                          <Pencil className="w-2.5 h-2.5" />
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
                          className="p-1 rounded hover:bg-[var(--nous-mars)]/10 text-[var(--nous-fg-3)] hover:text-[var(--nous-mars)] transition-colors"
                        >
                          <Trash2 className="w-2.5 h-2.5" />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}

        {sections.length === 0 && (
          <div className="px-4 py-8 text-center">
            <MessageSquare className="w-6 h-6 text-[var(--nous-fg-3)]/40 mx-auto mb-2" />
            <p
              className="text-[11px] text-[var(--nous-fg-3)]"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              {searchQuery ? 'No matching threads' : 'No conversations yet'}
            </p>
          </div>
        )}
      </div>
    </aside>
  );
});
