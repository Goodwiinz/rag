'use client';

import React, { memo, useMemo, useCallback, useRef } from 'react';
import { VariableSizeList as List } from 'react-window';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import {
  MessageSquare,
  MoreVertical,
  Trash2,
  Share,
  Bookmark,
  BookmarkCheck,
  Edit,
  Copy,
  Download,
  Clock,
  Archive,
  Tag,
  X,
} from 'lucide-react';
import type { Conversation } from './ConversationSidebar';

// ============================================================================
// Types
// ============================================================================

type VirtualizedItem =
  | { type: 'header'; label: string; count: number }
  | { type: 'conversation'; data: Conversation };

interface VirtualizedConversationListProps {
  groupedConversations: Record<string, Conversation[]>;
  activeConversationId?: string;
  isSelectMode: boolean;
  selectedIds: Set<string>;
  containerHeight: number;
  onConversationSelect: (id: string) => void;
  onToggleSelection?: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string, title: string) => void;
  onToggleBookmark: (id: string) => void;
  onArchiveConversation: (id: string) => void;
  onShareConversation: (id: string) => void;
  onExportConversation: (id: string) => void;
  onDuplicateConversation: (id: string) => void;
  onTagConversation: (id: string) => void;
}

interface ItemData {
  items: VirtualizedItem[];
  activeConversationId?: string;
  isSelectMode: boolean;
  selectedIds: Set<string>;
  editingId: string | null;
  editingTitle: string;
  setEditingId: (id: string | null) => void;
  setEditingTitle: (title: string) => void;
  onConversationSelect: (id: string) => void;
  onToggleSelection?: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string, title: string) => void;
  onToggleBookmark: (id: string) => void;
  onArchiveConversation: (id: string) => void;
  onShareConversation: (id: string) => void;
  onExportConversation: (id: string) => void;
  onDuplicateConversation: (id: string) => void;
  onTagConversation: (id: string) => void;
}

// ============================================================================
// Constants
// ============================================================================

const HEADER_HEIGHT = 36;
const ITEM_HEIGHT = 100;
const VIRTUALIZATION_THRESHOLD = 50;
const OVERSCAN_COUNT = 5;

// ============================================================================
// Utility Functions
// ============================================================================

function flattenGroupedConversations(
  groupedConversations: Record<string, Conversation[]>
): VirtualizedItem[] {
  const items: VirtualizedItem[] = [];
  const groupOrder = ['Today', 'Yesterday', 'This Week', 'This Month', 'Older'];

  for (const group of groupOrder) {
    const convs = groupedConversations[group];
    if (convs && convs.length > 0) {
      items.push({ type: 'header', label: group, count: convs.length });
      for (const conv of convs) {
        items.push({ type: 'conversation', data: conv });
      }
    }
  }

  return items;
}

function formatMessagePreview(content: string, maxLength = 50): string {
  return content.length > maxLength ? content.substring(0, maxLength) + '...' : content;
}

function formatDate(timestamp: number): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);

  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return date.toLocaleDateString();
}

// ============================================================================
// Group Header Component
// ============================================================================

const GroupHeader = memo<{ label: string; count: number }>(({ label, count }) => (
  <div className="px-4 pt-3 pb-1">
    <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
      {label} ({count})
    </h3>
  </div>
));

GroupHeader.displayName = 'GroupHeader';

// ============================================================================
// Conversation Item Component
// ============================================================================

const ConversationItem = memo<{
  conversation: Conversation;
  isActive: boolean;
  isSelectMode: boolean;
  isSelected: boolean;
  isEditing: boolean;
  editingTitle: string;
  setEditingId: (id: string | null) => void;
  setEditingTitle: (title: string) => void;
  onSelect: (id: string) => void;
  onToggleSelection?: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onToggleBookmark: (id: string) => void;
  onArchive: (id: string) => void;
  onShare: (id: string) => void;
  onExport: (id: string) => void;
  onDuplicate: (id: string) => void;
  onTag: (id: string) => void;
}>(({
  conversation,
  isActive,
  isSelectMode,
  isSelected,
  isEditing,
  editingTitle,
  setEditingId,
  setEditingTitle,
  onSelect,
  onToggleSelection,
  onDelete,
  onRename,
  onToggleBookmark,
  onArchive,
  onShare,
  onExport,
  onDuplicate,
  onTag,
}) => {
  const lastMessage = conversation.messages[conversation.messages.length - 1];
  const messageCount = conversation.messages.length;

  // Ref to prevent duplicate save calls (Enter + blur both trigger save)
  const savingRef = useRef(false);

  const handleClick = useCallback(() => {
    if (isSelectMode && onToggleSelection) {
      onToggleSelection(conversation.id);
    } else {
      onSelect(conversation.id);
    }
  }, [isSelectMode, onToggleSelection, onSelect, conversation.id]);

  const handleRename = useCallback(() => {
    setEditingId(conversation.id);
    setEditingTitle(conversation.title);
    savingRef.current = false; // Reset flag when starting rename
  }, [conversation.id, conversation.title, setEditingId, setEditingTitle]);

  const saveRename = useCallback(() => {
    // Prevent duplicate calls (e.g., Enter key + blur)
    if (savingRef.current) return;
    savingRef.current = true;

    if (editingTitle.trim()) {
      onRename(conversation.id, editingTitle.trim());
    }
    setEditingId(null);
    setEditingTitle('');

    // Reset flag after a short delay to allow next rename
    setTimeout(() => {
      savingRef.current = false;
    }, 100);
  }, [conversation.id, editingTitle, onRename, setEditingId, setEditingTitle]);

  return (
    <div
      className={cn(
        "group relative p-3 mx-4 rounded-lg border cursor-pointer",
        "transition-colors duration-150",
        "hover:border-orange-200 hover:bg-orange-50/50",
        isActive && "border-orange-500 bg-orange-50/80",
        isSelectMode && isSelected && "bg-accent/50 border-accent"
      )}
      onClick={handleClick}
    >
      {/* Selection Checkbox */}
      {isSelectMode && (
        <div className="absolute left-2 top-1/2 -translate-y-1/2 z-10">
          <Checkbox
            checked={isSelected}
            onCheckedChange={() => onToggleSelection?.(conversation.id)}
            onClick={(e) => e.stopPropagation()}
            className="mr-2"
          />
        </div>
      )}

      {/* Action Menu */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
          <Button
            variant="ghost"
            size="sm"
            className="absolute right-2 top-2 h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <MoreVertical className="w-3 h-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleRename(); }}>
            <Edit className="w-4 h-4 mr-2" />
            Rename
          </DropdownMenuItem>
          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onDuplicate(conversation.id); }}>
            <Copy className="w-4 h-4 mr-2" />
            Duplicate
          </DropdownMenuItem>
          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onTag(conversation.id); }}>
            <Tag className="w-4 h-4 mr-2" />
            Edit Tags
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onToggleBookmark(conversation.id); }}>
            {conversation.isBookmarked ? (
              <BookmarkCheck className="w-4 h-4 mr-2" />
            ) : (
              <Bookmark className="w-4 h-4 mr-2" />
            )}
            {conversation.isBookmarked ? 'Remove Bookmark' : 'Bookmark'}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onShare(conversation.id); }}>
            <Share className="w-4 h-4 mr-2" />
            Share
          </DropdownMenuItem>
          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onExport(conversation.id); }}>
            <Download className="w-4 h-4 mr-2" />
            Export
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onArchive(conversation.id); }}>
            <Archive className="w-4 h-4 mr-2" />
            Archive
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={(e) => { e.stopPropagation(); onDelete(conversation.id); }}
            className="text-red-600"
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Content */}
      <div className={cn("space-y-1 pr-6", isSelectMode && "pl-7")}>
        <div className="flex items-center gap-2">
          {isEditing ? (
            <Input
              value={editingTitle}
              onChange={(e) => setEditingTitle(e.target.value)}
              onBlur={saveRename}
              onKeyDown={(e) => {
                if (e.key === 'Enter') saveRename();
                if (e.key === 'Escape') {
                  setEditingId(null);
                  setEditingTitle('');
                }
              }}
              className="h-6 text-sm"
              autoFocus
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <h3 className="text-sm font-medium truncate flex-1">
              {conversation.title}
            </h3>
          )}
          {conversation.isBookmarked && (
            <BookmarkCheck className="w-3 h-3 text-orange-500 fill-current flex-shrink-0" />
          )}
          {conversation.shareUrl && (
            <Share className="w-3 h-3 text-blue-500 flex-shrink-0" />
          )}
        </div>

        {lastMessage && (
          <p className="text-xs text-muted-foreground truncate">
            {lastMessage.role === 'user' ? 'You: ' : 'Assistant: '}
            {formatMessagePreview(lastMessage.content)}
          </p>
        )}

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1">
              <MessageSquare className="w-3 h-3" />
              {messageCount}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDate(conversation.updatedAt)}
            </span>
          </div>
          {conversation.modelId && (
            <Badge variant="secondary" className="text-[10px] px-1 py-0">
              {conversation.modelId.split('-')[0]}
            </Badge>
          )}
        </div>

        {/* Tags - truncated to max 3 with fixed height */}
        {conversation.tags && conversation.tags.length > 0 && (
          <div className="flex gap-1 flex-wrap mt-1 max-h-5 overflow-hidden">
            {conversation.tags.slice(0, 3).map((tag, idx) => (
              <Badge key={idx} variant="outline" className="text-[10px] px-1 py-0">
                {tag}
              </Badge>
            ))}
            {conversation.tags.length > 3 && (
              <Badge variant="outline" className="text-[10px] px-1 py-0">
                +{conversation.tags.length - 3}
              </Badge>
            )}
          </div>
        )}
      </div>
    </div>
  );
});

ConversationItem.displayName = 'ConversationItem';

// ============================================================================
// Row Renderer
// ============================================================================

const RowRenderer = memo<{
  index: number;
  style: React.CSSProperties;
  data: ItemData;
}>(({ index, style, data }) => {
  const item = data.items[index];

  if (item.type === 'header') {
    return (
      <div style={style}>
        <GroupHeader label={item.label} count={item.count} />
      </div>
    );
  }

  const conversation = item.data;
  const isActive = conversation.id === data.activeConversationId;
  const isSelected = data.selectedIds.has(conversation.id);
  const isEditing = data.editingId === conversation.id;

  return (
    <div style={style}>
      <ConversationItem
        conversation={conversation}
        isActive={isActive}
        isSelectMode={data.isSelectMode}
        isSelected={isSelected}
        isEditing={isEditing}
        editingTitle={data.editingTitle}
        setEditingId={data.setEditingId}
        setEditingTitle={data.setEditingTitle}
        onSelect={data.onConversationSelect}
        onToggleSelection={data.onToggleSelection}
        onDelete={data.onDeleteConversation}
        onRename={data.onRenameConversation}
        onToggleBookmark={data.onToggleBookmark}
        onArchive={data.onArchiveConversation}
        onShare={data.onShareConversation}
        onExport={data.onExportConversation}
        onDuplicate={data.onDuplicateConversation}
        onTag={data.onTagConversation}
      />
    </div>
  );
});

RowRenderer.displayName = 'RowRenderer';

// ============================================================================
// Non-Virtualized List (for small datasets)
// ============================================================================

const NonVirtualizedList = memo<{
  items: VirtualizedItem[];
  itemData: ItemData;
}>(({ items, itemData }) => (
  <div className="p-4 space-y-2">
    {items.map((item, index) => {
      if (item.type === 'header') {
        return (
          <div key={`header-${item.label}`} className={index > 0 ? 'mt-4' : ''}>
            <GroupHeader label={item.label} count={item.count} />
          </div>
        );
      }

      const conversation = item.data;
      const isActive = conversation.id === itemData.activeConversationId;
      const isSelected = itemData.selectedIds.has(conversation.id);
      const isEditing = itemData.editingId === conversation.id;

      return (
        <ConversationItem
          key={conversation.id}
          conversation={conversation}
          isActive={isActive}
          isSelectMode={itemData.isSelectMode}
          isSelected={isSelected}
          isEditing={isEditing}
          editingTitle={itemData.editingTitle}
          setEditingId={itemData.setEditingId}
          setEditingTitle={itemData.setEditingTitle}
          onSelect={itemData.onConversationSelect}
          onToggleSelection={itemData.onToggleSelection}
          onDelete={itemData.onDeleteConversation}
          onRename={itemData.onRenameConversation}
          onToggleBookmark={itemData.onToggleBookmark}
          onArchive={itemData.onArchiveConversation}
          onShare={itemData.onShareConversation}
          onExport={itemData.onExportConversation}
          onDuplicate={itemData.onDuplicateConversation}
          onTag={itemData.onTagConversation}
        />
      );
    })}
  </div>
));

NonVirtualizedList.displayName = 'NonVirtualizedList';

// ============================================================================
// Main Component
// ============================================================================

export const VirtualizedConversationList = memo<VirtualizedConversationListProps>(({
  groupedConversations,
  activeConversationId,
  isSelectMode,
  selectedIds,
  containerHeight,
  onConversationSelect,
  onToggleSelection,
  onDeleteConversation,
  onRenameConversation,
  onToggleBookmark,
  onArchiveConversation,
  onShareConversation,
  onExportConversation,
  onDuplicateConversation,
  onTagConversation,
}) => {
  const listRef = useRef<List<ItemData>>(null);
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [editingTitle, setEditingTitle] = React.useState('');

  // Flatten grouped conversations into a single list with headers
  const flatItems = useMemo(
    () => flattenGroupedConversations(groupedConversations),
    [groupedConversations]
  );

  // Count total conversations (excluding headers)
  const totalConversations = useMemo(
    () => flatItems.filter(item => item.type === 'conversation').length,
    [flatItems]
  );

  // Memoize item data to prevent re-renders
  const itemData = useMemo<ItemData>(() => ({
    items: flatItems,
    activeConversationId,
    isSelectMode,
    selectedIds,
    editingId,
    editingTitle,
    setEditingId,
    setEditingTitle,
    onConversationSelect,
    onToggleSelection,
    onDeleteConversation,
    onRenameConversation,
    onToggleBookmark,
    onArchiveConversation,
    onShareConversation,
    onExportConversation,
    onDuplicateConversation,
    onTagConversation,
  }), [
    flatItems,
    activeConversationId,
    isSelectMode,
    selectedIds,
    editingId,
    editingTitle,
    onConversationSelect,
    onToggleSelection,
    onDeleteConversation,
    onRenameConversation,
    onToggleBookmark,
    onArchiveConversation,
    onShareConversation,
    onExportConversation,
    onDuplicateConversation,
    onTagConversation,
  ]);

  // Get item size based on type (header vs conversation)
  const getItemSize = useCallback((index: number) => {
    const item = flatItems[index];
    return item.type === 'header' ? HEADER_HEIGHT : ITEM_HEIGHT;
  }, [flatItems]);

  // Empty state
  if (flatItems.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center">
          <MessageSquare className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-sm text-muted-foreground">No conversations yet</p>
        </div>
      </div>
    );
  }

  // Use non-virtualized rendering for small lists
  if (totalConversations < VIRTUALIZATION_THRESHOLD) {
    return (
      <div className="flex-1 overflow-auto">
        <NonVirtualizedList items={flatItems} itemData={itemData} />
      </div>
    );
  }

  // Virtualized list for large datasets
  return (
    <List
      ref={listRef}
      height={containerHeight}
      width="100%"
      itemCount={flatItems.length}
      itemSize={getItemSize}
      itemData={itemData}
      overscanCount={OVERSCAN_COUNT}
      className="scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100"
    >
      {RowRenderer}
    </List>
  );
});

VirtualizedConversationList.displayName = 'VirtualizedConversationList';

export default VirtualizedConversationList;
