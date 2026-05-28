'use client';

/**
 * ProjectChatTab Component
 * Main tab in project detail view for managing linked chat threads
 *
 * Features:
 * - List of linked threads with ThreadCard components
 * - Start new chat from project context
 * - Empty state when no threads linked
 * - Loading and error states
 * - Responsive grid layout
 */

import React, { useEffect, useState } from 'react';
import {
  MessageSquare,
  Plus,
  Loader2,
  AlertCircle,
  RefreshCw,
  Link2,
} from 'lucide-react';
import { useProjectChat } from '@/hooks/useProjectChat';
import { ThreadCard } from './ThreadCard';
import { StartChatModal } from './StartChatModal';
import { LinkThreadModal } from './LinkThreadModal';
import { SaveToNoteModal } from './SaveToNoteModal';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

export interface ProjectChatTabProps {
  projectId: string;
}

export const ProjectChatTab: React.FC<ProjectChatTabProps> = ({
  projectId,
}) => {
  const {
    threads,
    isLoading,
    error,
    startChat,
    linkThread,
    unlinkThread,
    saveToNote,
    refreshThreads,
    clearError,
  } = useProjectChat(projectId);

  // Modal state management
  const [isStartChatModalOpen, setIsStartChatModalOpen] = useState(false);
  const [isLinkThreadModalOpen, setIsLinkThreadModalOpen] = useState(false);
  const [isSaveToNoteModalOpen, setIsSaveToNoteModalOpen] = useState(false);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [projectWorkspaceId, setProjectWorkspaceId] = useState<string | null>(
    null
  );

  // Unlink confirmation dialog
  const [unlinkDialogOpen, setUnlinkDialogOpen] = useState(false);
  const [threadToUnlink, setThreadToUnlink] = useState<string | null>(null);

  // Fetch threads on mount (only if projectId is valid)
  useEffect(() => {
    if (projectId && projectId !== 'undefined') {
      refreshThreads();
    }
  }, [projectId, refreshThreads]);

  // Fetch project workspace ID for LinkThreadModal
  useEffect(() => {
    async function fetchProjectWorkspace() {
      if (!projectId || projectId === 'undefined') return;
      try {
        const { projectService } = await import('@/services/projectService');
        const project = await projectService.getProject(projectId);
        setProjectWorkspaceId(project.workspace_id);
      } catch (err) {
        console.error('Failed to fetch project workspace:', err);
      }
    }
    fetchProjectWorkspace();
  }, [projectId]);

  // Handle start chat
  const handleStartChat = async (
    initialMessage: string,
    threadTitle?: string
  ) => {
    await startChat({
      initial_message: initialMessage,
      thread_title: threadTitle,
    });
    setIsStartChatModalOpen(false);
  };

  // Handle unlink thread
  const handleUnlinkClick = (threadId: string) => {
    setThreadToUnlink(threadId);
    setUnlinkDialogOpen(true);
  };

  const confirmUnlink = async () => {
    if (threadToUnlink) {
      await unlinkThread(threadToUnlink);
      setThreadToUnlink(null);
      setUnlinkDialogOpen(false);
    }
  };

  // Handle save to note
  const handleSaveToNoteClick = (threadId: string) => {
    setSelectedThreadId(threadId);
    setIsSaveToNoteModalOpen(true);
  };

  const handleSaveToNote = async (
    noteTitle: string,
    includeCitations: boolean
  ) => {
    if (selectedThreadId) {
      await saveToNote({
        thread_id: selectedThreadId,
        note_title: noteTitle,
        include_citations: includeCitations,
      });
      setSelectedThreadId(null);
      setIsSaveToNoteModalOpen(false);
    }
  };

  // Handle link thread
  const handleLinkThread = async (threadId: string, contextNote?: string) => {
    await linkThread({ thread_id: threadId, context_note: contextNote });
    setIsLinkThreadModalOpen(false);
    refreshThreads();
  };

  // Handle retry
  const handleRetry = () => {
    clearError();
    refreshThreads();
  };

  // Loading state
  if (isLoading && threads.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-sol" />
          <p className="text-sm text-muted-foreground font-mono">
            Loading threads...
          </p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex flex-col items-center gap-4 max-w-md text-center">
          <div className="p-3 rounded-full bg-red-500/10 border border-red-500/30">
            <AlertCircle className="h-8 w-8 text-red-400" />
          </div>
          <div>
            <h3 className="text-lg font-mono font-bold text-muted-foreground mb-2">
              Failed to Load Threads
            </h3>
            <p className="text-sm text-muted-foreground font-mono mb-4">
              {error}
            </p>
            <button
              onClick={handleRetry}
              className="flex items-center gap-2 px-4 py-2 bg-sol/10 text-sol border border-sol/30 rounded font-mono text-sm hover:bg-sol/20 transition-colors mx-auto"
            >
              <RefreshCw className="h-4 w-4" />
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Empty state
  if (threads.length === 0) {
    return (
      <>
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-4 max-w-md text-center">
            <div className="p-4 rounded-full bg-[#1a1a1a] border border-[#333]">
              <MessageSquare className="h-12 w-12 text-muted-foreground" />
            </div>
            <div>
              <h3 className="text-lg font-mono font-bold text-muted-foreground mb-2">
                No Chat Threads Linked
              </h3>
              <p className="text-sm text-muted-foreground font-mono mb-4">
                Start a new chat using this project's documents as context, or
                link an existing thread.
              </p>
              <div className="flex items-center gap-3 justify-center">
                <button
                  onClick={() => setIsStartChatModalOpen(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-sol/10 text-sol border border-sol/30 rounded font-mono text-sm hover:bg-sol/20 transition-colors"
                >
                  <Plus className="h-4 w-4" />
                  Start Chat
                </button>
                <button
                  onClick={() => setIsLinkThreadModalOpen(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/30 rounded font-mono text-sm hover:bg-brand-cyan/20 transition-colors"
                >
                  <Link2 className="h-4 w-4" />
                  Link Existing
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Modals must be rendered even in empty state */}
        <StartChatModal
          isOpen={isStartChatModalOpen}
          onClose={() => setIsStartChatModalOpen(false)}
          onStartChat={handleStartChat}
        />

        {projectWorkspaceId && (
          <LinkThreadModal
            isOpen={isLinkThreadModalOpen}
            projectWorkspaceId={projectWorkspaceId}
            onClose={() => setIsLinkThreadModalOpen(false)}
            onLinkThread={handleLinkThread}
          />
        )}
      </>
    );
  }

  // Threads list
  return (
    <div className="space-y-4">
      {/* Header with action button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-5 w-5 text-sol" />
          <h3 className="text-lg font-mono font-bold text-muted-foreground">
            Linked Threads ({threads.length})
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsLinkThreadModalOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/30 rounded font-mono text-sm hover:bg-brand-cyan/20 transition-colors"
          >
            <Link2 className="h-4 w-4" />
            Link Existing
          </button>
          <button
            onClick={() => setIsStartChatModalOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-sol/10 text-sol border border-sol/30 rounded font-mono text-sm hover:bg-sol/20 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Start Chat
          </button>
        </div>
      </div>

      {/* Thread grid - responsive layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {threads.map((thread) => (
          <ThreadCard
            key={thread.id}
            thread={thread}
            onUnlink={handleUnlinkClick}
            onSaveToNote={handleSaveToNoteClick}
          />
        ))}
      </div>

      {/* Modals */}
      <StartChatModal
        isOpen={isStartChatModalOpen}
        onClose={() => setIsStartChatModalOpen(false)}
        onStartChat={handleStartChat}
      />

      <SaveToNoteModal
        isOpen={isSaveToNoteModalOpen}
        onClose={() => {
          setIsSaveToNoteModalOpen(false);
          setSelectedThreadId(null);
        }}
        onSave={handleSaveToNote}
      />

      {projectWorkspaceId && (
        <LinkThreadModal
          isOpen={isLinkThreadModalOpen}
          projectWorkspaceId={projectWorkspaceId}
          onClose={() => setIsLinkThreadModalOpen(false)}
          onLinkThread={handleLinkThread}
        />
      )}

      {/* Unlink confirmation dialog */}
      <AlertDialog open={unlinkDialogOpen} onOpenChange={setUnlinkDialogOpen}>
        <AlertDialogContent className="bg-[#0a0a0a] border-[#1a1a1a]">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-mono text-muted-foreground">
              Unlink Thread from Project?
            </AlertDialogTitle>
            <AlertDialogDescription className="font-mono text-muted-foreground">
              This will remove the connection between this thread and the
              project. The thread and its messages will not be deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="font-mono">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmUnlink}
              className="bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20 font-mono"
            >
              Unlink
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default ProjectChatTab;
