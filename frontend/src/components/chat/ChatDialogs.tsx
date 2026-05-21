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
import { Input } from '@/components/ui/input';
import type {
  BulkDeleteDialogState,
  DeleteDialogState,
  RenameDialogState,
} from '@/hooks/chat/useChatThreadActions';
import React from 'react';

interface ChatDialogsProps {
  renameDialog: RenameDialogState;
  setRenameDialog: React.Dispatch<React.SetStateAction<RenameDialogState>>;
  commitRename: () => void;
  deleteDialog: DeleteDialogState;
  setDeleteDialog: React.Dispatch<React.SetStateAction<DeleteDialogState>>;
  commitDeleteThread: () => void;
  bulkDeleteDialog: BulkDeleteDialogState;
  setBulkDeleteDialog: React.Dispatch<React.SetStateAction<BulkDeleteDialogState>>;
  commitBulkDelete: () => void;
}

export function ChatDialogs({
  renameDialog,
  setRenameDialog,
  commitRename,
  deleteDialog,
  setDeleteDialog,
  commitDeleteThread,
  bulkDeleteDialog,
  setBulkDeleteDialog,
  commitBulkDelete,
}: ChatDialogsProps) {
  return (
    <>
      {/* Rename dialog */}
      <AlertDialog
        open={renameDialog.open}
        onOpenChange={(open) => setRenameDialog((d) => ({ ...d, open }))}
      >
        <AlertDialogContent className="terminal-window border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-[var(--terminal-text)] font-mono tracking-tight">
              Rename thread
            </AlertDialogTitle>
          </AlertDialogHeader>
          <Input
            className="font-mono text-sm bg-[var(--terminal-surface)] border-[var(--terminal-border)] text-[var(--terminal-text)]"
            value={renameDialog.value}
            onChange={(e) =>
              setRenameDialog((d) => ({ ...d, value: e.target.value }))
            }
            onKeyDown={(e) => e.key === 'Enter' && commitRename()}
            autoFocus
          />
          <AlertDialogFooter>
            <AlertDialogCancel className="font-mono text-xs uppercase tracking-wider">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={commitRename}
              className="font-mono text-xs uppercase tracking-wider"
            >
              Rename
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete single thread dialog */}
      <AlertDialog
        open={deleteDialog.open}
        onOpenChange={(open) => setDeleteDialog((d) => ({ ...d, open }))}
      >
        <AlertDialogContent className="terminal-window border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-[var(--terminal-text)] font-mono tracking-tight">
              Delete thread?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-[var(--terminal-text-muted)] font-mono text-xs">
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="font-mono text-xs uppercase tracking-wider">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={commitDeleteThread}
              className="bg-red-500/10 border border-red-500/50 text-red-400 hover:bg-red-500/20 font-mono text-xs uppercase tracking-wider"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bulk delete dialog */}
      <AlertDialog
        open={bulkDeleteDialog.open}
        onOpenChange={(open) => setBulkDeleteDialog((d) => ({ ...d, open }))}
      >
        <AlertDialogContent className="terminal-window border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-[var(--terminal-text)] font-mono tracking-tight">
              Delete {bulkDeleteDialog.ids.length} threads?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-[var(--terminal-text-muted)] font-mono text-xs">
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="font-mono text-xs uppercase tracking-wider">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={commitBulkDelete}
              className="bg-red-500/10 border border-red-500/50 text-red-400 hover:bg-red-500/20 font-mono text-xs uppercase tracking-wider"
            >
              Delete all
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
