'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { IconButtonSm } from '@/components/ui/icon-button';
import { DeleteConfirmDialog } from '@/components/ui/confirm-dialog';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import {
    Archive,
    Calendar,
    CheckCircle,
    CheckSquare,
    ChevronDown,
    Filter,
    Folder,
    FolderOpen,
    MessageSquare,
    Plus,
    Search,
    Trash2,
    X,
} from 'lucide-react';
import React, { useCallback, useMemo, useRef, useState } from 'react';
import { VirtualizedConversationList } from './VirtualizedConversationList';

export interface Conversation {
  id: string;
  title: string;
  messages: Array<{
    role: 'user' | 'assistant';
    content: string;
    timestamp: number;
  }>;
  modelId?: string;
  tags?: string[];
  isBookmarked?: boolean;
  isArchived?: boolean;
  folderId?: string;
  createdAt: number;
  updatedAt: number;
  shareUrl?: string;
}

export interface Folder {
  id: string;
  name: string;
  color?: string;
  conversationIds: string[];
}

// Stable empty Set to avoid creating new instances on every render
const EMPTY_SELECTION = new Set<string>();

interface ConversationSidebarProps {
  conversations: Conversation[];
  activeConversationId?: string;
  onConversationSelect: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string, title: string) => void;
  onToggleBookmark: (id: string) => void;
  onArchiveConversation: (id: string) => void;
  onShareConversation: (id: string) => void;
  onExportConversation: (id: string) => void;
  onDuplicateConversation: (id: string) => void;
  onTagConversation: (id: string, tags: string[]) => void;
  onMoveConversation: (id: string, folderId?: string) => void;
  folders?: Folder[];
  onCreateFolder: (name: string) => void;
  onDeleteFolder: (id: string) => void;
  className?: string;
  isOpen?: boolean;
  onToggle?: () => void;
  // Bulk selection props
  isSelectMode?: boolean;
  selectedIds?: Set<string>;
  onToggleSelectMode?: () => void;
  onToggleSelection?: (id: string) => void;
  onSelectAll?: () => void;
  onClearSelection?: () => void;
  onBulkResolve?: () => void;
  onBulkArchive?: () => void;
  onBulkDelete?: () => void;
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  onConversationSelect,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
  onToggleBookmark,
  onArchiveConversation,
  onShareConversation,
  onExportConversation,
  onDuplicateConversation,
  onTagConversation,
  onMoveConversation,
  folders = [],
  onCreateFolder,
  onDeleteFolder,
  className,
  isOpen = true,
  onToggle,
  // Bulk selection props
  isSelectMode = false,
  selectedIds = EMPTY_SELECTION,
  onToggleSelectMode,
  onToggleSelection,
  onSelectAll,
  onClearSelection,
  onBulkResolve,
  onBulkArchive,
  onBulkDelete,
}: ConversationSidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'bookmarked' | 'recent' | 'archived'>('all');
  const [sortBy, setSortBy] = useState<'updated' | 'created' | 'title' | 'messages'>('updated');
  const [showArchived, setShowArchived] = useState(false);
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
  const [tagDialogOpen, setTagDialogOpen] = useState(false);
  const [tagConversationId, setTagConversationId] = useState<string | null>(null);
  const [newTags, setNewTags] = useState<string[]>([]);

  // Filter and sort conversations
  const filteredConversations = useMemo(() => {
    const filtered = conversations.filter(conv => {
      // Filter by archived status
      if (!showArchived && conv.isArchived) return false;
      if (showArchived && !conv.isArchived) return false;

      // Filter by folder
      if (selectedFolder && conv.folderId !== selectedFolder) return false;

      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        return (
          conv.title.toLowerCase().includes(query) ||
          conv.messages.some(msg => msg.content.toLowerCase().includes(query))
        );
      }

      // Type filter
      if (filterType === 'bookmarked' && !conv.isBookmarked) return false;
      if (filterType === 'recent') {
        const dayAgo = Date.now() - 24 * 60 * 60 * 1000;
        return conv.updatedAt > dayAgo;
      }

      return true;
    });

    // Sort
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'updated':
          return b.updatedAt - a.updatedAt;
        case 'created':
          return b.createdAt - a.createdAt;
        case 'title':
          return a.title.localeCompare(b.title);
        case 'messages':
          return b.messages.length - a.messages.length;
        default:
          return 0;
      }
    });

    return filtered;
  }, [conversations, searchQuery, filterType, sortBy, showArchived, selectedFolder]);

  // Group conversations by date
  const groupedConversations = useMemo(() => {
    const groups: { [key: string]: typeof filteredConversations } = {};

    filteredConversations.forEach(conv => {
      const date = new Date(conv.updatedAt);
      const now = new Date();
      const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

      let group: string;
      if (diffDays === 0) group = 'Today';
      else if (diffDays === 1) group = 'Yesterday';
      else if (diffDays < 7) group = 'This Week';
      else if (diffDays < 30) group = 'This Month';
      else group = 'Older';

      if (!groups[group]) groups[group] = [];
      groups[group].push(conv);
    });

    return groups;
  }, [filteredConversations]);

  const saveTags = () => {
    if (tagConversationId) {
      onTagConversation(tagConversationId, newTags);
      setTagDialogOpen(false);
      setTagConversationId(null);
      setNewTags([]);
    }
  };

  // Ref for measuring container height for virtualization
  const listContainerRef = useRef<HTMLDivElement>(null);
  const [containerHeight, setContainerHeight] = useState(400);

  // Measure container height for virtualized list using ResizeObserver
  // More accurate than window.resize - catches sidebar, toolbar, font size changes
  React.useEffect(() => {
    const container = listContainerRef.current;
    if (!container) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const height = entry.contentRect.height;
        setContainerHeight(height);
      }
    });

    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, []);

  // Callback for opening tag dialog from virtualized list
  const handleOpenTagDialog = useCallback((id: string) => {
    const conv = conversations.find(c => c.id === id);
    if (conv) {
      setTagConversationId(id);
      setNewTags(conv.tags || []);
      setTagDialogOpen(true);
    }
  }, [conversations]);

  return (
    <div className={cn("flex flex-col bg-background border-r", className)}>
      {/* Header */}
      <div className="p-4 border-b space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <MessageSquare className="w-5 h-5" />
            Conversations
          </h2>
          <div className="flex items-center gap-1">
            {onToggleSelectMode && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onToggleSelectMode}
                className={cn(isSelectMode && "bg-accent")}
                title={isSelectMode ? "Exit select mode" : "Select multiple"}
              >
                <CheckSquare className="w-4 h-4" />
              </Button>
            )}
            {onToggle && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onToggle}
                className="lg:hidden"
              >
                <X className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>

        {/* New Chat Button */}
        <Button onClick={onNewConversation} className="w-full">
          <Plus className="w-4 h-4 mr-2" />
          New Conversation
        </Button>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="flex-1">
                <Filter className="w-4 h-4 mr-2" />
                {filterType === 'all' ? 'All' :
                 filterType === 'bookmarked' ? 'Bookmarked' :
                 filterType === 'recent' ? 'Recent' : 'Archived'}
                <ChevronDown className="w-3 h-3 ml-auto" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={() => setFilterType('all')}>
                All Conversations
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setFilterType('bookmarked')}>
                Bookmarked
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setFilterType('recent')}>
                Recent
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => setShowArchived(!showArchived)}>
                {showArchived ? 'Hide' : 'Show'} Archived
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Calendar className="w-4 h-4 mr-2" />
                Sort
                <ChevronDown className="w-3 h-3 ml-1" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={() => setSortBy('updated')}>
                Last Updated
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setSortBy('created')}>
                Created Date
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setSortBy('title')}>
                Title
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setSortBy('messages')}>
                Message Count
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Bulk Action Toolbar */}
      {isSelectMode && selectedIds.size > 0 && (
        <div className="flex items-center gap-2 px-4 py-2 border-b bg-muted/50">
          <span className="text-sm text-muted-foreground">
            {selectedIds.size} selected
          </span>
          <div className="flex-1" />
          {onSelectAll && (
            <Button variant="ghost" size="sm" onClick={onSelectAll}>
              Select All
            </Button>
          )}
          {onClearSelection && (
            <Button variant="ghost" size="sm" onClick={onClearSelection}>
              Clear
            </Button>
          )}
          <Separator orientation="vertical" className="h-4" />
          {onBulkResolve && (
            <Button variant="ghost" size="sm" onClick={onBulkResolve}>
              <CheckCircle className="h-4 w-4 mr-1" />
              Resolve
            </Button>
          )}
          {onBulkArchive && (
            <Button variant="ghost" size="sm" onClick={onBulkArchive}>
              <Archive className="h-4 w-4 mr-1" />
              Archive
            </Button>
          )}
          {onBulkDelete && (
            <DeleteConfirmDialog
              itemName={`${selectedIds.size} thread${selectedIds.size > 1 ? 's' : ''}`}
              onConfirm={onBulkDelete}
            >
              <Button variant="destructive" size="sm">
                <Trash2 className="h-4 w-4 mr-1" />
                Delete
              </Button>
            </DeleteConfirmDialog>
          )}
        </div>
      )}

      {/* Folder Navigation */}
      {folders.length > 0 && (
        <div className="px-4 py-2 border-b">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-muted-foreground">Folders</h3>
            <Button variant="ghost" size="sm" onClick={() => onCreateFolder('New Folder')}>
              <Plus className="w-3 h-3" />
            </Button>
          </div>
          <div className="space-y-1">
            <Button
              variant={!selectedFolder ? "secondary" : "ghost"}
              size="sm"
              className="w-full justify-start"
              onClick={() => setSelectedFolder(null)}
            >
              <MessageSquare className="w-3 h-3 mr-2" />
              All Conversations
            </Button>
            {folders.map(folder => (
              <Button
                key={folder.id}
                variant={selectedFolder === folder.id ? "secondary" : "ghost"}
                size="sm"
                className="w-full justify-start"
                onClick={() => setSelectedFolder(folder.id)}
              >
                {folder.conversationIds.length > 0 ? (
                  <FolderOpen className="w-3 h-3 mr-2" />
                ) : (
                  <Folder className="w-3 h-3 mr-2" />
                )}
                {folder.name}
                <Badge variant="outline" className="ml-auto text-xs">
                  {folder.conversationIds.length}
                </Badge>
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Conversation List - Virtualized for performance */}
      <div ref={listContainerRef} className="flex-1 overflow-hidden">
        <VirtualizedConversationList
          groupedConversations={groupedConversations}
          activeConversationId={activeConversationId}
          isSelectMode={isSelectMode}
          selectedIds={selectedIds}
          containerHeight={containerHeight}
          onConversationSelect={onConversationSelect}
          onToggleSelection={onToggleSelection}
          onDeleteConversation={onDeleteConversation}
          onRenameConversation={onRenameConversation}
          onToggleBookmark={onToggleBookmark}
          onArchiveConversation={onArchiveConversation}
          onShareConversation={onShareConversation}
          onExportConversation={onExportConversation}
          onDuplicateConversation={onDuplicateConversation}
          onTagConversation={handleOpenTagDialog}
        />
      </div>

      {/* Tag Dialog */}
      <Dialog open={tagDialogOpen} onOpenChange={setTagDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Tags</DialogTitle>
            <DialogDescription>
              Add or remove tags to organize your conversations
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Input
                placeholder="Add a tag..."
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.currentTarget.value) {
                    const tag = e.currentTarget.value.trim();
                    if (tag && !newTags.includes(tag)) {
                      setNewTags([...newTags, tag]);
                    }
                    e.currentTarget.value = '';
                  }
                }}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {newTags.map((tag, idx) => (
                <Badge key={idx} variant="secondary" className="pr-1">
                  {tag}
                  <IconButtonSm
                    icon={<X className="w-3 h-3" />}
                    label="Remove tag"
                    onClick={() => setNewTags(newTags.filter(t => t !== tag))}
                    className="h-4 w-4 ml-1 hover:bg-transparent"
                  />
                </Badge>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTagDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={saveTags}>Save Tags</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default ConversationSidebar;