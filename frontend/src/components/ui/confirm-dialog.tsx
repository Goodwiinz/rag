import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { cn } from '@/lib/utils';
import * as React from 'react';

interface ConfirmDialogProps {
  trigger?: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'destructive';
  onConfirm: () => void;
  onCancel?: () => void;
}

export function ConfirmDialog({
  trigger,
  open: openProp,
  onOpenChange: onOpenChangeProp,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'default',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [internalOpen, setInternalOpen] = React.useState(false);
  const isControlled = openProp !== undefined;
  const open = isControlled ? openProp : internalOpen;
  const setOpen = (next: boolean) => {
    if (!isControlled) setInternalOpen(next);
    onOpenChangeProp?.(next);
  };

  const handleConfirm = () => {
    onConfirm();
    setOpen(false);
  };

  const handleCancel = () => {
    onCancel?.();
    setOpen(false);
  };

  // Uncontrolled mode requires a trigger
  if (!isControlled && !trigger) {
    throw new Error(
      'ConfirmDialog: either `trigger` (uncontrolled) or `open`/`onOpenChange` (controlled) must be provided.'
    );
  }

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      {!isControlled && (
        <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger>
      )}
      <AlertDialogContent className="rounded-[var(--nous-radius-lg)] border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)] shadow-[var(--nous-shadow-lg)]">
        <AlertDialogHeader>
          <AlertDialogTitle className="text-[var(--nous-fg-1)] tracking-tight">
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription className="text-[var(--nous-fg-3)] text-xs">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="gap-2">
          <AlertDialogCancel
            onClick={handleCancel}
            className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] text-[var(--nous-fg-3)] hover:bg-[var(--nous-bg-3)] hover:text-[var(--nous-fg-1)] text-xs"
          >
            {cancelLabel}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            className={cn(
              'text-xs border transition-all',
              variant === 'destructive'
                ? 'bg-[var(--nous-mars)]/10 border-[var(--nous-mars)]/50 text-[var(--nous-mars)] hover:bg-[var(--nous-mars)]/20 hover:border-[var(--nous-mars)]'
                : 'bg-[var(--nous-sol)]/10 border-[var(--nous-sol)]/50 text-[var(--nous-sol)] hover:bg-[var(--nous-sol)]/20 hover:border-[var(--nous-sol)]'
            )}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

// Convenience wrapper for delete actions
export function DeleteConfirmDialog({
  itemName,
  onConfirm,
  children,
}: {
  itemName: string;
  onConfirm: () => void;
  children: React.ReactNode;
}) {
  return (
    <ConfirmDialog
      trigger={children}
      title={`Delete ${itemName}?`}
      description={`This action cannot be undone. This will permanently delete the ${itemName}.`}
      confirmLabel="Delete"
      variant="destructive"
      onConfirm={onConfirm}
    />
  );
}
