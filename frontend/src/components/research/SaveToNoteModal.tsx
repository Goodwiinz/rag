'use client';

import React, { useState } from 'react';
import { FileText, Loader2, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export interface SaveToNoteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (noteTitle: string, includeCitations: boolean) => Promise<void>;
}

export const SaveToNoteModal: React.FC<SaveToNoteModalProps> = ({
  isOpen,
  onClose,
  onSave,
}) => {
  const [noteTitle, setNoteTitle] = useState('');
  const [includeCitations, setIncludeCitations] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!noteTitle.trim()) {
      setError('Note title is required');
      return;
    }

    setIsSubmitting(true);
    try {
      await onSave(noteTitle.trim(), includeCitations);
      setNoteTitle('');
      setIncludeCitations(true);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save note');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenChange = (open: boolean) => {
    if (!open && !isSubmitting) {
      setNoteTitle('');
      setIncludeCitations(true);
      setError(null);
      onClose();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            Save thread to note
          </DialogTitle>
          <DialogDescription>
            This will be the filename of your markdown note
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="note-title" className="mb-1.5 block">
              Note title <span className="text-destructive">*</span>
            </Label>
            <Input
              id="note-title"
              type="text"
              value={noteTitle}
              onChange={(e) => setNoteTitle(e.target.value)}
              placeholder="e.g., Research Discussion Summary"
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
            <div className="flex-1">
              <span className="text-sm text-foreground">
                Include citations
              </span>
              <p className="text-xs text-muted-foreground mt-0.5">
                Add reference links to source documents in the note
              </p>
            </div>
            <Switch
              checked={includeCitations}
              onCheckedChange={setIncludeCitations}
              disabled={isSubmitting}
              aria-label="Include citations"
            />
          </div>

          {error && (
            <div
              role="alert"
              className="p-3 bg-destructive/10 border border-destructive/30 rounded text-sm text-destructive"
            >
              {error}
            </div>
          )}

          <div className="p-3 bg-muted rounded text-xs text-muted-foreground">
            The thread messages will be converted to a markdown note and saved
            to your project. You can access it from the project notes tab.
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
              disabled={isSubmitting || !noteTitle.trim()}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Save note
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default SaveToNoteModal;
