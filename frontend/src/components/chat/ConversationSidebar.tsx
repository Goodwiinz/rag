'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Checkbox } from '@/components/ui/checkbox';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageSquare,
  Plus,
  Search,
  Filter,
  MoreVertical,
  Trash2,
  Share,
  Bookmark,
  BookmarkCheck,
  Edit,
  Copy,
  Download,
  Star,
  Clock,
  Calendar,
  Hash,
  ChevronDown,
  X,
  Folder,
  FolderOpen,
  Archive,
  Tag,
  Users,
  Bot,
  User,
  CheckSquare,
  CheckCircle,
} from 'lucide-react';

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
  selectedIds = new Set(),
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
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [tagDialogOpen, setTagDialogOpen] = useState(false);
  const [tagConversationId, setTagConversationId] = useState<string | null>(null);
  const [newTags, setNewTags] = useState<string[]>([]);

  // Filter and sort conversations
  const filteredConversations = useMemo(() => {
    let filtered = conversations.filter(conv => {
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

  const formatMessagePreview = (content: string, maxLength = 50) => {
    return content.length > maxLength ? content.substring(0, maxLength) + '...' : content;
  };

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  const handleRename = (id: string) => {
    const conv = conversations.find(c => c.id === id);
    if (conv) {
      setEditingId(id);
      setEditingTitle(conv.title);
    }
  };

  const saveRename = () => {
    if (editingId && editingTitle.trim()) {
      onRenameConversation(editingId, editingTitle.trim());
      setEditingId(null);
      setEditingTitle('');
    }
  };

  const handleTagDialog = (id: string) => {
    const conv = conversations.find(c => c.id === id);
    if (conv) {
      setTagConversationId(id);
      setNewTags(conv.tags || []);
      setTagDialogOpen(true);
    }
  };

  const saveTags = () => {
    if (tagConversationId) {
      onTagConversation(tagConversationId, newTags);
      setTagDialogOpen(false);
      setTagConversationId(null);
      setNewTags([]);
    }
  };

  const ConversationItem = ({ conversation }: { conversation: Conversation }) => {
    const isActive = conversation.id === activeConversationId;
    const lastMessage = conversation.messages[conversation.messages.length - 1];
    const messageCount = conversation.messages.length;

    return (
      <motion.div
        layout
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className={cn(
          "group relative p-3 rounded-lg border cursor-pointer transition-all",
          "hover:border-orange-200 hover:bg-orange-50/50",
          isActive && "border-orange-500 bg-orange-50/80",
          isSelectMode && selectedIds.has(conversation.id) && "bg-accent/50 border-accent"
        )}
        onClick={() => {
          if (isSelectMode && onToggleSelection) {
            onToggleSelection(conversation.id);
          } else {
            onConversationSelect(conversation.id);
          }
        }}
      >
        {/* Selection Checkbox */}
        {isSelectMode && (
          <div className="absolute left-2 top-1/2 -translate-y-1/2 z-10">
            <Checkbox
              checked={selectedIds.has(conversation.id)}
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
              className="absolute right-2 top-2 h-6 w-6 p-0 opacity-0 group-hover:opacity-100"
            >
              <MoreVertical className="w-3 h-3" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleRename(conversation.id); }}>
              <Edit className="w-4 h-4 mr-2" />
              Rename
            </DropdownMenuItem>
            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onDuplicateConversation(conversation.id); }}>
              <Copy className="w-4 h-4 mr-2" />
              Duplicate
            </DropdownMenuItem>
            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleTagDialog(conversation.id); }}>
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
            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onShareConversation(conversation.id); }}>
              <Share className="w-4 h-4 mr-2" />
              Share
            </DropdownMenuItem>
            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onExportConversation(conversation.id); }}>
              <Download className="w-4 h-4 mr-2" />
              Export
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onArchiveConversation(conversation.id); }}>
              <Archive className="w-4 h-4 mr-2" />
              Archive
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={(e) => { e.stopPropagation(); onDeleteConversation(conversation.id); }}
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
            {editingId === conversation.id ? (
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
              <BookmarkCheck className="w-3 h-3 text-orange-500 fill-current" />
            )}
            {conversation.shareUrl && (
              <Share className="w-3 h-3 text-blue-500" />
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

          {/* Tags */}
          {conversation.tags && conversation.tags.length > 0 && (
            <div className="flex gap-1 flex-wrap mt-2">
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
      </motion.div>
    );
  };

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
            <Button variant="destructive" size="sm" onClick={onBulkDelete}>
              <Trash2 className="h-4 w-4 mr-1" />
              Delete
            </Button>
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

      {/* Conversation List */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-4">
          {Object.entries(groupedConversations).map(([group, convs]) => (
            <div key={group}>
              <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                {group} ({convs.length})
              </h3>
              <div className="space-y-2">
                <AnimatePresence>
                  {convs.map((conv) => (
                    <ConversationItem key={conv.id} conversation={conv} />
                  ))}
                </AnimatePresence>
              </div>
            </div>
          ))}

          {filteredConversations.length === 0 && (
            <div className="text-center py-8">
              <MessageSquare className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-sm text-muted-foreground">
                {searchQuery ? 'No conversations found' : 'No conversations yet'}
              </p>
            </div>
          )}
        </div>
      </ScrollArea>

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
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-4 w-4 p-0 ml-1 hover:bg-transparent"
                    onClick={() => setNewTags(newTags.filter(t => t !== tag))}
                  >
                    <X className="w-3 h-3" />
                  </Button>
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