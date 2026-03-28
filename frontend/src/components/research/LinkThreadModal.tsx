'use client';

/**
 * LinkThreadModal Component
 * Modal for linking an existing chat thread to a project
 *
 * Features:
 * - Search/select from existing threads
 * - Optional context note
 * - Terminal Observatory theme styling
 */

import React, { useState, useEffect } from 'react';
import { Link2, X, Loader2, Search, MessageSquare, Clock } from 'lucide-react';
import { workspaceService } from '@/services/workspaceService';
import type { Thread } from '@/types/workspace';

export interface LinkThreadModalProps {
  isOpen: boolean;
  projectWorkspaceId: string;
  onClose: () => void;
  onLinkThread: (threadId: string, contextNote?: string) => Promise<void>;
}

export const LinkThreadModal: React.FC<LinkThreadModalProps> = ({
  isOpen,
  projectWorkspaceId,
  onClose,
  onLinkThread,
}) => {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [filteredThreads, setFilteredThreads] = useState<Thread[]>([]);
  const [isLoadingThreads, setIsLoadingThreads] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [contextNote, setContextNote] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch threads when modal opens
  useEffect(() => {
    if (isOpen && projectWorkspaceId) {
      fetchThreads();
    }
  }, [isOpen, projectWorkspaceId]);

  // Filter threads based on search
  useEffect(() => {
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      setFilteredThreads(
        threads.filter(
          (t) =>
            t.title?.toLowerCase().includes(query) ||
            t.id.toLowerCase().includes(query)
        )
      );
    } else {
      setFilteredThreads(threads);
    }
  }, [searchQuery, threads]);

  const fetchThreads = async () => {
    setIsLoadingThreads(true);
    setError(null);
    try {
      // Get all conversations in the workspace
      const conversationsResponse = await workspaceService.listConversations(
        projectWorkspaceId,
        { limit: 100 }
      );

      // Get threads from all conversations
      const allThreads: Thread[] = [];
      for (const conv of conversationsResponse.conversations) {
        try {
          const threadsResponse = await workspaceService.listThreads(conv.id, {
            limit: 50,
          });
          allThreads.push(...threadsResponse.threads);
        } catch (err) {
          console.warn(`Failed to fetch threads for conversation ${conv.id}`);
        }
      }

      // Sort by last activity
      allThreads.sort(
        (a, b) =>
          new Date(b.last_message_at || b.created_at).getTime() -
          new Date(a.last_message_at || a.created_at).getTime()
      );

      setThreads(allThreads);
      setFilteredThreads(allThreads);
    } catch (err) {
      console.error('Failed to fetch threads:', err);
      setError('Failed to load threads');
    } finally {
      setIsLoadingThreads(false);
    }
  };

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!selectedThreadId) {
      setError('Please select a thread to link');
      return;
    }

    setIsSubmitting(true);
    try {
      await onLinkThread(selectedThreadId, contextNote.trim() || undefined);
      // Reset form
      setSelectedThreadId(null);
      setContextNote('');
      setSearchQuery('');
      onClose();
    } catch (err: any) {
      if (err?.message?.includes('already linked')) {
        setError('This thread is already linked to this project');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to link thread');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (!isSubmitting) {
      setSelectedThreadId(null);
      setContextNote('');
      setSearchQuery('');
      setError(null);
      onClose();
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#1a1a1a] shrink-0">
          <div className="flex items-center gap-2">
            <Link2 className="h-5 w-5 text-[#D4A039]" />
            <h2 className="font-mono font-bold text-gray-200">
              Link Existing Thread
            </h2>
          </div>
          <button
            onClick={handleClose}
            disabled={isSubmitting}
            className="p-1 text-gray-500 hover:text-gray-300 transition-colors disabled:opacity-50"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
          <div className="p-4 space-y-4 overflow-y-auto flex-1">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search threads..."
                disabled={isSubmitting}
                className="w-full pl-10 pr-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-gray-200 font-mono text-sm placeholder:text-gray-600 focus:outline-none focus:border-[#D4A039]/50 disabled:opacity-50"
              />
            </div>

            {/* Thread List */}
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {isLoadingThreads ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-[#D4A039]" />
                </div>
              ) : filteredThreads.length === 0 ? (
                <div className="text-center py-8 text-gray-500 font-mono text-sm">
                  {threads.length === 0
                    ? 'No threads found in this workspace'
                    : 'No threads match your search'}
                </div>
              ) : (
                filteredThreads.map((thread) => (
                  <button
                    key={thread.id}
                    type="button"
                    onClick={() => setSelectedThreadId(thread.id)}
                    disabled={isSubmitting}
                    className={`w-full p-3 rounded border text-left transition-colors ${
                      selectedThreadId === thread.id
                        ? 'bg-[#D4A039]/10 border-[#D4A039]/50'
                        : 'bg-[#1a1a1a] border-[#333] hover:border-[#D4A039]/30'
                    } disabled:opacity-50`}
                  >
                    <div className="flex items-start gap-3">
                      <MessageSquare
                        className={`h-4 w-4 mt-0.5 shrink-0 ${
                          selectedThreadId === thread.id
                            ? 'text-[#D4A039]'
                            : 'text-gray-500'
                        }`}
                      />
                      <div className="flex-1 min-w-0">
                        <p
                          className={`font-mono text-sm truncate ${
                            selectedThreadId === thread.id
                              ? 'text-[#D4A039]'
                              : 'text-gray-200'
                          }`}
                        >
                          {thread.title || 'Untitled Thread'}
                        </p>
                        <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 font-mono">
                          <span>{thread.message_count} messages</span>
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatDate(thread.last_message_at || thread.created_at)}
                          </span>
                        </div>
                      </div>
                      {selectedThreadId === thread.id && (
                        <div className="w-2 h-2 rounded-full bg-[#D4A039] shrink-0 mt-1.5" />
                      )}
                    </div>
                  </button>
                ))
              )}
            </div>

            {/* Context Note */}
            <div>
              <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-2">
                Context Note <span className="text-gray-600">(optional)</span>
              </label>
              <textarea
                value={contextNote}
                onChange={(e) => setContextNote(e.target.value)}
                placeholder="Add a note about why this thread is linked..."
                disabled={isSubmitting}
                maxLength={500}
                className="w-full h-20 px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-gray-200 font-mono text-sm placeholder:text-gray-600 focus:outline-none focus:border-[#D4A039]/50 disabled:opacity-50 resize-none"
              />
              <p className="text-xs text-gray-600 font-mono mt-1 text-right">
                {contextNote.length}/500
              </p>
            </div>

            {/* Error Display */}
            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded text-sm font-mono text-red-400">
                {error}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 p-4 border-t border-[#1a1a1a] shrink-0">
            <button
              type="button"
              onClick={handleClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-sm font-mono text-gray-400 hover:text-gray-300 transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !selectedThreadId}
              className="flex items-center gap-2 px-4 py-2 bg-[#D4A039]/10 text-[#D4A039] border border-[#D4A039]/30 rounded font-mono text-sm hover:bg-[#D4A039]/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Linking...
                </>
              ) : (
                <>
                  <Link2 className="h-4 w-4" />
                  Link Thread
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default LinkThreadModal;
