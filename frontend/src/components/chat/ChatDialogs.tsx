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
  setBulkDeleteDialog: React.Dispatch<
    React.SetStateAction<BulkDeleteDialogState>
  >;
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
        <AlertDialogContent className="rounded-xl border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]">
          <AlertDialogHeader>
            <AlertDialogTitle
              className="text-[var(--nous-fg-1)] tracking-tight"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Rename thread
            </AlertDialogTitle>
          </AlertDialogHeader>
          <Input
            className="text-sm bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] text-[var(--nous-fg-1)]"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
            value={renameDialog.value}
            onChange={(e) =>
              setRenameDialog((d) => ({ ...d, value: e.target.value }))
            }
            onKeyDown={(e) => e.key === 'Enter' && commitRename()}
            autoFocus
          />
          <AlertDialogFooter>
            <AlertDialogCancel
              className="text-xs"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={commitRename}
              className="text-xs"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
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
        <AlertDialogContent className="rounded-xl border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]">
          <AlertDialogHeader>
            <AlertDialogTitle
              className="text-[var(--nous-fg-1)] tracking-tight"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Delete thread?
            </AlertDialogTitle>
            <AlertDialogDescription
              className="text-[var(--nous-fg-3)] text-xs"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              className="text-xs"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={commitDeleteThread}
              className="bg-[var(--nous-mars)]/10 border border-[var(--nous-mars)]/50 text-[var(--nous-mars)] hover:bg-[var(--nous-mars)]/20 text-xs"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
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
        <AlertDialogContent className="rounded-xl border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]">
          <AlertDialogHeader>
            <AlertDialogTitle
              className="text-[var(--nous-fg-1)] tracking-tight"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Delete {bulkDeleteDialog.ids.length} threads?
            </AlertDialogTitle>
            <AlertDialogDescription
              className="text-[var(--nous-fg-3)] text-xs"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              className="text-xs"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={commitBulkDelete}
              className="bg-[var(--nous-mars)]/10 border border-[var(--nous-mars)]/50 text-[var(--nous-mars)] hover:bg-[var(--nous-mars)]/20 text-xs"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Delete all
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
