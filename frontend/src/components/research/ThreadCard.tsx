'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  MessageSquare,
  Clock,
  FileText,
  Link2,
  Trash2,
  ExternalLink,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from '@/components/ui/card';
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
import { ProjectThread, ProjectThreadLinkType } from '@/types/project-chat';
import { formatDistanceToNow } from 'date-fns';

const linkTypeVariant: Record<
  ProjectThreadLinkType,
  'default' | 'secondary' | 'outline'
> = {
  [ProjectThreadLinkType.AUTO]: 'default',
  [ProjectThreadLinkType.MANUAL]: 'secondary',
  [ProjectThreadLinkType.FROM_CHAT]: 'outline',
};

interface ThreadCardProps {
  thread: ProjectThread;
  onSaveToNote: (threadId: string) => void;
  onUnlink: (threadId: string) => void;
}

export const ThreadCard: React.FC<ThreadCardProps> = ({
  thread,
  onSaveToNote,
  onUnlink,
}) => {
  const router = useRouter();
  const [unlinkDialogOpen, setUnlinkDialogOpen] = useState(false);

  const formatLastMessageTime = (timestamp?: string) => {
    if (!timestamp) return 'No messages yet';
    try {
      return formatDistanceToNow(new Date(timestamp), { addSuffix: true });
    } catch {
      return 'Recently';
    }
  };

  const handleTitleClick = () => {
    router.push(`/chat?conversationId=${thread.conversation_id}`);
  };

  const handleTitleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleTitleClick();
    }
  };

  const handleOpenThread = () => {
    router.push(`/chat?conversationId=${thread.conversation_id}`);
  };

  const handleSaveToNote = () => {
    onSaveToNote(thread.thread_id);
  };

  const handleConfirmUnlink = () => {
    onUnlink(thread.thread_id);
    setUnlinkDialogOpen(false);
  };

  return (
    <>
      <Card className="group hover:border-primary/40 transition-colors">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-3">
            <h3
              role="button"
              tabIndex={0}
              onClick={handleTitleClick}
              onKeyDown={handleTitleKeyDown}
              className="text-base font-semibold text-foreground cursor-pointer hover:text-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded truncate"
            >
              {thread.thread_title}
            </h3>
            <Badge variant={linkTypeVariant[thread.link_type]} className="text-[10px] shrink-0">
              {thread.link_type}
            </Badge>
          </div>

          <div className="flex items-center gap-4 text-xs text-muted-foreground mt-2">
            <div className="flex items-center gap-1.5">
              <MessageSquare className="h-3.5 w-3.5" />
              <span className="tabular-nums">
                {thread.message_count} message{thread.message_count !== 1 ? 's' : ''}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" />
              <span>{formatLastMessageTime(thread.last_message_at)}</span>
            </div>
          </div>
        </CardHeader>

        {thread.context_note && (
          <CardContent className="pt-0 pb-3">
            <div className="p-3 rounded-lg bg-muted border border-border text-sm text-muted-foreground italic">
              {thread.context_note}
            </div>
          </CardContent>
        )}

        <CardFooter className="pt-3 border-t border-border gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleOpenThread}
            className="flex-1"
          >
            <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
            Open
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleSaveToNote}
            className="flex-1"
          >
            <FileText className="h-3.5 w-3.5 mr-1.5" />
            Save to note
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setUnlinkDialogOpen(true)}
            className="text-muted-foreground hover:text-destructive"
            aria-label="Unlink thread"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </CardFooter>
      </Card>

      <AlertDialog open={unlinkDialogOpen} onOpenChange={setUnlinkDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unlink thread from project?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove the connection between this thread and the
              project. The thread and its messages will not be deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmUnlink}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Unlink
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

export default ThreadCard;
