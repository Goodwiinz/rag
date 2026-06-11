'use client';

import React, { useState } from 'react';
import { MessageSquare, Loader2, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export interface StartChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStartChat: (initialMessage: string, threadTitle?: string) => Promise<void>;
}

export const StartChatModal: React.FC<StartChatModalProps> = ({
  isOpen,
  onClose,
  onStartChat,
}) => {
  const [initialMessage, setInitialMessage] = useState('');
  const [threadTitle, setThreadTitle] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!initialMessage.trim()) {
      setError('Initial message is required');
      return;
    }

    setIsSubmitting(true);
    try {
      await onStartChat(initialMessage.trim(), threadTitle.trim() || undefined);
      setInitialMessage('');
      setThreadTitle('');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start chat');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenChange = (open: boolean) => {
    if (!open && !isSubmitting) {
      setInitialMessage('');
      setThreadTitle('');
      setError(null);
      onClose();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-primary" />
            Start new chat
          </DialogTitle>
          <DialogDescription>
            This message will start the chat with project documents as context
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="initial-message" className="mb-1.5 block">
              Initial message <span className="text-destructive">*</span>
            </Label>
            <textarea
              id="initial-message"
              value={initialMessage}
              onChange={(e) => setInitialMessage(e.target.value)}
              placeholder="Enter your first message to start the conversation..."
              disabled={isSubmitting}
              className="w-full h-32 px-3 py-2 bg-background border border-border rounded text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 resize-none"
              required
            />
          </div>

          <div>
            <Label htmlFor="thread-title" className="mb-1.5 block">
              Thread title <span className="text-muted-foreground">(optional)</span>
            </Label>
            <Input
              id="thread-title"
              type="text"
              value={threadTitle}
              onChange={(e) => setThreadTitle(e.target.value)}
              placeholder="e.g., Research Discussion - Methods Analysis"
              disabled={isSubmitting}
            />
            <p className="text-xs text-muted-foreground mt-1">
              If not provided, a title will be generated automatically
            </p>
          </div>

          {error && (
            <div
              role="alert"
              className="p-3 bg-destructive/10 border border-destructive/30 rounded text-sm text-destructive"
            >
              {error}
            </div>
          )}

          <div className="p-3 bg-primary/10 border border-primary/30 rounded text-xs text-primary">
            This chat will use all documents in this project as RAG context. You
            can ask questions and have natural conversations about your research
            materials.
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleOpenChange.bind(null, false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || !initialMessage.trim()}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Starting chat...
                </>
              ) : (
                <>
                  <Send className="h-4 w-4 mr-2" />
                  Start chat
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default StartChatModal;
