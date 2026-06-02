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
  trigger: React.ReactNode;
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
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'default',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [open, setOpen] = React.useState(false);

  const handleConfirm = () => {
    onConfirm();
    setOpen(false);
  };

  const handleCancel = () => {
    onCancel?.();
    setOpen(false);
  };

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger>
      <AlertDialogContent className="rounded-[var(--nous-radius-lg)] border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)] shadow-[var(--nous-shadow-lg)]">
        <AlertDialogHeader>
          <AlertDialogTitle className="text-[var(--nous-fg-1)] font-mono tracking-tight">
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription className="text-[var(--nous-fg-3)] font-mono text-xs">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="gap-2">
          <AlertDialogCancel
            onClick={handleCancel}
            className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] text-[var(--nous-fg-3)] hover:bg-[var(--nous-bg-3)] hover:text-[var(--nous-fg-1)] font-mono text-xs uppercase tracking-wider"
          >
            {cancelLabel}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            className={cn(
              'font-mono text-xs uppercase tracking-wider border transition-all',
              variant === 'destructive'
                ? 'bg-red-500/10 border-red-500/50 text-red-400 hover:bg-red-500/20 hover:border-red-500'
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
