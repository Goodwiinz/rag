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
      <AlertDialogContent className="rounded-(--nous-radius-lg) border border-(--nous-border-1) bg-(--nous-bg-1) shadow-(--nous-shadow-lg)">
        <AlertDialogHeader>
          <AlertDialogTitle className="text-(--nous-fg-1) tracking-tight">
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription className="text-(--nous-fg-3) text-xs">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="gap-2">
          <AlertDialogCancel
            onClick={handleCancel}
            className="border-(--nous-border-1) bg-(--nous-bg-2) text-(--nous-fg-3) hover:bg-(--nous-bg-3) hover:text-(--nous-fg-1) text-xs"
          >
            {cancelLabel}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            className={cn(
              'text-xs border transition-all',
              variant === 'destructive'
                ? 'bg-(--nous-mars)/10 border-(--nous-mars)/50 text-(--nous-mars) hover:bg-(--nous-mars)/20 hover:border-(--nous-mars)'
                : 'bg-(--nous-sol)/10 border-(--nous-sol)/50 text-(--nous-sol) hover:bg-(--nous-sol)/20 hover:border-(--nous-sol)'
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
